# -*- coding: utf-8 -*-
"""SPC(통계적 공정 관리) 유틸: 관리 한계선, 공정능력지수, 합불 판정"""
import numpy as np
import pandas as pd


def control_limits(series: pd.Series):
    """I-chart 관리 한계선: 이동범위(MR) 기반 UCL/LCL.

    반환 dict(mean, ucl, lcl, sigma_est)
    """
    s = series.dropna().astype(float)
    if len(s) < 3:
        return None
    mr = s.diff().abs().dropna()
    sigma = mr.mean() / 1.128  # d2 for n=2
    mean = s.mean()
    return {"mean": mean, "ucl": mean + 3 * sigma,
            "lcl": mean - 3 * sigma, "sigma_est": sigma}


def cpk(series: pd.Series, lsl=None, usl=None):
    """공정능력지수 Cpk. 단측 스펙이면 해당 쪽만 계산."""
    s = series.dropna().astype(float)
    if len(s) < 3 or s.std(ddof=1) == 0:
        return np.nan
    mu, sd = s.mean(), s.std(ddof=1)
    vals = []
    if usl is not None:
        vals.append((usl - mu) / (3 * sd))
    if lsl is not None:
        vals.append((mu - lsl) / (3 * sd))
    return min(vals) if vals else np.nan


def judge_mos2(row, spec):
    """MoS2 합불: Raman Delta + PL 품질. 반환 (pass/fail/na, 사유)"""
    reasons = []
    delta = row.get("MoS2_delta", np.nan)
    if not np.isnan(delta):
        if delta > spec["delta_max"]:
            reasons.append(f"delta {delta:.2f} > {spec['delta_max']}")
    fwhm = row.get("PL_MoS2_fwhm_meV", np.nan)
    if not np.isnan(fwhm) and fwhm > spec["pl_fwhm_max"]:
        reasons.append(f"PL FWHM {fwhm:.0f} > {spec['pl_fwhm_max']:.0f} meV")
    imax = row.get("PL_MoS2_Imax", np.nan)
    if not np.isnan(imax) and imax < spec["pl_imax_min"]:
        reasons.append(f"PL Imax {imax:.0f} < {spec['pl_imax_min']:.0f}")
    has_data = not (np.isnan(delta) and np.isnan(fwhm) and np.isnan(imax))
    if not has_data:
        return "na", "no data"
    return ("fail", "; ".join(reasons)) if reasons else ("pass", "")


def judge_ws2(row, spec):
    reasons = []
    ratio = row.get("WS2_I2LA_over_IA1g", np.nan)
    if not np.isnan(ratio) and ratio < spec["ratio_min"]:
        reasons.append(f"I(2LA)/I(A1g) {ratio:.2f} < {spec['ratio_min']}")
    fwhm = row.get("PL_WS2_fwhm_meV", np.nan)
    if not np.isnan(fwhm) and fwhm > spec["pl_fwhm_max"]:
        reasons.append(f"PL FWHM {fwhm:.0f} > {spec['pl_fwhm_max']:.0f} meV")
    imax = row.get("PL_WS2_Imax", np.nan)
    if not np.isnan(imax) and imax < spec["pl_imax_min"]:
        reasons.append(f"PL Imax {imax:.0f} < {spec['pl_imax_min']:.0f}")
    has_data = not (np.isnan(ratio) and np.isnan(fwhm) and np.isnan(imax))
    if not has_data:
        return "na", "no data"
    return ("fail", "; ".join(reasons)) if reasons else ("pass", "")


def site_table(df: pd.DataFrame) -> pd.DataFrame:
    """측정 사이트(런 x 존 x 위치) 단위로 Raman/PL 결과를 병합.

    같은 사이트의 Raman 행과 PL 행을 한 행으로 합쳐 합불 판정에 사용.
    반복 측정(_2)은 마지막 값 사용.
    """
    keys = ["run", "date", "material", "sample", "zone", "site"]
    metric_cols = [c for c in df.columns
                   if c.startswith(("MoS2_", "WS2_", "PL_"))]
    merged = (df.sort_values("rep")
                .groupby(keys)[metric_cols]
                .last()
                .reset_index())
    return merged
