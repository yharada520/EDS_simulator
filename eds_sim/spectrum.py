"""スペクトル合成: 制動X線＋特性X線ピーク → 検出器応答 → ポアソンノイズ。"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import SimulationConfig, ElementSpec
from .continuum import kramers_continuum
from .characteristic import build_peaks, build_peaks_layered, PeakInfo
from .composition import parse_formula
from .detector import detector_response


def _thin_film_bg_elements(cfg: SimulationConfig) -> list[ElementSpec]:
    """薄膜モードの制動X線用に、全層＋基板の元素を重み付きで集約する。

    各層元素は（膜厚 × 質量分率）、基板元素は代表重みで重み付け。
    平均原子番号の算出にのみ用いる。
    """
    out: list[ElementSpec] = []
    for L in cfg.layer.layers:
        try:
            fr = parse_formula(L.composition)
        except ValueError:
            continue
        for el, w in fr.items():
            out.append(ElementSpec(el, w * max(L.thickness_nm, 0.0)))
    try:
        for el, w in parse_formula(cfg.layer.substrate_composition).items():
            out.append(ElementSpec(el, w * 100.0))
    except ValueError:
        pass
    return out


@dataclass
class SpectrumResult:
    """シミュレーション結果一式。"""

    energy_kev: np.ndarray            # エネルギー軸 [keV]
    theoretical: np.ndarray           # 理論スペクトル [counts]（ノイズ無し）
    observed: np.ndarray              # 観測スペクトル [counts]（ポアソン重畳）
    continuum: np.ndarray             # 制動X線成分 [counts]
    characteristic: np.ndarray        # 特性X線成分 [counts]
    peaks: list[PeakInfo] = field(default_factory=list)  # ピーク一覧（注釈用）

    @property
    def max_counts(self) -> float:
        return float(self.observed.max()) if self.observed.size else 0.0


def make_energy_axis(cfg: SimulationConfig) -> np.ndarray:
    """設定からエネルギー軸 [keV] を生成。"""
    ax = cfg.axis
    e_max = min(ax.e_max_kev, cfg.beam.accel_voltage_kv)  # E0 を超える領域は無意味
    e_max = max(e_max, ax.e_min_kev + 1.0e-3)
    return np.linspace(ax.e_min_kev, e_max, ax.n_channels)


def simulate(cfg: SimulationConfig) -> SpectrumResult:
    """設定に基づき EDS スペクトルをシミュレートする。

    フロー:
        1. 制動X線（Kramers）＋特性X線（Gaussian）で理論相対スペクトルを生成
        2. 検出器窓の透過率を乗算（低エネルギー減衰）
        3. 最強ピーク位置で P/B を peak_to_background に合わせて制動X線を正規化
        4. 最強ピーク高さ = intensity_scale × 線量 となるよう実測カウントにスケール
        5. numpy.random.poisson でショットノイズを重畳
    """
    energy = make_energy_axis(cfg)
    e0_ev = cfg.beam.e0_ev

    # --- 1. 相対強度スペクトル -------------------------------------------
    if cfg.mode == "thin_film":
        continuum_rel = kramers_continuum(
            energy, e0_ev, _thin_film_bg_elements(cfg))
        char_rel, peaks = build_peaks_layered(energy, cfg)
    else:
        continuum_rel = kramers_continuum(energy, e0_ev, cfg.elements)
        char_rel, peaks = build_peaks(energy, cfg)

    # --- 2. 検出器応答（窓吸収など） -------------------------------------
    response = detector_response(energy, cfg.detector)
    continuum_rel = continuum_rel * response
    char_rel = char_rel * response

    # --- 3. P/B 正規化: 最強ピーク直下の制動X線を peak_height/pb に合わせる ---
    if char_rel.size and char_rel.max() > 0.0:
        i_peak = int(np.argmax(char_rel))
        p_ref = float(char_rel[i_peak])          # 最強ピークのチャネル高さ
        b_at = float(continuum_rel[i_peak])      # その直下の制動X線高さ
        if b_at > 0.0:
            target_bg = p_ref / max(cfg.peak_to_background, 1.0e-6)
            continuum_rel = continuum_rel * (target_bg / b_at)
        norm_ref = p_ref
    else:
        # 特性ピーク不在時は制動X線の最大で正規化
        norm_ref = float(continuum_rel.max()) or 1.0

    # --- 4. カウントへのスケール（Max カウント = intensity_scale × 線量） ---
    dose = max(cfg.beam.probe_current, 0.0) * max(cfg.beam.live_time_s, 0.0)
    factor = (cfg.intensity_scale * dose) / norm_ref if norm_ref > 0.0 else 0.0

    continuum_counts = continuum_rel * factor
    char_counts = char_rel * factor
    theoretical = continuum_counts + char_counts

    # --- 5. ポアソンノイズ重畳 -------------------------------------------
    rng = np.random.default_rng(cfg.random_seed)
    lam = np.clip(theoretical, 0.0, None)
    observed = rng.poisson(lam).astype(float)

    # 各ピークの実測カウント（注釈用: ピーク位置チャネルの観測値）
    for p in peaks:
        idx = int(np.argmin(np.abs(energy - p.energy_kev)))
        p.observed_at_peak = float(observed[idx])

    return SpectrumResult(
        energy_kev=energy,
        theoretical=theoretical,
        observed=observed,
        continuum=continuum_counts,
        characteristic=char_counts,
        peaks=peaks,
    )
