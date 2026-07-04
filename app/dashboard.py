# -*- coding: utf-8 -*-
"""TMD CVD 공정-계측 분석 대시보드 (Streamlit)

실행:  streamlit run app/dashboard.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import SPEC  # noqa: E402
from src.pipeline import run_pipeline  # noqa: E402
from src.spc import (cpk, control_limits, judge_mos2, judge_ws2,  # noqa: E402
                     site_table)

st.set_page_config(page_title="TMD Fab Analytics", page_icon="🧪",
                   layout="wide")

SUMMARY = ROOT / "output" / "summary.csv"


@st.cache_data
def load_summary():
    if not SUMMARY.exists():
        df = run_pipeline(verbose=False)
    else:
        df = pd.read_csv(SUMMARY)
    for col in ("date", "sample", "zone", "site"):
        df[col] = df[col].astype(str)
    return df


df = load_summary()
sites = site_table(df)

# ---------------------------------------------------------------- 사이드바
st.sidebar.title("🧪 TMD Fab Analytics")
st.sidebar.caption("CVD 성장 → Raman/PL 계측 → SPC 산포 분석")

materials = sorted(df["material"].unique())
sel_mat = st.sidebar.multiselect("물질(공정)", materials, default=materials)

st.sidebar.subheader("합불 스펙 기준")
spec_mos2 = dict(SPEC["MoS2"])
spec_ws2 = dict(SPEC["WS2"])
spec_mos2["delta_max"] = st.sidebar.slider(
    "MoS₂ Δ 상한 (cm⁻¹)", 18.0, 26.0, float(SPEC["MoS2"]["delta_max"]), 0.1,
    help="A1g-E2g 간격. 작을수록 얇음 (~19.5 이하 = 1L)")
spec_mos2["pl_fwhm_max"] = st.sidebar.slider(
    "MoS₂ PL FWHM 상한 (meV)", 60.0, 200.0, float(SPEC["MoS2"]["pl_fwhm_max"]), 5.0)
spec_ws2["ratio_min"] = st.sidebar.slider(
    "WS₂ I(2LA)/I(A1g) 하한", 1.0, 8.0, float(SPEC["WS2"]["ratio_min"]), 0.1,
    help="532 nm 공명에서 1L일수록 큼 (>2.2 = 1L)")
spec_ws2["pl_fwhm_max"] = st.sidebar.slider(
    "WS₂ PL FWHM 상한 (meV)", 50.0, 150.0, float(SPEC["WS2"]["pl_fwhm_max"]), 5.0)

fsel = sites[sites["material"].isin(sel_mat)].copy()

# 합불 판정
def judge(row):
    if row["material"] == "WS2":
        return judge_ws2(row, spec_ws2)
    if row["material"] == "MoS2":
        return judge_mos2(row, spec_mos2)
    # 이종접합: 두 물질 모두 판정
    r1, m1 = judge_mos2(row, spec_mos2)
    r2, m2 = judge_ws2(row, spec_ws2)
    if "fail" in (r1, r2):
        return "fail", "; ".join(x for x in (m1, m2) if x)
    if "pass" in (r1, r2):
        return "pass", ""
    return "na", "no data"

fsel[["judgement", "fail_reason"]] = fsel.apply(
    lambda r: pd.Series(judge(r)), axis=1)

# ---------------------------------------------------------------- KPI
judged = fsel[fsel["judgement"] != "na"]
yield_pct = 100 * (judged["judgement"] == "pass").mean() if len(judged) else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("측정 사이트", f"{len(fsel)}")
c2.metric("성장 런", f"{fsel['run'].nunique()}")
c3.metric("판정 가능 사이트", f"{len(judged)}")
c4.metric("수율 (Pass rate)", f"{yield_pct:.0f}%")

tab_map, tab_spc, tab_judge, tab_corr, tab_check = st.tabs(
    ["🗺️ 존-위치 맵", "📈 SPC 관리도", "✅ 합불 판정", "🔬 상관 분석",
     "🔎 라벨 교차검증"])

# ---------------------------------------------------------------- 존-위치 맵
with tab_map:
    st.subheader("기판 내 균일도 — 존(Z)·위치별 계측 맵")
    st.caption("3-zone furnace의 존 위치(Z1~Z3)가 공정 조건(온도·전구체 농도 프로파일)에 "
               "해당합니다. 웨이퍼 맵의 축소판으로 존별 산포를 확인합니다.")
    metric_options = {
        "MoS₂ Δ (cm⁻¹, 층수)": "MoS2_delta",
        "MoS₂ PL 강도": "PL_MoS2_Imax",
        "MoS₂ PL FWHM (meV)": "PL_MoS2_fwhm_meV",
        "WS₂ I(2LA)/I(A1g)": "WS2_I2LA_over_IA1g",
        "WS₂ A1g 위치 (cm⁻¹, 보정)": "WS2_A1g_cal",
        "WS₂ PL 강도": "PL_WS2_Imax",
        "WS₂ PL FWHM (meV)": "PL_WS2_fwhm_meV",
    }
    sel_metric = st.selectbox("계측 항목", list(metric_options.keys()))
    col = metric_options[sel_metric]
    sub = fsel.dropna(subset=[col]) if col in fsel else pd.DataFrame()
    if sub.empty:
        st.info("선택한 항목에 데이터가 없습니다. 물질 필터를 확인하세요.")
    else:
        sub = sub.copy()
        sub["pos"] = "Z" + sub["zone"].str.lstrip("Z") + "-" + sub["site"]
        fig = px.scatter(
            sub, x="zone", y="run", size=np.abs(sub[col]) + 0.1, color=col,
            symbol="site", color_continuous_scale="RdYlGn_r",
            hover_data=["pos", col, "judgement"],
            labels={"zone": "존 (furnace 위치)", "run": "성장 런"})
        fig.update_layout(height=450)
        st.plotly_chart(fig, width='stretch')

        pv = sub.pivot_table(index="run", columns="pos", values=col,
                             aggfunc="mean")
        st.dataframe(pv.style.background_gradient(cmap="RdYlGn_r", axis=None)
                     .format("{:.2f}"), width='stretch')
        zstat = sub.groupby("zone")[col].agg(["mean", "std", "count"])
        st.caption("존별 통계 (산포 = 존 간 공정 불균일)")
        st.dataframe(zstat.style.format("{:.3f}"))

# ---------------------------------------------------------------- SPC
with tab_spc:
    st.subheader("런별 트렌드 + I-chart 관리 한계선 (±3σ, MR 기반)")
    spc_options = {
        "MoS₂ Δ (cm⁻¹)": ("MoS2_delta", "MoS2"),
        "MoS₂ A1g 위치 보정 (cm⁻¹)": ("MoS2_A1g_cal", "MoS2"),
        "MoS₂ PL FWHM (meV)": ("PL_MoS2_fwhm_meV", "MoS2"),
        "WS₂ A1g 위치 보정 (cm⁻¹)": ("WS2_A1g_cal", "WS2"),
        "WS₂ I(2LA)/I(A1g)": ("WS2_I2LA_over_IA1g", "WS2"),
        "WS₂ PL FWHM (meV)": ("PL_WS2_fwhm_meV", "WS2"),
    }
    sel_spc = st.selectbox("관리 항목", list(spc_options.keys()))
    col, mat = spc_options[sel_spc]
    sub = fsel.dropna(subset=[col]).sort_values(["date", "sample", "zone", "site"]) \
        if col in fsel else pd.DataFrame()
    if len(sub) < 3:
        st.info("데이터가 부족합니다 (3점 이상 필요).")
    else:
        lim = control_limits(sub[col])
        seq = np.arange(len(sub))
        fig = go.Figure()
        fig.add_scatter(x=seq, y=sub[col], mode="lines+markers",
                        marker=dict(size=8,
                                    color=np.where(
                                        (sub[col] > lim["ucl"]) |
                                        (sub[col] < lim["lcl"]),
                                        "crimson", "steelblue")),
                        text=sub["run"] + " " + sub["zone"] + "-" + sub["site"],
                        name=sel_spc)
        for yv, nm, dash in [(lim["mean"], "CL", "solid"),
                             (lim["ucl"], "UCL(+3σ)", "dash"),
                             (lim["lcl"], "LCL(-3σ)", "dash")]:
            fig.add_hline(y=yv, line_dash=dash, line_color="gray",
                          annotation_text=nm)
        # 날짜 경계 표시
        dates = sub["date"].values
        for i in range(1, len(dates)):
            if dates[i] != dates[i - 1]:
                fig.add_vline(x=i - 0.5, line_color="lightgray", line_width=1)
        fig.update_layout(height=430, xaxis_title="측정 순서 (세로선=런 경계)",
                          yaxis_title=sel_spc)
        st.plotly_chart(fig, width='stretch')

        ooc = ((sub[col] > lim["ucl"]) | (sub[col] < lim["lcl"])).sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("평균 (CL)", f"{lim['mean']:.3f}")
        c2.metric("σ 추정 (MR/d2)", f"{lim['sigma_est']:.3f}")
        c3.metric("관리이탈점 (OOC)", f"{ooc}")
        if mat == "MoS2" and col == "MoS2_delta":
            c4.metric("Cpk (USL=Δ상한)",
                      f"{cpk(sub[col], usl=spec_mos2['delta_max']):.2f}")
        elif mat == "WS2" and col == "WS2_I2LA_over_IA1g":
            c4.metric("Cpk (LSL=비율하한)",
                      f"{cpk(sub[col], lsl=spec_ws2['ratio_min']):.2f}")

# ---------------------------------------------------------------- 합불
with tab_judge:
    st.subheader("사이트별 합불 판정 (스펙 기준은 사이드바에서 조정)")
    show = fsel[["run", "zone", "site", "material", "MoS2_delta",
                 "MoS2_layers_est", "WS2_I2LA_over_IA1g",
                 "PL_MoS2_fwhm_meV", "PL_WS2_fwhm_meV",
                 "judgement", "fail_reason"]].copy()
    show = show.sort_values(["run", "zone", "site"])

    def color_judge(v):
        return {"pass": "background-color:#d4efdf",
                "fail": "background-color:#fadbd8"}.get(v, "")
    st.dataframe(show.style.map(color_judge, subset=["judgement"])
                 .format(precision=2), width='stretch', height=480)

    st.subheader("런별 수율")
    runjq = judged.groupby("run")["judgement"] \
        .apply(lambda s: 100 * (s == "pass").mean()).rename("yield_%")
    st.bar_chart(runjq)

# ---------------------------------------------------------------- 상관
with tab_corr:
    st.subheader("공정 조건 ↔ 계측 결과 상관 분석")
    left, right = st.columns(2)
    with left:
        st.markdown("**존 위치 → MoS₂ 층수(Δ)** — 존별 온도·전구체 프로파일 효과")
        sub = fsel.dropna(subset=["MoS2_delta"])
        if not sub.empty:
            fig = px.box(sub, x="zone", y="MoS2_delta", points="all",
                         color="zone",
                         labels={"MoS2_delta": "Δ (cm⁻¹)", "zone": "존"})
            fig.add_hline(y=19.5, line_dash="dash",
                          annotation_text="1L 경계 (19.5)")
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, width='stretch')
            # 일원분산분석
            groups = [g[1].values for g in sub.groupby("zone")["MoS2_delta"]
                      if len(g[1]) >= 2]
            if len(groups) >= 2:
                from scipy.stats import f_oneway
                f, p = f_oneway(*groups)
                st.caption(f"one-way ANOVA: F={f:.2f}, p={p:.4f} "
                           f"({'존 간 유의한 차이 있음' if p < 0.05 else '유의차 없음'} @ α=0.05)")
    with right:
        st.markdown("**Raman(구조) ↔ PL(광학 품질)** — 계측 항목 간 정합성")
        pairs = {
            "MoS₂: Δ vs PL FWHM": ("MoS2_delta", "PL_MoS2_fwhm_meV"),
            "MoS₂: Δ vs PL 강도(log)": ("MoS2_delta", "PL_MoS2_Imax"),
            "WS₂: 강도비 vs PL 강도(log)": ("WS2_I2LA_over_IA1g", "PL_WS2_Imax"),
        }
        sel_pair = st.selectbox("항목 쌍", list(pairs.keys()))
        xc, yc = pairs[sel_pair]
        sub = fsel.dropna(subset=[xc, yc])
        if len(sub) >= 3:
            logy = "강도" in sel_pair
            fig = px.scatter(sub, x=xc, y=yc, color="zone",
                             hover_data=["run", "site"], log_y=logy)
            fig.update_layout(height=400)
            st.plotly_chart(fig, width='stretch')
            r = np.corrcoef(sub[xc], np.log10(sub[yc]) if logy else sub[yc])[0, 1]
            st.caption(f"Pearson r = {r:.2f} (n={len(sub)})"
                       + (" — log(강도) 기준" if logy else ""))
        else:
            st.info("이 조합의 동시 측정 데이터가 부족합니다.")

# ---------------------------------------------------------------- 교차검증
with tab_check:
    st.subheader("수동 기록(파일명 라벨) vs 자동 피팅 — 계측 기록 신뢰성 검증")
    st.caption("측정 당시 Origin에서 수동으로 읽어 파일명에 기록한 값과 "
               "자동 Lorentzian 피팅 결과를 비교합니다. "
               "데이터 그리드 간격(~0.86 cm⁻¹)보다 큰 차이는 수동 기록 오류 후보입니다.")
    chk = df[df["label_vs_fit_diff"].notna()].copy()
    chk = chk[chk["material"].isin(sel_mat)]
    if chk.empty:
        st.info("교차검증 대상(숫자 라벨이 있는 파일)이 없습니다.")
    else:
        chk["abs_diff"] = chk["label_vs_fit_diff"].abs()
        chk["status"] = np.where(chk["abs_diff"] < 1.0, "일치(<1 cm⁻¹)",
                                 "불일치(≥1 cm⁻¹) — 기록 오류 후보")
        fig = px.strip(chk, x="material", y="label_vs_fit_diff",
                       color="status", hover_data=["file"],
                       labels={"label_vs_fit_diff": "피팅 − 라벨 (cm⁻¹)"})
        fig.add_hline(y=0, line_color="gray")
        fig.update_layout(height=380)
        st.plotly_chart(fig, width='stretch')
        st.dataframe(
            chk.sort_values("abs_diff", ascending=False)
            [["file", "label_parsed", "label_vs_fit_diff", "status"]]
            .style.format(precision=2),
            width='stretch')
        n_bad = (chk["abs_diff"] >= 1.0).sum()
        st.metric("기록 오류 후보", f"{n_bad} / {len(chk)}",
                  help="자동화된 계측 파이프라인이 수동 기록의 휴먼 에러를 잡아냅니다.")
