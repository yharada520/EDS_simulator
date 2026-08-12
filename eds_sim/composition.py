"""化合物組成の取り扱い（化学式パース・密度・質量吸収・平均原子番号）。

各層／基板を化学式（例: "Ti", "TiO2", "Al2O3", "Si3N4"）で指定できるようにする。
括弧付き式（"Ca(OH)2" 等）は未対応（単純式のみ）。
"""

from __future__ import annotations

import logging
import re

import numpy as np

from .elements import (
    atomic_number,
    atomic_weight,
    element_density,
    mass_attenuation_coefficient,
)

logger = logging.getLogger(__name__)

# 元素記号＋任意の係数（整数/小数）
_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*\.?\d*)")


def parse_formula(formula: str) -> dict[str, float]:
    """化学式を {元素記号: 質量分率} に変換する。

    Raises:
        ValueError: 解釈できない式、または未知の元素記号。
    """
    formula = (formula or "").strip()
    if not formula:
        raise ValueError("組成式が空です")

    counts: dict[str, float] = {}
    matched_len = 0
    for m in _TOKEN.finditer(formula):
        el = m.group(1)
        num = m.group(2)
        n = float(num) if num else 1.0
        counts[el] = counts.get(el, 0.0) + n
        matched_len += len(m.group(0))

    if not counts or matched_len != len(formula):
        raise ValueError(f"組成式を解釈できません: {formula}")

    # 原子数 → 質量分率（atomic_number で未知記号は ValueError）
    weights = {el: n * atomic_weight(el) for el, n in counts.items()
               if atomic_number(el)}
    total = sum(weights.values())
    if total <= 0.0:
        raise ValueError(f"質量分率を計算できません: {formula}")
    return {el: w / total for el, w in weights.items()}


def _atom_counts(formula: str) -> dict[str, float]:
    counts: dict[str, float] = {}
    matched_len = 0
    for m in _TOKEN.finditer(formula.strip()):
        el = m.group(1)
        num = m.group(2)
        counts[el] = counts.get(el, 0.0) + (float(num) if num else 1.0)
        matched_len += len(m.group(0))
    return counts


def _canonical(formula: str) -> str:
    """元素記号のアルファベット順に並べた正規化キー（プリセット照合用）。"""
    counts = _atom_counts(formula)
    return "".join(f"{el}{counts[el]:g}" for el in sorted(counts))


# よく使う薄膜化合物の密度 [g/cm^3]（正規化キーで保持）
_PRESET_DENSITY_RAW = {
    "TiN": 5.22, "TiO2": 4.23, "SiO2": 2.20, "Si3N4": 3.17, "SiC": 3.21,
    "Al2O3": 3.95, "AlN": 3.26, "Cr2O3": 5.22, "Fe2O3": 5.24, "NiO": 6.67,
    "ZnO": 5.61, "Ga2O3": 5.88, "GaN": 6.15, "HfO2": 9.68, "ZrO2": 5.68,
    "Ta2O5": 8.20, "TaN": 14.3, "WC": 15.6, "MoS2": 5.06, "Cu2O": 6.0,
}
_PRESET_DENSITY = {_canonical(k): v for k, v in _PRESET_DENSITY_RAW.items()}


# プリセット外・上書きなしの多元素化合物に用いる仮の既定密度 [g/cm^3]
_NOMINAL_DENSITY = 5.0


def resolve_density(formula: str,
                    override: float | None = None) -> tuple[float, str]:
    """化合物密度 [g/cm^3] と出所（言語中立トークン）を返す。

    優先順位: ユーザ上書き > プリセット表 > 単一元素の元素密度 > 仮の既定値。
    出所トークンは "specified" | "preset" | "element" | "nominal"。

    体積加算則 1/ρ=Σ w_i/ρ_i は、xraylib が O/N を気体密度で返すため
    化合物では破綻する。よってプリセットに無い多元素化合物は仮の既定値とし、
    正確な密度はユーザ手入力を促す。
    """
    if override is not None and override > 0.0:
        return override, "specified"
    canon = _canonical(formula)
    if canon in _PRESET_DENSITY:
        return _PRESET_DENSITY[canon], "preset"
    fractions = parse_formula(formula)
    if len(fractions) == 1:
        return element_density(next(iter(fractions))), "element"
    return _NOMINAL_DENSITY, "nominal"


def compound_density(formula: str, override: float | None = None) -> float:
    """化合物密度 [g/cm^3]（出所は resolve_density を参照）。"""
    return resolve_density(formula, override)[0]


def compound_mac(formula: str, energy_kev: np.ndarray) -> np.ndarray:
    """化合物の全質量減衰係数 [cm^2/g]（Bragg 加算則）。"""
    energy_kev = np.asarray(energy_kev, dtype=float)
    fractions = parse_formula(formula)
    out = np.zeros_like(energy_kev)
    for el, w in fractions.items():
        out += w * mass_attenuation_coefficient(el, energy_kev)
    return out


def compound_mac_scalar(formula: str, energy_kev: float) -> float:
    """化合物 μ/ρ のスカラー版。"""
    return float(compound_mac(formula, np.array([energy_kev]))[0])


def compound_mean_z_a(formula: str) -> tuple[float, float]:
    """φ(ρz) の飛程計算用の質量加重平均 (Z̄, Ā)。"""
    fractions = parse_formula(formula)
    z_bar = sum(w * atomic_number(el) for el, w in fractions.items())
    a_bar = sum(w * atomic_weight(el) for el, w in fractions.items())
    return z_bar, a_bar
