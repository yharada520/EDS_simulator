"""UI 文字列の日本語/英語対訳。

`t(key, lang, **kw)` で取得し、必要なら `.format(**kw)` で埋め込む。
物理演算 (eds_sim) は言語非依存に保ち、翻訳は UI 層のみで行う。
"""

from __future__ import annotations

# 表示名 -> 言語コード（先頭がセレクタの初期値＝既定言語）
LANGUAGES: dict[str, str] = {"English": "en", "日本語": "ja"}
DEFAULT_LANG = "en"

TR: dict[str, dict[str, str]] = {
    # --- 言語・ページ全体 ---
    "language": {"ja": "言語 / Language", "en": "言語 / Language"},
    "app_title": {"ja": "EDS スペクトル・シミュレータ",
                  "en": "EDS Spectrum Simulator"},
    "app_subtitle": {
        "ja": "計数統計（ポアソンノイズ）と検出器応答の可視化 — 微量ピークが √N ノイズに埋もれる現象を体験する",
        "en": "Counting statistics (Poisson noise) and detector response — see how a trace peak drowns in √N noise",
    },
    "xraylib_warning": {
        "ja": "xraylib を検出できませんでした。内蔵の簡易テーブルで動作します（フェーズ2/3の精度は限定的）。pip / conda-forge から xraylib を導入してください。",
        "en": "xraylib not found; running on a small built-in fallback table (limited Phase 2/3 accuracy). Install xraylib via pip or conda-forge.",
    },

    # --- 表示トグル ---
    "overlay_theory": {"ja": "理論スペクトルを重ねる",
                       "en": "Overlay theoretical spectrum"},
    "show_bg": {"ja": "制動X線(BG)を表示", "en": "Show bremsstrahlung (BG)"},
    "log_y": {"ja": "Y軸 対数表示", "en": "Log Y axis"},

    # --- サイドバー: モード ---
    "sample_model": {"ja": "試料モデル", "en": "Sample model"},
    "mode": {"ja": "モード", "en": "Mode"},
    "mode_bulk": {"ja": "均質バルク（統計）",
                  "en": "Homogeneous bulk (statistics)"},
    "mode_film": {"ja": "薄膜／基板（多層）",
                  "en": "Thin film / substrate (multilayer)"},
    "mode_help": {
        "ja": "均質バルク=フェーズ1/2（計数統計）。薄膜/基板=フェーズ3（φ(ρz)深さモデル）。",
        "en": "Bulk = Phase 1/2 (counting statistics). Thin film = Phase 3 (φ(ρz) depth model).",
    },

    # --- 測定条件 ---
    "conditions": {"ja": "測定条件", "en": "Measurement conditions"},
    "kv": {"ja": "加速電圧 [kV]", "en": "Accelerating voltage [kV]"},
    "current": {"ja": "プローブ電流 [任意単位]", "en": "Probe current [a.u.]"},
    "live_time": {"ja": "積算時間 [s]", "en": "Live time [s]"},

    # --- バルク組成 ---
    "composition": {"ja": "試料組成", "en": "Composition"},
    "composition_caption": {
        "ja": "主成分と微量元素を指定（濃度は質量% 相当）",
        "en": "Set major and trace elements (concentration ≈ mass %)",
    },
    "n_elements": {"ja": "元素数", "en": "Number of elements"},
    "element_n": {"ja": "元素 {i}", "en": "Element {i}"},
    "conc_n": {"ja": "濃度% {i}", "en": "Conc. % {i}"},

    # --- 多層 ---
    "multilayer": {"ja": "多層構造", "en": "Multilayer stack"},
    "multilayer_caption": {
        "ja": "表面から順に層を積む（層1 = 最表面/付着物、下ほど基板側）。組成は化学式で指定（例: Ti, TiN, TiO2, Al2O3, SiO2）。密度 0 で自動（プリセット/推定）。埋もれた層ほど上層に吸収され見えにくい。",
        "en": "Stack layers from the surface down (layer 1 = topmost / contamination). Composition as a chemical formula (e.g. Ti, TiN, TiO2, Al2O3, SiO2). Density 0 = auto (preset/estimate). Buried layers are absorbed by those above.",
    },
    "n_layers": {"ja": "層数（基板を除く）",
                 "en": "Number of layers (excl. substrate)"},
    "layer_comp_n": {"ja": "層{i} 組成", "en": "Layer {i} formula"},
    "layer_thick_n": {"ja": "層{i} 厚[nm]", "en": "Layer {i} nm"},
    "layer_rho_n": {"ja": "層{i} ρ", "en": "Layer {i} ρ"},
    "density_help": {"ja": "密度[g/cm³]。0 で自動決定。",
                     "en": "Density [g/cm³]. 0 = auto."},
    "substrate_comp": {"ja": "基板 組成", "en": "Substrate formula"},
    "substrate_rho": {"ja": "基板 ρ", "en": "Substrate ρ"},
    "takeoff": {"ja": "X線取り出し角 [deg]", "en": "X-ray take-off angle [deg]"},

    # --- 組成検証 ---
    "comp_check": {"ja": "組成の確認（解釈結果）", "en": "Parsed compositions"},
    "comp_error_hint": {
        "ja": "組成式は単純な化学式のみ対応（括弧なし）。例: TiO2, Al2O3",
        "en": "Only simple formulas are supported (no parentheses). e.g. TiO2, Al2O3",
    },
    "comp_parse_error": {"ja": "{label}「{formula}」: 組成式を解釈できません",
                         "en": "{label} \"{formula}\": cannot parse formula"},
    "density_nominal_warning": {
        "ja": "密度が未知のため仮の既定値を使用: {items}。膜厚→質量深さ変換に効くため、正確な密度[g/cm³]の手入力を推奨。",
        "en": "Density unknown; using a nominal default for {items}. It affects the thickness→mass-depth conversion, so entering the real density [g/cm³] is recommended.",
    },
    "layer_label": {"ja": "層{i}", "en": "Layer {i}"},
    # 密度出所トークン (composition.resolve_density) の表示名
    "src_specified": {"ja": "指定", "en": "specified"},
    "src_preset": {"ja": "プリセット", "en": "preset"},
    "src_element": {"ja": "元素", "en": "element"},
    "src_nominal": {"ja": "既定(要手入力)", "en": "nominal (enter manually)"},

    # --- 検出器 ---
    "detector": {"ja": "検出器", "en": "Detector"},
    "window_toggle": {"ja": "窓吸収 (Be) を考慮",
                      "en": "Apply window absorption (Be)"},
    "window_thickness": {"ja": "Be 窓厚 [µm]", "en": "Be window thickness [µm]"},
    "window_caption": {
        "ja": "参考: 従来型 Be 窓は 5〜8 µm（軽元素 C/N/O を強く吸収）。超薄ポリマー窓や窓レス機は軽元素検出に有利。厚いほど低エネルギー側が減衰。",
        "en": "Note: conventional Be windows are 5–8 µm (strongly absorb light elements C/N/O). Ultra-thin polymer or windowless detectors favor light-element detection. Thicker = more low-energy attenuation.",
    },

    # --- 表示・乱数 ---
    "display_random": {"ja": "表示・乱数", "en": "Display & random"},
    "e_max": {"ja": "表示上限エネルギー [keV]",
              "en": "Max displayed energy [keV]"},
    "fixed_seed": {"ja": "乱数シード固定（再現用）",
                   "en": "Fix random seed (reproducible)"},

    # --- 情報パネル ---
    "counting_stats": {"ja": "計数統計", "en": "Counting statistics"},
    "max_counts": {"ja": "Max カウント", "en": "Max counts"},
    "bg_level": {"ja": "BG レベル(中央値)", "en": "BG level (median)"},
    "bg_noise": {"ja": "BG ノイズ √N", "en": "BG noise √N"},
    "layer_signals": {"ja": "層別シグナル", "en": "Signal by layer"},
    "layer_signals_caption": {
        "ja": "各層の最強ラインのネット強度（上層に吸収されるほど小）",
        "en": "Net intensity of each layer's strongest line (smaller = more absorbed by layers above)",
    },
    "peak_detectability": {"ja": "ピーク検出性", "en": "Peak detectability"},
    "peak_detectability_caption": {
        "ja": "ネット強度 / √(2·BG) を簡易 S/N とする",
        "en": "Simple S/N = net intensity / √(2·BG)",
    },
    "no_peaks": {"ja": "表示レンジ内に励起可能なピークがありません。",
                 "en": "No excitable peaks in the displayed range."},

    # --- 凡例・軸（プロット） ---
    "trace_observed": {"ja": "観測 (Poisson)", "en": "Observed (Poisson)"},
    "trace_theory": {"ja": "理論 (ノイズ無)", "en": "Theoretical (no noise)"},
    "trace_bg": {"ja": "制動X線 (BG)", "en": "Bremsstrahlung (BG)"},
    "axis_energy": {"ja": "X線エネルギー [keV]", "en": "X-ray energy [keV]"},
    "axis_counts": {"ja": "カウント", "en": "Counts"},

    # --- テーブル列 ---
    "col_line": {"ja": "ライン", "en": "Line"},
    "col_energy": {"ja": "E[keV]", "en": "E [keV]"},
    "col_snr": {"ja": "S/N", "en": "S/N"},
    "col_layer": {"ja": "層", "en": "Layer"},
    "col_rep_line": {"ja": "代表ライン", "en": "Line"},
    "col_net": {"ja": "ネット", "en": "Net"},

    # --- 層ラベル（プロット注釈・テーブル） ---
    "layer_film": {"ja": "膜{i}", "en": "Film {i}"},
    "layer_substrate": {"ja": "基板", "en": "Substrate"},

    # --- 限界の注記（expander） ---
    "limits_title": {"ja": "このツールの前提と限界",
                     "en": "Assumptions & limitations"},
    "limits_md": {
        "ja": (
            "- 制動X線は **Kramers 近似**、特性X線は **xraylib のライン"
            "エネルギー**。相対強度は **電子衝突電離（Bethe形）×蛍光収率×遷移確率** で、"
            "多殻元素（Au の M/L 等）の過電圧依存の殻間比を再現する。\n"
            "- 検出器分解能は **Fano 統計の標準式**（Mn Kα 130 eV を基準に較正）。\n"
            "- 検出器窓吸収は **Be 窓の質量減衰係数** による低エネルギー減衰。\n"
            "- ピーク/バックグラウンド比・絶対カウントは可視化向けの**経験較正**"
            "であり第一原理の定量値ではない（`peak_to_background` / `intensity_scale`）。\n"
            "- 多層モードの φ(ρz) は **Packwood-Brown 型**、深さスケールは "
            "**Kanaya-Okayama 電子飛程**に固定。各層の放出X線は上側の全層の"
            "質量厚×質量吸収係数で減衰させる。**電子散乱マトリクスは基板組成で近似**"
            "しているため、厚い重元素の最上層（例: 数百 nm の Au）では"
            "電子の減速を過小評価しうる。\n"
            "- 化合物の組成は**単純な化学式のみ**（括弧なし）。密度はプリセット表・単一元素は"
            "自動、それ以外は仮の既定値（要手入力）。"
        ),
        "en": (
            "- Bremsstrahlung uses the **Kramers approximation**; characteristic lines use "
            "**xraylib line energies**. Intensities use **electron-impact ionization "
            "(Bethe) × fluorescence yield × radiative rate**, reproducing the "
            "overvoltage-dependent shell ratios of multi-shell elements (e.g. Au M vs L).\n"
            "- Detector resolution follows the standard **Fano-statistics** formula "
            "(calibrated to 130 eV at Mn Kα).\n"
            "- Window absorption is the low-energy attenuation of a **Be window** via mass "
            "attenuation coefficients.\n"
            "- Peak-to-background ratio and absolute counts are an **empirical calibration** "
            "for visualization, not first-principles values (`peak_to_background` / "
            "`intensity_scale`).\n"
            "- The multilayer φ(ρz) is **Packwood-Brown**, with the depth scale anchored to "
            "the **Kanaya-Okayama** electron range. Each layer's emission is attenuated by "
            "the mass thickness × MAC of all overlying layers. The **electron-scattering "
            "matrix is approximated by the substrate composition**, so a thick heavy top "
            "layer (e.g. hundreds of nm of Au) underestimates electron slowing-down.\n"
            "- Compound formulas are **simple only** (no parentheses). Density is automatic "
            "for presets and single elements, otherwise a nominal default (enter manually)."
        ),
    },
}

# よく使う元素（プリセット）は言語非依存
COMMON_ELEMENTS = ["C", "O", "Al", "Si", "Ti", "Cr", "Fe", "Ni", "Cu", "Zn",
                   "Ga", "Mo", "Ag", "Ta", "W", "Pt", "Au"]


def t(key: str, lang: str, **kwargs) -> str:
    """翻訳文字列を取得（欠落時は key を返す）。kwargs があれば format する。"""
    entry = TR.get(key)
    if entry is None:
        return key
    text = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    return text.format(**kwargs) if kwargs else text


def density_source_label(src: str, lang: str) -> str:
    """密度出所トークン (specified/preset/element/nominal) を表示名に。"""
    return t(f"src_{src}", lang)
