"""EDS スペクトル・シミュレータ（Streamlit UI）。

フェーズ1（計数統計）＋フェーズ2（xraylib 連携）＋フェーズ3（薄膜/基板）統合版。

計数統計（ポアソン分布）と検出器窓吸収を可視化し、
「不十分な測定条件で微量ピークが統計ノイズ(√N)に埋もれる」現象や
「加速電圧・線量の適正化」、および「基板上の極薄膜で加速電圧を下げると
基板シグナルが減り薄膜 S/N が相対向上する」挙動を直感的に理解するための
教育・R&D 用ツール。
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

logging.basicConfig(level=logging.INFO)

# よく使う元素（プリセット）
COMMON_ELEMENTS = ["C", "O", "Al", "Si", "Ti", "Cr", "Fe", "Ni", "Cu", "Zn",
                   "Ga", "Mo", "Ag", "Ta", "W", "Pt", "Au"]


# --------------------------------------------------------------------------
# サイドバー: 入力 UI
# --------------------------------------------------------------------------
def build_sidebar() -> SimulationConfig:
    st.sidebar.header("試料モデル")
    mode_label = st.sidebar.radio(
        "モード", ["均質バルク（統計）", "薄膜／基板（多層）"],
        help="均質バルク=フェーズ1/2（計数統計）。薄膜/基板=フェーズ3（φ(ρz)深さモデル）。",
    )
    mode = "thin_film" if mode_label.startswith("薄膜") else "bulk"

    st.sidebar.header("測定条件")
    kv = st.sidebar.slider("加速電圧 [kV]", 1.0, 30.0, 15.0, 0.5)
    current = st.sidebar.slider("プローブ電流 [任意単位]", 0.1, 20.0, 1.0, 0.1)
    live_time = st.sidebar.slider("積算時間 [s]", 1.0, 600.0, 60.0, 1.0)

    elements: list[ElementSpec] = []
    layer = LayerConfig()

    if mode == "bulk":
        st.sidebar.header("試料組成")
        st.sidebar.caption("主成分と微量元素を指定（濃度は質量% 相当）")
        n_elem = st.sidebar.number_input("元素数", 1, 6, 2, 1)
        default_syms = ["Si", "Ti", "Fe", "Cu", "Au", "O"]
        default_conc = [99.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        for i in range(int(n_elem)):
            cols = st.sidebar.columns([2, 2])
            sym = cols[0].selectbox(
                f"元素 {i + 1}", COMMON_ELEMENTS,
                index=COMMON_ELEMENTS.index(default_syms[i]) if default_syms[i] in COMMON_ELEMENTS else 0,
                key=f"sym_{i}",
            )
            conc = cols[1].number_input(
                f"濃度% {i + 1}", 0.0, 100.0,
                float(default_conc[i]) if i < len(default_conc) else 1.0,
                0.1, key=f"conc_{i}",
            )
            elements.append(ElementSpec(symbol=sym, concentration=conc))
    else:
        st.sidebar.header("多層構造")
        st.sidebar.caption(
            "表面から順に層を積む（層1 = 最表面/付着物、下ほど基板側）。"
            "組成は化学式で指定（例: Ti, TiN, TiO2, Al2O3, SiO2）。"
            "密度 0 で自動（プリセット/推定）。埋もれた層ほど上層に吸収され見えにくい。"
        )
        n_layers = st.sidebar.number_input("層数（基板を除く）", 1, 5, 2, 1)
        default_layers = [("Au", 50.0), ("Ti", 10.0), ("TiN", 5.0),
                          ("SiO2", 3.0), ("C", 2.0)]
        layers: list[Layer] = []
        for i in range(int(n_layers)):
            d_comp, d_th = default_layers[i] if i < len(default_layers) else ("Au", 10.0)
            cols = st.sidebar.columns([2, 1, 1])
            comp = cols[0].text_input(f"層{i + 1} 組成", d_comp, key=f"lay_comp_{i}")
            th = cols[1].number_input(
                f"層{i + 1} 厚[nm]", 0.0, 2000.0, float(d_th), 1.0, key=f"lay_th_{i}",
            )
            dens = cols[2].number_input(
                f"層{i + 1} ρ", 0.0, 25.0, 0.0, 0.1, key=f"lay_rho_{i}",
                help="密度[g/cm³]。0 で自動決定。",
            )
            layers.append(Layer(composition=comp.strip(), thickness_nm=th,
                                density=(dens if dens > 0 else None)))
        sc1, sc2 = st.sidebar.columns([2, 1])
        sub_comp = sc1.text_input("基板 組成", "Si", key="sub_comp")
        sub_rho = sc2.number_input("基板 ρ", 0.0, 25.0, 0.0, 0.1, key="sub_rho",
                                   help="密度[g/cm³]。0 で自動決定。")
        takeoff = st.sidebar.slider("X線取り出し角 [deg]", 10.0, 70.0, 35.0, 1.0)
        layer = LayerConfig(
            layers=layers, substrate_composition=sub_comp.strip(),
            substrate_density=(sub_rho if sub_rho > 0 else None),
            takeoff_deg=takeoff,
        )
        _validate_compositions(layer)

    st.sidebar.header("検出器")
    apply_window = st.sidebar.checkbox("窓吸収 (Be) を考慮", value=True)
    window_um = st.sidebar.slider("Be 窓厚 [µm]", 0.0, 30.0, 8.0, 0.5,
                                  disabled=not apply_window)
    st.sidebar.caption(
        "参考: 従来型 Be 窓は 5〜8 µm（軽元素 C/N/O を強く吸収）。"
        "超薄ポリマー窓や窓レス機は軽元素検出に有利。厚いほど低エネルギー側が減衰。"
    )

    st.sidebar.header("表示・乱数")
    e_max = st.sidebar.slider("表示上限エネルギー [keV]", 5.0, 30.0, 20.0, 1.0)
    fixed_seed = st.sidebar.checkbox("乱数シード固定（再現用）", value=False)
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


def _validate_compositions(layer: LayerConfig) -> None:
    """各層・基板の組成式を検証し、解釈結果を表示。誤りがあれば停止。"""
    problems: list[str] = []
    infos: list[str] = []
    nominal: list[str] = []

    def describe(label: str, formula: str, density) -> None:
        try:
            fr = parse_formula(formula)
            rho, src = resolve_density(formula, density)
            els = " ".join(f"{e} {w * 100:.0f}%" for e, w in fr.items())
            infos.append(f"{label}「{formula}」→ {els} / ρ={rho:.2f} g/cm³（{src}）")
            if src.startswith("既定"):
                nominal.append(f"{label}「{formula}」")
        except Exception as exc:  # noqa: BLE001 - ユーザ入力の検証
            problems.append(f"{label}「{formula}」: {exc}")

    for i, L in enumerate(layer.layers):
        describe(f"層{i + 1}", L.composition, L.density)
    describe("基板", layer.substrate_composition, layer.substrate_density)

    if problems:
        for p in problems:
            st.sidebar.error(p)
        st.sidebar.info("組成式は単純な化学式のみ対応（括弧なし）。例: TiO2, Al2O3")
        st.stop()

    if nominal:
        st.sidebar.warning(
            "密度が未知のため仮の既定値を使用: " + " / ".join(nominal)
            + "。膜厚→質量深さ変換に効くため、正確な密度[g/cm³]の手入力を推奨。",
            icon="⚠️",
        )

    with st.sidebar.expander("組成の確認（解釈結果）", expanded=False):
        for s in infos:
            st.caption(s)


# --------------------------------------------------------------------------
# 描画
# --------------------------------------------------------------------------
def plot_spectrum(result: SpectrumResult, show_theory: bool,
                  show_components: bool, log_y: bool) -> go.Figure:
    fig = go.Figure()

    # 観測スペクトル（ポアソンノイズ込み）
    fig.add_trace(go.Scatter(
        x=result.energy_kev, y=result.observed,
        mode="lines", name="観測 (Poisson)",
        line=dict(color="#1f77b4", width=1.0),
    ))

    if show_theory:
        fig.add_trace(go.Scatter(
            x=result.energy_kev, y=result.theoretical,
            mode="lines", name="理論 (ノイズ無)",
            line=dict(color="#d62728", width=1.6),
        ))

    if show_components:
        fig.add_trace(go.Scatter(
            x=result.energy_kev, y=result.continuum,
            mode="lines", name="制動X線 (BG)",
            line=dict(color="#7f7f7f", width=1.0, dash="dot"),
        ))

    # ピーク注釈（主要ラインのみラベル表示、層で色分け）
    for p in _top_peaks(result, limit=8):
        idx = int(np.argmin(np.abs(result.energy_kev - p.energy_kev)))
        y_at = result.theoretical[idx] if show_theory else result.observed[idx]
        color = _layer_color(p.layer_order, p.layer)
        tag = "" if p.layer == "bulk" else f" ({p.layer})"
        fig.add_annotation(
            x=p.energy_kev, y=y_at,
            text=f"{p.symbol} {p.name}{tag}",
            showarrow=True, arrowhead=2, arrowsize=0.7,
            ax=0, ay=-30, font=dict(size=10, color=color),
            arrowcolor=color,
        )

    fig.update_layout(
        xaxis_title="X線エネルギー [keV]",
        yaxis_title="カウント",
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
    """実測ネット強度（窓吸収後）の大きい順に上位ピークを返す。

    rel_weight（窓吸収前の生強度）ではなく実際に見えるネット強度で
    並べることで、低エネルギー側の吸収されたラインを過大評価しない。
    """
    return sorted(result.peaks, key=lambda p: _peak_net(result, p),
                  reverse=True)[:limit]


# --------------------------------------------------------------------------
# メイン
# --------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(
        page_title="EDS スペクトル・シミュレータ",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("EDS スペクトル・シミュレータ")
    st.caption(
        "計数統計（ポアソンノイズ）と検出器応答の可視化 — "
        "微量ピークが √N ノイズに埋もれる現象を体験する"
    )

    if not xraylib_available():
        st.warning(
            "xraylib を検出できませんでした。内蔵の簡易テーブルで動作します"
            "（フェーズ2の精度は限定的）。conda-forge から xraylib を導入してください。",
            icon="⚠️",
        )

    cfg = build_sidebar()

    col_plot, col_info = st.columns([3, 1])

    with col_plot:
        show_theory = st.checkbox("理論スペクトルを重ねる", value=True)
        c1, c2 = st.columns(2)
        show_components = c1.checkbox("制動X線(BG)を表示", value=True)
        log_y = c2.checkbox("Y軸 対数表示", value=False)

        result = simulate(cfg)
        fig = plot_spectrum(result, show_theory, show_components, log_y)
        st.plotly_chart(fig, width="stretch")

    with col_info:
        st.subheader("計数統計")
        max_counts = result.max_counts
        st.metric("Max カウント", f"{max_counts:,.0f}")
        # バックグラウンドの代表 S/N（√N 目安）
        bg_level = float(np.median(result.continuum[result.continuum > 0]) or 1.0)
        st.metric("BG レベル(中央値)", f"{bg_level:,.1f}")
        st.metric("BG ノイズ √N", f"{np.sqrt(max(bg_level, 0.0)):,.1f}")

        if cfg.mode == "thin_film":
            st.divider()
            st.subheader("層別シグナル")
            st.caption("各層の最強ラインのネット強度（上層に吸収されるほど小）")
            _layer_summary(result)

        st.divider()
        st.subheader("ピーク検出性")
        st.caption("ネット強度 / √(2·BG) を簡易 S/N とする")
        _peak_table(result, layered=(cfg.mode == "thin_film"))

    with st.expander("このツールの前提と限界", expanded=False):
        st.markdown(
            "- 制動X線は **Kramers 近似**、特性X線は **xraylib のライン"
            "エネルギー・遷移確率** に基づく。\n"
            "- 検出器分解能は **Fano 統計の標準式**（Mn Kα 130 eV を基準に較正）。\n"
            "- 検出器窓吸収は **Be 窓の質量減衰係数** による低エネルギー減衰。\n"
            "- ピーク/バックグラウンド比・絶対カウントは可視化向けの**経験較正**"
            "であり第一原理の定量値ではない（`peak_to_background` / `intensity_scale`）。\n"
            "- 多層モードの φ(ρz) は **Packwood-Brown 型**、深さスケールは "
            "**Kanaya-Okayama 電子飛程**に固定。各層の放出X線は上側の全層の"
            "質量厚×質量吸収係数で減衰させる。**電子散乱マトリクスは基板組成で近似**"
            "しているため、厚い重元素の最上層（例: 数百 nm の Au）では"
            "電子の減速を過小評価しうる。多殻元素の殻間相対強度は RadRate のみ。"
        )


def _peak_table(result: SpectrumResult, layered: bool = False) -> None:
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
            "ライン": f"{p.symbol} {p.name}",
            "E[keV]": round(p.energy_kev, 3),
            "S/N": round(snr, 1),
        }
        if layered:
            row["層"] = p.layer
        rows.append(row)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info("表示レンジ内に励起可能なピークがありません。")


# 層の深さ順に割り当てる色（0=最表面 → 基板は最後）
_LAYER_PALETTE = ["#2ca02c", "#ff7f0e", "#17becf", "#e377c2", "#bcbd22"]
_SUBSTRATE_COLOR = "#9467bd"


def _layer_color(layer_order: int, layer_label: str) -> str:
    if layer_label == "bulk":
        return "#333333"
    if layer_label == "基板":
        return _SUBSTRATE_COLOR
    return _LAYER_PALETTE[layer_order % len(_LAYER_PALETTE)]


def _layer_summary(result: SpectrumResult) -> None:
    """層ごとに最強ラインのネット強度をまとめて表示。"""
    # layer_order ごとに最強ネットのピークを集計
    by_layer: dict[int, object] = {}
    for p in result.peaks:
        cur = by_layer.get(p.layer_order)
        if cur is None or _peak_net(result, p) > _peak_net(result, cur):
            by_layer[p.layer_order] = p
    rows = []
    for order in sorted(by_layer):
        p = by_layer[order]
        rows.append({
            "層": p.layer,
            "代表ライン": f"{p.symbol} {p.name}",
            "ネット": round(_peak_net(result, p), 1),
        })
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")


if __name__ == "__main__":
    main()
