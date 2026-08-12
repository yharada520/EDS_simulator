"""EDS スペクトル・シミュレータ（Streamlit UI）/ EDS Spectrum Simulator.

フェーズ1（計数統計）＋フェーズ2（xraylib 連携）＋フェーズ3（薄膜/基板）統合版。
UI 文字列は i18n.py で日本語/英語を切り替える（物理演算 eds_sim は言語非依存）。
"""

from __future__ import annotations

import logging

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from eds_sim.config import (
    BeamConditions,
    DetectorConfig,
    ElementSpec,
    EnergyAxis,
    Layer,
    LayerConfig,
    SimulationConfig,
)
from eds_sim.composition import parse_formula, resolve_density
from eds_sim.elements import xraylib_available
from eds_sim.spectrum import simulate, SpectrumResult
from i18n import COMMON_ELEMENTS, LANGUAGES, density_source_label, t

logging.basicConfig(level=logging.INFO)


def language_selector() -> str:
    """サイドバー先頭の言語切替。言語コード（'ja'/'en'）を返す。"""
    display = st.sidebar.selectbox(
        "言語 / Language", list(LANGUAGES.keys()), index=0, key="lang")
    return LANGUAGES[display]


# --------------------------------------------------------------------------
# サイドバー: 入力 UI
# --------------------------------------------------------------------------
def build_sidebar(lang: str) -> SimulationConfig:
    st.sidebar.header(t("sample_model", lang))
    mode = st.sidebar.radio(
        t("mode", lang), ["bulk", "thin_film"],
        format_func=lambda m: t(f"mode_{'bulk' if m == 'bulk' else 'film'}", lang),
        help=t("mode_help", lang),
    )

    st.sidebar.header(t("conditions", lang))
    kv = st.sidebar.slider(t("kv", lang), 1.0, 30.0, 15.0, 0.5)
    current = st.sidebar.slider(t("current", lang), 0.1, 20.0, 1.0, 0.1)
    live_time = st.sidebar.slider(t("live_time", lang), 1.0, 600.0, 60.0, 1.0)

    elements: list[ElementSpec] = []
    layer = LayerConfig()

    if mode == "bulk":
        st.sidebar.header(t("composition", lang))
        st.sidebar.caption(t("composition_caption", lang))
        n_elem = st.sidebar.number_input(t("n_elements", lang), 1, 6, 2, 1)
        default_syms = ["Si", "Ti", "Fe", "Cu", "Au", "O"]
        default_conc = [99.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        for i in range(int(n_elem)):
            cols = st.sidebar.columns([2, 2])
            sym = cols[0].selectbox(
                t("element_n", lang, i=i + 1), COMMON_ELEMENTS,
                index=COMMON_ELEMENTS.index(default_syms[i]) if default_syms[i] in COMMON_ELEMENTS else 0,
                key=f"sym_{i}",
            )
            conc = cols[1].number_input(
                t("conc_n", lang, i=i + 1), 0.0, 100.0,
                float(default_conc[i]) if i < len(default_conc) else 1.0,
                0.1, key=f"conc_{i}",
            )
            elements.append(ElementSpec(symbol=sym, concentration=conc))
    else:
        st.sidebar.header(t("multilayer", lang))
        st.sidebar.caption(t("multilayer_caption", lang))
        n_layers = st.sidebar.number_input(t("n_layers", lang), 1, 5, 2, 1)
        default_layers = [("Au", 50.0), ("Ti", 10.0), ("TiN", 5.0),
                          ("SiO2", 3.0), ("C", 2.0)]
        layers: list[Layer] = []
        for i in range(int(n_layers)):
            d_comp, d_th = default_layers[i] if i < len(default_layers) else ("Au", 10.0)
            cols = st.sidebar.columns([2, 1, 1])
            comp = cols[0].text_input(t("layer_comp_n", lang, i=i + 1), d_comp,
                                      key=f"lay_comp_{i}")
            th = cols[1].number_input(
                t("layer_thick_n", lang, i=i + 1), 0.0, 2000.0, float(d_th), 1.0,
                key=f"lay_th_{i}",
            )
            dens = cols[2].number_input(
                t("layer_rho_n", lang, i=i + 1), 0.0, 25.0, 0.0, 0.1,
                key=f"lay_rho_{i}", help=t("density_help", lang),
            )
            layers.append(Layer(composition=comp.strip(), thickness_nm=th,
                                density=(dens if dens > 0 else None)))
        sc1, sc2 = st.sidebar.columns([2, 1])
        sub_comp = sc1.text_input(t("substrate_comp", lang), "Si", key="sub_comp")
        sub_rho = sc2.number_input(t("substrate_rho", lang), 0.0, 25.0, 0.0, 0.1,
                                   key="sub_rho", help=t("density_help", lang))
        takeoff = st.sidebar.slider(t("takeoff", lang), 10.0, 70.0, 35.0, 1.0)
        layer = LayerConfig(
            layers=layers, substrate_composition=sub_comp.strip(),
            substrate_density=(sub_rho if sub_rho > 0 else None),
            takeoff_deg=takeoff,
        )
        _validate_compositions(layer, lang)

    st.sidebar.header(t("detector", lang))
    apply_window = st.sidebar.checkbox(t("window_toggle", lang), value=True)
    window_um = st.sidebar.slider(t("window_thickness", lang), 0.0, 30.0, 8.0, 0.5,
                                  disabled=not apply_window)
    st.sidebar.caption(t("window_caption", lang))

    st.sidebar.header(t("display_random", lang))
    e_max = st.sidebar.slider(t("e_max", lang), 5.0, 30.0, 20.0, 1.0)
    fixed_seed = st.sidebar.checkbox(t("fixed_seed", lang), value=False)
    seed = 42 if fixed_seed else None

    return SimulationConfig(
        beam=BeamConditions(kv, current, live_time),
        elements=elements,
        detector=DetectorConfig(
            window_element="Be",
            window_thickness_um=window_um,
            apply_window_absorption=apply_window,
        ),
        axis=EnergyAxis(e_max_kev=e_max),
        mode=mode,
        layer=layer,
        random_seed=seed,
    )


def _validate_compositions(layer: LayerConfig, lang: str) -> None:
    """各層・基板の組成式を検証し、解釈結果を表示。誤りがあれば停止。"""
    problems: list[str] = []
    infos: list[str] = []
    nominal: list[str] = []

    def describe(label: str, formula: str, density) -> None:
        try:
            fr = parse_formula(formula)
            rho, src = resolve_density(formula, density)
            els = " ".join(f"{e} {w * 100:.0f}%" for e, w in fr.items())
            src_disp = density_source_label(src, lang)
            infos.append(f'{label} "{formula}" → {els} / ρ={rho:.2f} g/cm³ ({src_disp})')
            if src == "nominal":
                nominal.append(f'{label} "{formula}"')
        except Exception:  # noqa: BLE001 - ユーザ入力の検証
            problems.append(t("comp_parse_error", lang, label=label, formula=formula))

    for i, L in enumerate(layer.layers):
        describe(t("layer_label", lang, i=i + 1), L.composition, L.density)
    describe(t("layer_substrate", lang), layer.substrate_composition,
             layer.substrate_density)

    if problems:
        for p in problems:
            st.sidebar.error(p)
        st.sidebar.info(t("comp_error_hint", lang))
        st.stop()

    if nominal:
        st.sidebar.warning(
            t("density_nominal_warning", lang, items=" / ".join(nominal)),
            icon="⚠️",
        )

    with st.sidebar.expander(t("comp_check", lang), expanded=False):
        for s in infos:
            st.caption(s)


# --------------------------------------------------------------------------
# 描画
# --------------------------------------------------------------------------
def plot_spectrum(result: SpectrumResult, lang: str, show_theory: bool,
                  show_components: bool, log_y: bool) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=result.energy_kev, y=result.observed,
        mode="lines", name=t("trace_observed", lang),
        line=dict(color="#1f77b4", width=1.0),
    ))

    if show_theory:
        fig.add_trace(go.Scatter(
            x=result.energy_kev, y=result.theoretical,
            mode="lines", name=t("trace_theory", lang),
            line=dict(color="#d62728", width=1.6),
        ))

    if show_components:
        fig.add_trace(go.Scatter(
            x=result.energy_kev, y=result.continuum,
            mode="lines", name=t("trace_bg", lang),
            line=dict(color="#7f7f7f", width=1.0, dash="dot"),
        ))

    # ピーク注釈（主要ラインのみラベル表示、層で色分け）
    for p in _top_peaks(result, limit=8):
        idx = int(np.argmin(np.abs(result.energy_kev - p.energy_kev)))
        y_at = result.theoretical[idx] if show_theory else result.observed[idx]
        color = _layer_color(p.layer_order, p.layer)
        disp = _layer_display(p, lang)
        tag = f" ({disp})" if disp else ""
        fig.add_annotation(
            x=p.energy_kev, y=y_at,
            text=f"{p.symbol} {p.name}{tag}",
            showarrow=True, arrowhead=2, arrowsize=0.7,
            ax=0, ay=-30, font=dict(size=10, color=color),
            arrowcolor=color,
        )

    fig.update_layout(
        xaxis_title=t("axis_energy", lang),
        yaxis_title=t("axis_counts", lang),
        yaxis_type="log" if log_y else "linear",
        height=520,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=20, t=40, b=50),
    )
    if log_y:
        fig.update_yaxes(rangemode="tozero")
    return fig


