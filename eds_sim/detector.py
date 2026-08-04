"""検出器応答モデル: エネルギー分解能・窓吸収・検出効率。"""

from __future__ import annotations

import numpy as np

from .config import DetectorConfig
from .elements import element_density, mass_attenuation_coefficient


def fwhm_ev(energy_ev: np.ndarray, cfg: DetectorConfig,
            epsilon: float = 3.85, fano: float = 0.12) -> np.ndarray:
    """エネルギー依存の検出器分解能 FWHM [eV]。

    FWHM(E)^2 = FWHM_ref^2 + (2.3548)^2 * epsilon * Fano * (E - E_ref)
    基準点（Mn Kα, 5895 eV で 130 eV）から統計項でスケールさせる標準式。
    負の平方根を避けるため下限をクリップ。
    """
    energy_ev = np.asarray(energy_ev, dtype=float)
    noise_term = cfg.fwhm_ref_ev ** 2
    stat_slope = (2.3548 ** 2) * epsilon * fano  # eV
    var = noise_term + stat_slope * (energy_ev - cfg.e_ref_ev)
    return np.sqrt(np.clip(var, 1.0, None))


def window_transmission(energy_kev: np.ndarray, cfg: DetectorConfig) -> np.ndarray:
    """検出器窓（既定 Be）の透過率。

    T(E) = exp(-(μ/ρ) * ρ * t)
    低エネルギー側で強く減衰し、軽元素ピークが抑制される様子を再現する。
    """
    if not cfg.apply_window_absorption:
        return np.ones_like(np.asarray(energy_kev, dtype=float))

    energy_kev = np.asarray(energy_kev, dtype=float)
    mu_rho = mass_attenuation_coefficient(cfg.window_element, energy_kev)  # cm^2/g
    rho = element_density(cfg.window_element)                              # g/cm^3
    thickness_cm = cfg.window_thickness_um * 1.0e-4                        # um -> cm
    return np.exp(-mu_rho * rho * thickness_cm)


def detector_response(energy_kev: np.ndarray, cfg: DetectorConfig) -> np.ndarray:
    """総合検出効率（現状は窓透過のみ。将来は Si 死層・空乏層厚を追加）。"""
    return window_transmission(energy_kev, cfg)
