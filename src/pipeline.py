# -*- coding: utf-8 -*-
"""일괄 계측 파이프라인: raw 스펙트럼 폴더 -> 피크 피팅 -> summary 테이블

실행:  python -m src.pipeline  (저장소 루트에서)
출력:  output/summary.csv, output/summary.xlsx
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (PL_WINDOWS, RAMAN_WINDOWS, SI_REF, SI_WINDOW,
                     mos2_layers_from_delta)
from .spectra import despike, find_pl_peak, fit_peak, load_spectrum

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"

# 파일명 규칙: "날짜 물질 #샘플 Z존-위치 [PL|Raman][_2] (라벨).txt"
FNAME_RE = re.compile(
    r"(?P<date>\d{6})\s+(?P<material>MoS2-WS2|MoS2|WS2)\s+#(?P<sample>\d+)\s+"
    r"(?P<zone>Z\d+)-(?P<site>\d+)[ _]+(?P<kind>PL|Raman)(?P<rep>_2)?"
    r"(?:\s*\((?P<label>[^)]*)\))?\.txt",
    re.IGNORECASE,
)


def parse_filename(path: Path):
    m = FNAME_RE.match(path.name)
    if not m:
        return None
    d = m.groupdict()
    d["rep"] = 2 if d["rep"] else 1
    d["label"] = (d["label"] or "").strip()
    d["run"] = f"{d['date']} {d['material']} #{d['sample']}"
    return d


def analyze_raman(x, y, material):
    res = {}
    si = fit_peak(x, y, *SI_WINDOW)
    res["Si_pos_raw"] = si["center"] if si else np.nan
    shift = SI_REF - si["center"] if si else 0.0
    res["calib_shift"] = shift if si else np.nan

    mats = ["MoS2", "WS2"] if material == "MoS2-WS2" else [material]
    for mat in mats:
        for name, (lo, hi) in RAMAN_WINDOWS[mat].items():
            p = fit_peak(x, y, lo, hi)
            key = f"{mat}_{name}".replace("/", "_")
            res[f"{key}_raw"] = p["center"] if p else np.nan
            res[f"{key}_cal"] = p["center"] + shift if p else np.nan
            res[f"{key}_fwhm"] = p["fwhm"] if p else np.nan
            res[f"{key}_height"] = p["height"] if p else np.nan

    if "MoS2" in mats:
        res["MoS2_delta"] = (res.get("MoS2_A1g_raw", np.nan)
                             - res.get("MoS2_E2g_raw", np.nan))
        res["MoS2_layers_est"] = mos2_layers_from_delta(res["MoS2_delta"])
        if si and not np.isnan(res.get("MoS2_A1g_height", np.nan)):
            res["MoS2_A1g_over_Si"] = res["MoS2_A1g_height"] / si["height"]
    if "WS2" in mats:
        h2la = res.get("WS2_2LA_E2g_height", np.nan)
        ha1g = res.get("WS2_A1g_height", np.nan)
        res["WS2_I2LA_over_IA1g"] = (h2la / ha1g
                                     if ha1g and not np.isnan(ha1g) else np.nan)
    return res


def analyze_pl(x, y, material):
    res = {}
    mats = ["MoS2", "WS2"] if material == "MoS2-WS2" else [material]
    for mat in mats:
        p = find_pl_peak(x, y, *PL_WINDOWS[mat])
        prefix = f"PL_{mat}"
        if p is None:
            res[f"{prefix}_peak_eV"] = np.nan
            continue
        for k, v in p.items():
            res[f"{prefix}_{k}"] = v
    return res


def cross_check(row):
    """파일명 괄호 라벨(수동 기록) vs 자동 피팅 결과 비교.

    MoS2 Raman 라벨 = Delta, WS2 Raman 라벨 = A1g 위치(raw).
    반환: (해석된 라벨, 피팅-라벨 차이)
    """
    label = row["label"]
    if not label or "x" in label.lower():
        return ("no-peak" if label else "", np.nan)
    try:
        val = float(label)
    except ValueError:
        return (label, np.nan)  # "(1L, H)" 같은 층수 메모
    if row["kind"].lower() == "raman":
        if row["material"] == "MoS2":
            return (f"delta={val}", row.get("MoS2_delta", np.nan) - val)
        if row["material"] == "WS2":
            return (f"A1g={val}", row.get("WS2_A1g_raw", np.nan) - val)
    return (label, np.nan)


def run_pipeline(data_dir=DATA_DIR, out_dir=OUT_DIR, verbose=True):
    out_dir.mkdir(exist_ok=True)
    records = []
    txt_files = sorted(Path(data_dir).rglob("*.txt"))
    if verbose:
        print(f"{len(txt_files)} txt files found under {data_dir}")

    for path in txt_files:
        info = parse_filename(path)
        if info is None:
            if verbose:
                print(f"  [skip] filename pattern mismatch: {path.name}")
            continue
        try:
            x, y = load_spectrum(path)
        except Exception as e:
            if verbose:
                print(f"  [skip] load failed: {path.name} ({e})")
            continue
        y = despike(y)

        row = {"file": path.name, "folder": path.parent.name,
               "relpath": str(path.relative_to(data_dir)), **info}
        if info["kind"].lower() == "raman":
            row.update(analyze_raman(x, y, info["material"]))
        else:
            row.update(analyze_pl(x, y, info["material"]))

        lab, diff = cross_check(row)
        row["label_parsed"] = lab
        row["label_vs_fit_diff"] = diff
        records.append(row)

    df = pd.DataFrame(records)
    num_cols = df.select_dtypes(float).columns
    df[num_cols] = df[num_cols].round(3)

    df.to_csv(out_dir / "summary.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(out_dir / "summary.xlsx") as xw:
        df[df["kind"].str.lower() == "raman"].dropna(axis=1, how="all") \
            .to_excel(xw, sheet_name="Raman", index=False)
        df[df["kind"].str.lower() == "pl"].dropna(axis=1, how="all") \
            .to_excel(xw, sheet_name="PL", index=False)
    if verbose:
        print(f"-> {out_dir / 'summary.csv'}")
        chk = df[df["label_vs_fit_diff"].notna()]
        if not chk.empty:
            ok = (chk["label_vs_fit_diff"].abs() < 1.0).sum()
            print(f"cross-check: {ok}/{len(chk)} manual labels within 1 cm-1 of fit")
    return df


if __name__ == "__main__":
    run_pipeline()