def _peak_net(result: SpectrumResult, p) -> float:
    """ピーク位置チャネルの特性X線ネット強度（窓吸収後）。"""
    idx = int(np.argmin(np.abs(result.energy_kev - p.energy_kev)))
    return float(result.characteristic[idx])


def _top_peaks(result: SpectrumResult, limit: int):
    """実測ネット強度（窓吸収後）の大きい順に上位ピークを返す。"""
    return sorted(result.peaks, key=lambda p: _peak_net(result, p),
                  reverse=True)[:limit]


# 層の深さ順に割り当てる色（0=最表面 → 基板は最後）
_LAYER_PALETTE = ["#2ca02c", "#ff7f0e", "#17becf", "#e377c2", "#bcbd22"]
_SUBSTRATE_COLOR = "#9467bd"


def _layer_color(layer_order: int, layer_token: str) -> str:
    if layer_token == "substrate":
        return _SUBSTRATE_COLOR
    if layer_token == "film":
        return _LAYER_PALETTE[layer_order % len(_LAYER_PALETTE)]
    return "#333333"  # bulk


def _layer_display(p, lang: str) -> str:
    """ピークの層ラベルを言語に合わせて整形（bulk は空）。"""
    if p.layer == "substrate":
        return t("layer_substrate", lang)
    if p.layer == "film":
        return t("layer_film", lang, i=p.layer_order + 1)
    return ""


