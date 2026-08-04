"""特性X線ピークの生成（xraylib 連携 → エネルギー依存 Gaussian）。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import SimulationConfig
from .detector import fwhm_ev
from .elements import characteristic_lines
from .config import FWHM_TO_SIGMA


@dataclass
class PeakInfo:
    """描画注釈用のピーク情報。"""

    symbol: str          # 元素記号
    name: str            # ライン名（Ka1 など）
    energy_kev: float    # エネルギー [keV]
    rel_weight: float    # このピークの相対総カウント重み
    observed_at_peak: float = 0.0  # ピーク位置チャネルの観測カウント（後段で設定）
    layer: str = "bulk"      # 表示ラベル（"bulk" | "膜1" | "基板" 等）
    layer_order: int = 0     # 深さ順（0=最表面, N=基板）。色分け・並べ替え用


def _gaussian_channels(energy_kev: np.ndarray, center_kev: float,
                       sigma_kev: float) -> np.ndarray:
    """チャネル和が 1 になるよう規格化した Gaussian 形状を返す。"""
    if sigma_kev <= 0.0:
        out = np.zeros_like(energy_kev)
        out[int(np.argmin(np.abs(energy_kev - center_kev)))] = 1.0
        return out
    g = np.exp(-0.5 * ((energy_kev - center_kev) / sigma_kev) ** 2)
    total = g.sum()
    return g / total if total > 0.0 else g


def build_peaks(energy_kev: np.ndarray, cfg: SimulationConfig
                ) -> tuple[np.ndarray, list[PeakInfo]]:
    """全元素・全ラインの特性X線相対スペクトルとピーク一覧を生成する。

    各ピークの総カウント重み（相対）:
        weight = (濃度/100) * ライン相対強度
    をチャネル和 1 の Gaussian に分配する（エネルギー依存 FWHM を反映）。
    制動X線との相対スケール（P/B）は spectrum.simulate 側で正規化する。

    Returns:
        (相対スペクトル配列, PeakInfo のリスト)
    """
    energy_kev = np.asarray(energy_kev, dtype=float)
    spectrum = np.zeros_like(energy_kev)
    peaks: list[PeakInfo] = []
    e0_ev = cfg.beam.e0_ev

    for elem in cfg.elements:
        frac = max(elem.concentration, 0.0) / 100.0
        if frac <= 0.0:
            continue
        try:
            lines = characteristic_lines(elem.symbol, e0_ev)
        except ValueError:
            continue

        for line in lines:
            center = line.energy_kev
            if center < energy_kev[0] or center > energy_kev[-1]:
                continue  # 表示レンジ外
            sigma_kev = fwhm_ev(center * 1.0e3, cfg.detector) * FWHM_TO_SIGMA / 1.0e3
            weight = frac * line.rel_intensity
            shape = _gaussian_channels(energy_kev, center, sigma_kev)
            spectrum += weight * shape
            peaks.append(PeakInfo(
                symbol=elem.symbol,
                name=line.name,
                energy_kev=center,
                rel_weight=weight,
            ))

    return spectrum, peaks


def build_peaks_layered(energy_kev: np.ndarray, cfg: SimulationConfig
                        ) -> tuple[np.ndarray, list[PeakInfo]]:
    """フェーズ3: 薄膜/基板の深さ積分強度から特性X線スペクトルを生成。

    depth.layered_line_intensities が返す層別・ライン別の放出強度を、
    エネルギー依存 FWHM の Gaussian に分配する。層情報を PeakInfo に保持。
    """
    from .depth import layered_line_intensities  # 循環 import 回避のため遅延

    energy_kev = np.asarray(energy_kev, dtype=float)
    spectrum = np.zeros_like(energy_kev)
    peaks: list[PeakInfo] = []

    for ll in layered_line_intensities(cfg):
        center = ll.line.energy_kev
        if center < energy_kev[0] or center > energy_kev[-1]:
            continue
        if ll.intensity <= 0.0:
            continue
        sigma_kev = fwhm_ev(center * 1.0e3, cfg.detector) * FWHM_TO_SIGMA / 1.0e3
        shape = _gaussian_channels(energy_kev, center, sigma_kev)
        spectrum += ll.intensity * shape
        peaks.append(PeakInfo(
            symbol=ll.symbol,
            name=ll.line.name,
            energy_kev=center,
            rel_weight=ll.intensity,
            layer=ll.layer_label,
            layer_order=ll.layer_order,
        ))

    return spectrum, peaks
