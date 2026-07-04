# -*- coding: utf-8 -*-
"""분석 파라미터 정의 — 피크 탐색 구간, 스펙 기준, 층수 판정 기준"""

SI_REF = 520.7  # cm-1, Si 기준 피크 (라만 축 보정)
SI_WINDOW = (505, 535)

# 물질별 라만 피크 탐색 구간 (cm-1)
RAMAN_WINDOWS = {
    "MoS2": {"E2g": (373, 396), "A1g": (396, 415)},
    "WS2": {"2LA/E2g": (340, 366), "A1g": (408, 428)},
}

# PL A exciton 탐색 구간 (eV)
PL_WINDOWS = {"MoS2": (1.70, 2.02), "WS2": (1.85, 2.20)}

# MoS2 층수 판정: Delta = A1g - E2g (cm-1)
MOS2_LAYER_BINS = [
    (19.5, "1L"),
    (21.5, "1-2L"),
    (23.5, "2-3L"),
    (25.5, "3-4L"),
    (float("inf"), "bulk-like"),
]

# WS2 1L 판정: I(2LA)/I(A1g) 강도비 (532 nm 공명 조건)
WS2_1L_RATIO_MIN = 2.2

# 합불(Pass/Fail) 스펙 기준 — 대시보드에서 조정 가능한 기본값
SPEC = {
    "MoS2": {
        "delta_max": 21.5,      # cm-1, 이하면 1-2L 합격
        "pl_fwhm_max": 110.0,   # meV
        "pl_imax_min": 300.0,   # counts
    },
    "WS2": {
        "ratio_min": WS2_1L_RATIO_MIN,
        "pl_fwhm_max": 90.0,
        "pl_imax_min": 500.0,
    },
}


def mos2_layers_from_delta(delta: float) -> str:
    import math
    if delta is None or (isinstance(delta, float) and math.isnan(delta)):
        return ""
    for upper, name in MOS2_LAYER_BINS:
        if delta < upper:
            return name
    return "bulk-like"