# --------------------------------------------------------------------------
# メイン
# --------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(
        page_title="EDS Spectrum Simulator",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    lang = language_selector()

    st.title(t("app_title", lang))
    st.caption(t("app_subtitle", lang))

    if not xraylib_available():
        st.warning(t("xraylib_warning", lang), icon="⚠️")

    cfg = build_sidebar(lang)

    col_plot, col_info = st.columns([3, 1])

    with col_plot:
        show_theory = st.checkbox(t("overlay_theory", lang), value=True)
        c1, c2 = st.columns(2)
        show_components = c1.checkbox(t("show_bg", lang), value=True)
        log_y = c2.checkbox(t("log_y", lang), value=False)

        result = simulate(cfg)
        fig = plot_spectrum(result, lang, show_theory, show_components, log_y)
        st.plotly_chart(fig, width="stretch")

    with col_info:
        st.subheader(t("counting_stats", lang))
        st.metric(t("max_counts", lang), f"{result.max_counts:,.0f}")
        bg_level = float(np.median(result.continuum[result.continuum > 0]) or 1.0)
        st.metric(t("bg_level", lang), f"{bg_level:,.1f}")
        st.metric(t("bg_noise", lang), f"{np.sqrt(max(bg_level, 0.0)):,.1f}")

        if cfg.mode == "thin_film":
            st.divider()
            st.subheader(t("layer_signals", lang))
            st.caption(t("layer_signals_caption", lang))
            _layer_summary(result, lang)

        st.divider()
        st.subheader(t("peak_detectability", lang))
        st.caption(t("peak_detectability_caption", lang))
        _peak_table(result, lang, layered=(cfg.mode == "thin_film"))

    with st.expander(t("limits_title", lang), expanded=False):
        st.markdown(t("limits_md", lang))


def _peak_table(result: SpectrumResult, lang: str, layered: bool = False) -> None:
    """主要ピークの簡易 S/N テーブルを表示。"""
    energy = result.energy_kev
    rows = []
    for p in _top_peaks(result, limit=8):
        idx = int(np.argmin(np.abs(energy - p.energy_kev)))
        bg = float(result.continuum[idx])
        net = float(result.characteristic[idx])
        noise = np.sqrt(max(2.0 * bg, 1.0))  # BG のポアソン揺らぎ（±方向）
        snr = net / noise if noise > 0 else 0.0
        row = {
            t("col_line", lang): f"{p.symbol} {p.name}",
            t("col_energy", lang): round(p.energy_kev, 3),
            t("col_snr", lang): round(snr, 1),
        }
        if layered:
            row[t("col_layer", lang)] = _layer_display(p, lang)
        rows.append(row)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info(t("no_peaks", lang))


def _layer_summary(result: SpectrumResult, lang: str) -> None:
    """層ごとに最強ラインのネット強度をまとめて表示。"""
    by_layer: dict[int, object] = {}
    for p in result.peaks:
        cur = by_layer.get(p.layer_order)
        if cur is None or _peak_net(result, p) > _peak_net(result, cur):
            by_layer[p.layer_order] = p
    rows = []
    for order in sorted(by_layer):
        p = by_layer[order]
        rows.append({
            t("col_layer", lang): _layer_display(p, lang),
            t("col_rep_line", lang): f"{p.symbol} {p.name}",
            t("col_net", lang): round(_peak_net(result, p), 1),
        })
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")


if __name__ == "__main__":
    main()
