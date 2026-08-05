"""xraylib ヘルパ。遅延インポートとフォールバックを提供する。

xraylib は conda-forge 経由での導入を前提とするが、未導入環境
（素の pip、CI 等）でもフェーズ1が動くよう、存在しない場合は
内蔵の簡易テーブルにフォールバックする。
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# xraylib の遅延ロード
# --------------------------------------------------------------------------
_XRAYLIB = None
_XRAYLIB_TRIED = False


def get_xraylib():
    """xraylib モジュールを返す。未導入なら None。"""
    global _XRAYLIB, _XRAYLIB_TRIED
    if not _XRAYLIB_TRIED:
        _XRAYLIB_TRIED = True
        try:
            import xraylib  # type: ignore

            _XRAYLIB = xraylib
            logger.info("xraylib %s を検出", getattr(xraylib, "__version__", "?"))
        except Exception as exc:  # pragma: no cover - 環境依存
            logger.warning("xraylib を利用できません（フォールバック動作）: %s", exc)
            _XRAYLIB = None
    return _XRAYLIB


def xraylib_available() -> bool:
    return get_xraylib() is not None


# --------------------------------------------------------------------------
# フォールバック用の最小テーブル（xraylib 非導入時のデモ用）
# --------------------------------------------------------------------------
# symbol -> (Z, density[g/cm3], [(line_name, energy_keV, rel_intensity), ...])
_FALLBACK_TABLE = {
    "C":  (6,  2.267, [("Ka", 0.277, 1.0)]),
    "O":  (8,  1.429e-3, [("Ka", 0.525, 1.0)]),
    "Al": (13, 2.699, [("Ka", 1.487, 1.0)]),
    "Si": (14, 2.329, [("Ka", 1.740, 1.0)]),
    "Ti": (22, 4.506, [("Ka", 4.511, 1.0), ("Kb", 4.932, 0.13), ("La", 0.452, 0.4)]),
    "Fe": (26, 7.874, [("Ka", 6.404, 1.0), ("Kb", 7.058, 0.13), ("La", 0.705, 0.4)]),
    "Cu": (29, 8.960, [("Ka", 8.048, 1.0), ("Kb", 8.905, 0.13), ("La", 0.930, 0.4)]),
    "Au": (79, 19.30, [("Ma", 2.123, 1.0), ("La", 9.713, 0.6), ("Lb", 11.442, 0.4)]),
    "Be": (4,  1.848, [("Ka", 0.109, 1.0)]),
}


@dataclass(frozen=True)
class XLine:
    """特性X線1本。"""

    name: str            # ライン名（Ka1, Lb1 など）
    energy_kev: float    # エネルギー [keV]
    rel_intensity: float # 相対強度（同一試料内で規格化前の重み）
    ec_kev: float = 0.0  # 励起に必要な吸収端エネルギー（φ(ρz) の臨界励起電圧）
    series: str = ""     # 系列（K, L3, M5 など）


# --------------------------------------------------------------------------
# 基礎データ取得 API（xraylib があれば使用、無ければフォールバック）
# --------------------------------------------------------------------------
@lru_cache(maxsize=256)
def atomic_number(symbol: str) -> int:
    xl = get_xraylib()
    if xl is not None:
        return int(xl.SymbolToAtomicNumber(symbol))
    if symbol in _FALLBACK_TABLE:
        return _FALLBACK_TABLE[symbol][0]
    raise ValueError(f"未知の元素記号: {symbol}")


@lru_cache(maxsize=256)
def atomic_weight(symbol: str) -> float:
    """原子量 [g/mol]。フォールバックは A ≈ 2Z の粗い近似。"""
    xl = get_xraylib()
    if xl is not None:
        try:
            return float(xl.AtomicWeight(atomic_number(symbol)))
        except Exception:  # pragma: no cover
            pass
    return 2.0 * atomic_number(symbol)


@lru_cache(maxsize=256)
def element_density(symbol: str) -> float:
    """元素の密度 [g/cm^3]。"""
    xl = get_xraylib()
    if xl is not None:
        try:
            return float(xl.ElementDensity(atomic_number(symbol)))
        except Exception:  # pragma: no cover
            pass
    if symbol in _FALLBACK_TABLE:
        return _FALLBACK_TABLE[symbol][1]
    return 1.0


# xraylib のライン定数（存在する場合のみ参照）。
# (表示名, xraylib属性名, 系列) の順。系列で励起可否判定（吸収端）に使う。
_LINE_DEFS = [
    ("Ka1", "KA1_LINE", "K"),
    ("Ka2", "KA2_LINE", "K"),
    ("Kb1", "KB1_LINE", "K"),
    ("La1", "LA1_LINE", "L3"),
    ("La2", "LA2_LINE", "L3"),
    ("Lb1", "LB1_LINE", "L2"),
    ("Lb2", "LB2_LINE", "L3"),
    ("Lg1", "LG1_LINE", "L2"),
    ("Ma1", "MA1_LINE", "M5"),
    ("Mb",  "MB_LINE",  "M4"),
]

# 系列 → 対応する吸収端の xraylib SHELL 定数名
_SHELL_FOR_SERIES = {
    "K": "K_SHELL",
    "L1": "L1_SHELL",
    "L2": "L2_SHELL",
    "L3": "L3_SHELL",
    "M4": "M4_SHELL",
    "M5": "M5_SHELL",
}

# 系列 → その副殻の電子数（電子衝突電離断面積の重み）
_SHELL_ELECTRONS = {"K": 2, "L1": 2, "L2": 2, "L3": 4, "M4": 4, "M5": 6}


def _fluor_yield(xl, z: int, series: str) -> float:
    """副殻の蛍光収率 ω。取得不可（低ZのM殻等）は 0。"""
    shell_attr = _SHELL_FOR_SERIES.get(series)
    if shell_attr is not None and hasattr(xl, shell_attr):
        try:
            return float(xl.FluorYield(z, getattr(xl, shell_attr)))
        except Exception:
            return 0.0
    return 0.0


def electron_impact_weight(xl, z: int, series: str, edge_kev: float,
                           rad_rate: float, e0_kev: float) -> float:
    """電子線励起 EDS における特性ラインの相対生成強度。

        weight ∝ n_i · [ln(U)/U] / Ec²  ·  ω_i  ·  p_ij
        （n_i: 副殻電子数, U=E0/Ec: 過電圧, ω: 蛍光収率, p: 遷移確率）

    第1項は Bethe 形の電子衝突電離断面積で、閾値 U=1 でゼロ、U≈e で最大と
    なる（光子励起の xraylib CS_FluorLine とは挙動が異なる点に注意）。
    """
    if edge_kev <= 0.0:
        return 0.0
    u0 = e0_kev / edge_kev
    if u0 <= 1.0:
        return 0.0  # 過電圧不足で励起されない
    n_i = _SHELL_ELECTRONS.get(series, 2)
    ionization = n_i * math.log(u0) / (u0 * edge_kev * edge_kev)
    omega = _fluor_yield(xl, z, series)
    return ionization * omega * rad_rate


def characteristic_lines(symbol: str, e0_ev: float) -> list[XLine]:
    """指定元素の特性X線ラインを返す。

    e0_ev より吸収端エネルギーが低い（＝励起可能な）ラインのみ返す。
    相対強度は電子衝突電離（Bethe形）× 蛍光収率 × 遷移確率で重み付けし、
    多殻元素（Au の M/L 等）の殻間相対強度と過電圧依存性を反映する。
    xraylib 非導入時はフォールバックテーブル（近似）を使う。
    """
    xl = get_xraylib()
    z = atomic_number(symbol)
    e0_kev = e0_ev / 1.0e3

    if xl is None:
        lines = []
        if symbol in _FALLBACK_TABLE:
            for name, en, rel in _FALLBACK_TABLE[symbol][2]:
                if en < e0_kev:  # 簡易的にライン自身のエネルギーで判定
                    # フォールバックでは吸収端をライン+5%で近似
                    lines.append(XLine(name, en, rel, ec_kev=en * 1.05))
        return lines

    lines: list[XLine] = []
    for disp_name, attr, series in _LINE_DEFS:
        line_const = getattr(xl, attr, None)
        if line_const is None:
            continue
        try:
            energy = float(xl.LineEnergy(z, line_const))
        except Exception:
            energy = 0.0
        if energy <= 0.0:
            continue  # その元素に存在しないライン

        # 吸収端による励起可否判定
        edge = 0.0
        shell_attr = _SHELL_FOR_SERIES.get(series)
        if shell_attr is not None and hasattr(xl, shell_attr):
            try:
                edge = float(xl.EdgeEnergy(z, getattr(xl, shell_attr)))
            except Exception:
                edge = 0.0
            if edge > 0.0 and e0_kev < edge:
                continue  # 加速電圧不足で励起不可
        if edge <= 0.0:
            edge = energy * 1.05  # 端が取れない場合の近似

        # 放射遷移確率（殻内分岐比）
        try:
            rate = float(xl.RadRate(z, line_const))
        except Exception:
            rate = 0.0
        if rate <= 0.0:
            rate = 1.0e-3  # RadRate 未定義でも位置確認用に微小値を残す

        # 相対強度: 電子衝突電離 × 蛍光収率 × 遷移確率
        weight = electron_impact_weight(xl, z, series, edge, rate, e0_kev)
        if weight <= 0.0:
            weight = 1.0e-12  # 位置確認用の微小値（実質不可視）
        lines.append(XLine(disp_name, energy, weight, ec_kev=edge, series=series))

    return lines


# --------------------------------------------------------------------------
# 質量吸収係数（窓・自己吸収用）
# --------------------------------------------------------------------------
def mass_attenuation_coefficient(symbol: str, energy_kev: np.ndarray) -> np.ndarray:
    """全質量減衰係数 [cm^2/g] を配列で返す。

    xraylib.CS_Total はスカラー入力のため np.vectorize でベクトル化する。
    非導入時は簡易的な E^-3 近似（Z 依存込み）でフォールバック。
    """
    xl = get_xraylib()
    energy_kev = np.asarray(energy_kev, dtype=float)
    z = atomic_number(symbol)

    if xl is not None:
        def _one(e: float) -> float:
            # xraylib はスカラー入力かつタブレート範囲内のみ許容。
            # 範囲外（極低エネルギー等）は spline 外挿エラーを投げるため、
            # 強吸収（透過率≒0）相当の大きな値を返してフォールバックする。
            try:
                return float(xl.CS_Total(z, float(e)))
            except Exception:
                return 1.0e6
        _cs = np.vectorize(_one, otypes=[float])
        return _cs(np.clip(energy_kev, 1.0e-3, None))

    # フォールバック: 光電吸収の Bragg-Pierce 近似 μ/ρ ≈ k * Z^4 / E^3。
    # 係数 k は Be の実測（μ/ρ ≈ 12 cm^2/g @1.74 keV）に合わせて調整。
    # 低エネルギー側を十分に減衰させ、Kramers の 1/E 発散を抑える役割も持つ。
    safe_e = np.clip(energy_kev, 1.0e-2, None)
    return 0.15 * (z ** 4) / (safe_e ** 3)


def mac_scalar(symbol: str, energy_kev: float) -> float:
    """全質量減衰係数 [cm^2/g] のスカラー版（数値積分の内側で使う）。"""
    return float(mass_attenuation_coefficient(symbol, np.array([energy_kev]))[0])
