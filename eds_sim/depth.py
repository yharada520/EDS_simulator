"""フェーズ3: 薄膜／基板の φ(ρz) 深さ分布モデル。

X線発生の深さ分布 φ(ρz) に Packwood-Brown 型の表面中心ガウス形を採用する:

    φ(ρz) = γ·exp(-α²·ρz²)·[1 - (γ-φ0)/γ·exp(-β·ρz)]

深さスケール（α）は Kanaya-Okayama 電子飛程に固定し、加速電圧依存性
R ∝ E0^1.67 を担保する（材料分析で広く用いられる飛程式を出所とする）。
薄膜層・基板層の放出X線強度は、自己吸収および薄膜による吸収減衰を
含めて scipy.integrate.quad で数値積分する。

較正上の前提:
    - 電子散乱マトリクスは基板組成で近似（薄膜は nm オーダーで ρz_f ≪ ρR）。
    - φ の振幅 γ・表面項 φ0/β は近似。教育的に本質的な「深さ範囲」と
      「吸収」は飛程式と xraylib の質量減衰係数に基づく。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.integrate import quad

from .config import SimulationConfig
from .composition import (
    compound_density,
    compound_mac_scalar,
    compound_mean_z_a,
    parse_formula,
)
from .elements import characteristic_lines, XLine


# --------------------------------------------------------------------------
# 電子飛程と φ(ρz)
# --------------------------------------------------------------------------
def kanaya_okayama_mass_range(z: float, a: float, e0_kev: float,
                              ec_kev: float) -> float:
    """Kanaya-Okayama の質量飛程 ρR [g/cm^2]（X線発生の実効深さスケール）。

    ρR = 2.76e-6 · A · (E0^1.67 - Ec^1.67) / Z^0.889
    （E0 は加速電圧、Ec は臨界励起エネルギー; いずれも keV）。
    """
    drive = max(e0_kev ** 1.67 - ec_kev ** 1.67, 1.0e-6)
    return 2.76e-6 * a * drive / (z ** 0.889)


@dataclass
class PhiParams:
    """φ(ρz) のパラメータ一式。"""

    gamma: float   # 振幅
    alpha: float   # ガウス幅（1/(g/cm^2)）
    beta: float    # 表面項の立ち上がり
    phi0: float    # 表面（ρz=0）でのイオン化


def make_phi_params(z_matrix: float, a_matrix: float, e0_kev: float,
                    ec_kev: float) -> PhiParams:
    """基板マトリクスと臨界励起エネルギーから φ(ρz) パラメータを構築。"""
    rho_r = kanaya_okayama_mass_range(z_matrix, a_matrix, e0_kev, ec_kev)
    # ガウス幅: ρR 付近で φ が十分減衰するよう α = 1.5/ρR（exp(-2.25)≈0.1）
    alpha = 1.5 / max(rho_r, 1.0e-9)
    # 表面イオン化: 過電圧 U0=E0/Ec に対して単調増加（近似）
    u0 = max(e0_kev / max(ec_kev, 1.0e-6), 1.0 + 1.0e-6)
    phi0 = 1.0 + 1.0 * (1.0 - 1.0 / u0)
    gamma = 1.5 * phi0                # 表面より高いピークを持つよう γ>φ0
    beta = 4.0 * alpha               # ρR/4 程度で立ち上がり
    return PhiParams(gamma=gamma, alpha=alpha, beta=beta, phi0=phi0)


def phi_rhoz(rhoz: float, p: PhiParams) -> float:
    """深さ ρz [g/cm^2] における φ(ρz)。"""
    g = p.gamma * math.exp(-(p.alpha ** 2) * rhoz ** 2)
    surface = 1.0 - (p.gamma - p.phi0) / p.gamma * math.exp(-p.beta * rhoz)
    return g * surface


# --------------------------------------------------------------------------
# 放出X線強度（深さ積分）
# --------------------------------------------------------------------------
def _emitted_integral(p: PhiParams, lo: float, hi: float,
                      mu_chi: float, offset: float) -> float:
    """∫_lo^hi φ(ρz)·exp(-mu_chi·(ρz-offset)) dρz を quad で評価。

    上限 hi は有限値であること（∞ を渡すと φ のガウスが鋭い場合に
    quad が適応サンプリングでピークを取りこぼし値が消失する）。
    """
    if hi <= lo:
        return 0.0

    def integrand(rhoz: float) -> float:
        return phi_rhoz(rhoz, p) * math.exp(-mu_chi * (rhoz - offset))

    val, _ = quad(integrand, lo, hi, limit=200)
    return max(val, 0.0)


def _gaussian_depth_cap(p: PhiParams) -> float:
    """φ のガウス項が十分減衰する質量深さ [g/cm^2]（積分上限に使用）。

    exp(-α²·ρz²) が exp(-100)≈0 となる ρz = 10/α を上限とする。
    """
    return 10.0 / max(p.alpha, 1.0e-9)


def _slab_line_intensity(line: XLine, z_top: float, z_bot: float,
                         over_atten: float, chi: float,
                         z_mat: float, a_mat: float, e0_kev: float,
                         emit_formula: str) -> float:
    """1つの層スラブ [z_top, z_bot] からの放出強度。

    - 発生層内の自己吸収: exp(-(μ/ρ)_layer·χ·(ρz-z_top))（z_top から上向き、
      層の化合物 μ/ρ で評価）
    - 上側の全層による減衰: over_atten（呼び出し側で計算した定数）
    z_bot=∞ 相当（基板）には十分大きな有限上限（ガウス裾）を渡すこと。
    """
    p = make_phi_params(z_mat, a_mat, e0_kev, line.ec_kev)
    mu_self = compound_mac_scalar(emit_formula, line.energy_kev) * chi
    cap = _gaussian_depth_cap(p)
    # φ を全面積で規格化 → このスラブが担う「全生成のうち脱出できる割合」を返す。
    # 生成強度（過電圧・蛍光収率・遷移確率）はライン重み側が持つため二重計上を避ける。
    total_area = _emitted_integral(p, 0.0, cap, 0.0, offset=0.0)
    if total_area <= 0.0:
        return 0.0
    hi = min(z_bot, cap)  # 発生深さを超える層は 0
    integral = _emitted_integral(p, z_top, hi, mu_self, offset=z_top)
    return over_atten * integral / total_area


# --------------------------------------------------------------------------
# 層構造の全ライン強度
# --------------------------------------------------------------------------
@dataclass
class LayerLine:
    """層構造スペクトル構築用の1ライン。"""

    symbol: str         # 発生元素の記号
    layer_order: int    # 0..N-1 = 表面からの層, N = 基板
    layer_label: str    # 表示名（"膜1" / "基板" 等）
    line: XLine
    intensity: float    # 深さ積分・吸収込みの相対放出強度


def layered_line_intensities(cfg: SimulationConfig) -> list[LayerLine]:
    """多層（表面→基板）の全特性ラインについて放出強度を算出する。

    各層は化合物で、構成元素が質量分率に比例して発光する。放出X線は
    発生層の化合物 μ/ρ で自己吸収され、上側の全層の質量厚×化合物 μ/ρ
    （放出ラインのエネルギーで評価、Bragg 加算則）で減衰する。基板は
    最下層の下の半無限領域。電子散乱マトリクスは基板の平均 Z,A で近似する。
    """
    lay = cfg.layer
    e0_kev = cfg.beam.accel_voltage_kv
    chi = 1.0 / math.sin(math.radians(max(lay.takeoff_deg, 1.0)))

    # 電子散乱マトリクスは基板組成の質量加重平均 Z,A で近似
    z_mat, a_mat = compound_mean_z_a(lay.substrate_composition)

    layers = list(lay.layers)
    formulas = [L.composition for L in layers]
    fractions = [parse_formula(f) for f in formulas]  # 各層 {元素: 質量分率}
    densities = [compound_density(L.composition, L.density) for L in layers]

    # 各層の質量深さ ρz [g/cm^2] と境界（表面 z=0 から下向き）
    rhoz = [max(L.thickness_nm, 0.0) * 1.0e-7 * rho
            for L, rho in zip(layers, densities)]
    z_top = [sum(rhoz[:k]) for k in range(len(layers))]  # 各層の上端
    z_stack = sum(rhoz)                                   # スタック全厚（基板上端）

    def overlying_atten(energy_kev: float, n_above: int) -> float:
        """上側 n_above 層（index 0..n_above-1）による減衰係数。"""
        total = 0.0
        for j in range(n_above):
            total += compound_mac_scalar(formulas[j], energy_kev) * chi * rhoz[j]
        return math.exp(-total)

    out: list[LayerLine] = []

    # 各層ライン（構成元素ごと × 質量分率）
    # layer_label は言語中立トークン（表示は UI 側で層番号と共に整形）
    for k, L in enumerate(layers):
        if rhoz[k] <= 0.0:
            continue
        label = "film"
        for elem, wfrac in fractions[k].items():
            for line in characteristic_lines(elem, e0_kev * 1.0e3):
                over = overlying_atten(line.energy_kev, k)
                inten = wfrac * line.rel_intensity * _slab_line_intensity(
                    line, z_top[k], z_top[k] + rhoz[k], over, chi,
                    z_mat, a_mat, e0_kev, formulas[k])
                out.append(LayerLine(elem, k, label, line, inten))

    # 基板ライン（構成元素ごと、スタック全体で減衰）
    sub_fractions = parse_formula(lay.substrate_composition)
    for elem, wfrac in sub_fractions.items():
        for line in characteristic_lines(elem, e0_kev * 1.0e3):
            over = overlying_atten(line.energy_kev, len(layers))
            inten = wfrac * line.rel_intensity * _slab_line_intensity(
                line, z_stack, math.inf, over, chi,
                z_mat, a_mat, e0_kev, lay.substrate_composition)
            out.append(LayerLine(elem, len(layers), "substrate", line, inten))

    return out
