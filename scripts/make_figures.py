# -*- coding: utf-8 -*-
"""README용 대표 그림 생성: output/summary.csv -> docs/figures/*.png

실행:  python scripts/make_figures.py  (저장소 루트에서)
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.spc import control_limits, site_table  # noqa: E402

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

FIG_DIR = ROOT / "docs" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(ROOT / "output" / "summary.csv")
for col in ("date", "sample", "zone", "site"):
    df[col] = df[col].astype(str)
sites = site_table(df)

# 1) MoS2 Delta 히스토그램 (층수 판정)
sub = sites.dropna(subset=["MoS2_delta"])
fig, ax = plt.subplots(figsize=(7, 4.2))
ax.hist(sub["MoS2_delta"], bins=np.arange(17, 27, 0.5),
        color="tab:blue", edgecolor="k", alpha=0.85)
for edge, lab in [(19.5, "1L"), (21.5, "2L"), (23.5, "3L"), (25.5, "bulk")]:
    ax.axvline(edge, color="gray", ls="--", lw=0.8)
    ax.text(edge, ax.get_ylim()[1] * 0.97, lab, fontsize=8, ha="center")
ax.set_xlabel(r"$\Delta$ = A$_{1g}$ $-$ E$^1_{2g}$ (cm$^{-1}$)")
ax.set_ylabel("Site count")
ax.set_title("MoS$_2$ layer-number metrology: peak separation distribution")
fig.tight_layout()
fig.savefig(FIG_DIR / "mos2_delta_hist.png", dpi=170)
plt.close(fig)

# 2) SPC I-chart: MoS2 Delta
sub = sites.dropna(subset=["MoS2_delta"]).sort_values(
    ["date", "sample", "zone", "site"]).reset_index(drop=True)
lim = control_limits(sub["MoS2_delta"])
fig, ax = plt.subplots(figsize=(8.5, 4.2))
seq = np.arange(len(sub))
ooc = (sub["MoS2_delta"] > lim["ucl"]) | (sub["MoS2_delta"] < lim["lcl"])
ax.plot(seq, sub["MoS2_delta"], "-", color="steelblue", lw=1)
ax.scatter(seq[~ooc], sub["MoS2_delta"][~ooc], c="steelblue", zorder=3)
ax.scatter(seq[ooc], sub["MoS2_delta"][ooc], c="crimson", zorder=3,
           label="OOC (관리이탈)")
for yv, nm in [(lim["mean"], "CL"), (lim["ucl"], "UCL(+3σ)"),
               (lim["lcl"], "LCL(-3σ)")]:
    ax.axhline(yv, color="gray", ls="--" if nm != "CL" else "-", lw=0.9)
    ax.text(len(sub) - 0.5, yv, nm, fontsize=8, va="bottom", ha="right")
dates = sub["date"].values
for i in range(1, len(dates)):
    if dates[i] != dates[i - 1]:
        ax.axvline(i - 0.5, color="lightgray", lw=0.8)
ax.set_xlabel("측정 순서 (세로선 = 성장 런 경계)")
ax.set_ylabel(r"$\Delta$ (cm$^{-1}$)")
ax.set_title("SPC I-chart: MoS$_2$ $\\Delta$ (thickness indicator) run trend")
if ooc.any():
    ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIG_DIR / "spc_ichart_mos2_delta.png", dpi=170)
plt.close(fig)

# 3) 존별 boxplot (공정 조건 -> 결과)
sub = sites.dropna(subset=["MoS2_delta"])
zones = sorted(sub["zone"].unique())
fig, ax = plt.subplots(figsize=(6.5, 4.2))
ax.boxplot([sub[sub["zone"] == z]["MoS2_delta"] for z in zones],
           tick_labels=zones)
for i, z in enumerate(zones, 1):
    v = sub[sub["zone"] == z]["MoS2_delta"]
    ax.scatter(np.full(len(v), i) + np.random.uniform(-0.06, 0.06, len(v)),
               v, alpha=0.6, s=22, color="tab:blue", zorder=3)
ax.axhline(19.5, color="gray", ls="--", lw=0.8)
ax.text(0.55, 19.55, "1L 경계", fontsize=8)
ax.set_xlabel("존 (3-zone furnace 위치 = 공정 조건)")
ax.set_ylabel(r"$\Delta$ (cm$^{-1}$)")
ax.set_title("공정 조건-계측 상관: 존 위치별 MoS$_2$ 두께 분포")
fig.tight_layout()
fig.savefig(FIG_DIR / "zone_effect_boxplot.png", dpi=170)
plt.close(fig)

# 4) 라벨 vs 자동 피팅 교차 검증
chk = df[df["label_vs_fit_diff"].notna()].copy()
fig, ax = plt.subplots(figsize=(7, 4.2))
for mat, c in [("MoS2", "tab:blue"), ("WS2", "tab:red")]:
    s = chk[chk["material"] == mat]
    ax.scatter(np.arange(len(s)) + (0 if mat == "MoS2" else len(chk[chk["material"] == "MoS2"])),
               s["label_vs_fit_diff"], color=c, label=mat, s=36, edgecolor="k")
ax.axhspan(-1, 1, color="green", alpha=0.08)
ax.axhline(0, color="gray", lw=0.8)
ax.set_xlabel("측정 파일 (기록 라벨 보유분)")
ax.set_ylabel("자동 피팅 − 수동 기록 (cm$^{-1}$)")
ax.set_title("수동 기록 vs 자동 피팅 교차 검증 (녹색 = ±1 cm$^{-1}$ 일치)")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIG_DIR / "label_vs_fit_check.png", dpi=170)
plt.close(fig)

print(f"figures -> {FIG_DIR}")
