# -*- coding: utf-8 -*-
"""스펙트럼 로딩 · 전처리 · Lorentzian 피크 피팅"""
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import medfilt, savgol_filter


def load_spectrum(path: Path):
    """2열(x,y) 또는 3열(idx,x,y) 탭 구분 txt 모두 지원"""
    arr = np.loadtxt(path)
    if arr.ndim != 2 or arr.shape[0] < 10:
        raise ValueError(f"not a spectrum: {path}")
    if arr.shape[1] >= 3:
        x, y = arr[:, 1], arr[:, 2]
    else:
        x, y = arr[:, 0], arr[:, 1]
    order = np.argsort(x)
    return x[order], y[order]


def despike(y, kernel=5, thresh=6.0):
    """cosmic ray 제거: median filter 잔차가 큰 스파이크만 치환"""
    med = medfilt(y, kernel)
    resid = y - med
    sigma = 1.4826 * np.median(np.abs(resid - np.median(resid))) + 1e-12
    out = y.copy()
    mask = np.abs(resid) > thresh * sigma
    out[mask] = med[mask]
    return out


def lorentz_lin(x, x0, gamma, amp, a, b):
    """Lorentzian + 선형 배경"""
    return amp * gamma**2 / ((x - x0) ** 2 + gamma**2) + a * x + b


def fit_peak(x, y, lo, hi, min_snr=3.0, edge_margin=1.5, min_fwhm=1.5):
    """구간 [lo, hi] 내 단일 피크 피팅.

    저SNR·피팅 실패 시 None. 성공 시 dict(center, fwhm, height, area).
    그리드 간격(~0.86 cm-1)보다 정밀한 위치를 얻기 위해 argmax가 아닌
    함수 피팅을 사용한다.

    품질 게이트: 중심이 구간 경계에 붙거나(edge_margin 이내) FWHM이
    그리드 간격 수준(min_fwhm 미만)이면 스파이크/노이즈 오피팅으로
    간주하고 기각한다.
    """
    m = (x >= lo) & (x <= hi)
    xs, ys = x[m], y[m]
    if len(xs) < 8:
        return None
    i0 = int(np.argmax(ys))
    base = np.percentile(ys, 10)
    amp0 = ys[i0] - base
    noise = np.std(np.diff(ys)) / np.sqrt(2) + 1e-12
    if amp0 <= 0 or amp0 < min_snr * noise:
        return None
    p0 = [xs[i0], (hi - lo) / 8, amp0, 0.0, base]
    try:
        popt, _ = curve_fit(
            lorentz_lin, xs, ys, p0=p0,
            bounds=([lo, 0.1, 0, -np.inf, -np.inf],
                    [hi, hi - lo, np.inf, np.inf, np.inf]),
            maxfev=5000,
        )
    except Exception:
        return None
    x0, gamma, amp = popt[:3]
    if amp < min_snr * noise:
        return None
    if (x0 - lo) < edge_margin or (hi - x0) < edge_margin:
        return None
    if 2 * gamma < min_fwhm:
        return None
    return {"center": float(x0), "fwhm": float(2 * gamma),
            "height": float(amp), "area": float(np.pi * amp * gamma)}


def measure_fwhm_direct(x, y, i_peak):
    """반값폭 직접 측정 (선형 보간) — 비대칭 PL 피크에 견고"""
    base = np.percentile(y, 5)
    half = base + (y[i_peak] - base) / 2
    li = i_peak
    while li > 0 and y[li] > half:
        li -= 1
    ri = i_peak
    while ri < len(y) - 1 and y[ri] > half:
        ri += 1
    if li == 0 or ri == len(y) - 1:
        return np.nan
    xl = np.interp(half, [y[li], y[li + 1]], [x[li], x[li + 1]])
    xr = np.interp(half, [y[ri], y[ri - 1]], [x[ri], x[ri - 1]])
    return xr - xl


def find_pl_peak(x, y, lo, hi, min_snr=5.0):
    """PL A exciton: 스무딩 후 최대점 + 직접 FWHM. 반환 dict 또는 None"""
    ys = savgol_filter(y, 11, 3) if len(y) > 15 else y
    m = (x >= lo) & (x <= hi)
    if m.sum() < 10:
        return None
    xs, yw = x[m], ys[m]
    i0 = int(np.argmax(yw))
    base = np.percentile(yw, 5)
    noise = np.std(np.diff(yw)) / np.sqrt(2) + 1e-12
    if yw[i0] - base < min_snr * noise:
        return None
    fw = measure_fwhm_direct(xs, yw, i0)
    return {
        "peak_eV": float(xs[i0]),
        "peak_nm": 1239.84 / float(xs[i0]),
        "Imax": float(yw[i0]),
        "fwhm_meV": float(fw * 1000) if not np.isnan(fw) else np.nan,
    }
