"""物理定数・シミュレーション設定・データクラスモデル。

数値はすべて実験的に妥当な範囲の近似値。教育・R&D用途の直感的可視化を
目的としており、定量分析の絶対精度を保証するものではない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


# --------------------------------------------------------------------------
# 物理定数
# --------------------------------------------------------------------------
# Si(Li)/SDD 検出器の電子正孔対生成エネルギー [eV] と Fano 係数
EPSILON_EH_SI: float = 3.85   # eV / e-h pair (Si)
FANO_SI: float = 0.12         # Fano 係数（Si）
# EDS 分解能の基準点: Mn Kα (5895 eV) における FWHM [eV]
FWHM_REF_EV: float = 130.0
E_REF_EV: float = 5895.0
# ガウス FWHM ⇔ σ 変換係数 (2*sqrt(2*ln2))
FWHM_TO_SIGMA: float = 1.0 / 2.35482


# --------------------------------------------------------------------------
# 検出器窓（既定は Be 薄窓）
# --------------------------------------------------------------------------
# 密度 [g/cm^3] は xraylib からも取得できるが、窓材の既定値をここに保持
BE_DENSITY: float = 1.848      # g/cm^3
DEFAULT_WINDOW_ELEMENT: str = "Be"
DEFAULT_WINDOW_THICKNESS_UM: float = 8.0   # um（薄窓 Be の代表値）


# --------------------------------------------------------------------------
# エネルギー軸
# --------------------------------------------------------------------------
DEFAULT_E_MIN_KEV: float = 0.05
DEFAULT_E_MAX_KEV: float = 20.0
DEFAULT_N_CHANNELS: int = 2048   # マルチチャネルアナライザ相当


# --------------------------------------------------------------------------
# データクラスモデル
# --------------------------------------------------------------------------
@dataclass
class BeamConditions:
    """電子線・測定条件。"""

    accel_voltage_kv: float = 15.0     # 加速電圧 [kV]
    probe_current: float = 1.0         # プローブ電流 [任意単位]
    live_time_s: float = 60.0          # 積算時間 [s]

    @property
    def e0_ev(self) -> float:
        """入射電子エネルギー [eV]。"""
        return self.accel_voltage_kv * 1.0e3


@dataclass
class ElementSpec:
    """試料中の1元素の指定。"""

    symbol: str                 # 元素記号（例: "Ti"）
    concentration: float        # 濃度 [質量% 相当, 0-100]


@dataclass
class DetectorConfig:
    """検出器・窓の設定。"""

    window_element: str = DEFAULT_WINDOW_ELEMENT
    window_thickness_um: float = DEFAULT_WINDOW_THICKNESS_UM
    apply_window_absorption: bool = True
    fwhm_ref_ev: float = FWHM_REF_EV
    e_ref_ev: float = E_REF_EV


@dataclass
class EnergyAxis:
    """スペクトルのエネルギー軸設定。"""

    e_min_kev: float = DEFAULT_E_MIN_KEV
    e_max_kev: float = DEFAULT_E_MAX_KEV
    n_channels: int = DEFAULT_N_CHANNELS


@dataclass
class Layer:
    """多層構造の1層（化合物対応）。

    composition は化学式（"Ti", "TiO2", "Al2O3" 等）。density を None に
    すると式から自動決定（プリセット表 → 体積加算則推定）。
    """

    composition: str = "Ti"          # 化学式
    thickness_nm: float = 20.0       # 膜厚 [nm]
    density: float | None = None     # g/cm^3（None は自動）


@dataclass
class LayerConfig:
    """フェーズ3: 基板上の多層構造設定。

    layers は表面から順（layers[0] が最表面 = 付着物/最上層、
    末尾が基板に最も近い層）。その下に半無限の基板がある。
    各層・基板は化学式で組成を指定できる（Bragg 加算則で吸収を計算）。
    """

    layers: Sequence[Layer] = field(
        default_factory=lambda: [Layer("Au", 50.0), Layer("Ti", 10.0)])
    substrate_composition: str = "Si"   # 基板の組成（化学式）
    substrate_density: float | None = None
    takeoff_deg: float = 35.0           # X線取り出し角 [deg]


@dataclass
class SimulationConfig:
    """1回のシミュレーション実行の全設定。"""

    beam: BeamConditions = field(default_factory=BeamConditions)
    elements: Sequence[ElementSpec] = field(default_factory=list)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    axis: EnergyAxis = field(default_factory=EnergyAxis)
    # 動作モード: "bulk"（均質バルク, フェーズ1/2）| "thin_film"（薄膜/基板, フェーズ3）
    mode: str = "bulk"
    layer: LayerConfig = field(default_factory=LayerConfig)
    # 最強特性X線ピークのチャネル高さ ≒ intensity_scale × 線量(電流×時間)。
    # すなわち「Max カウント」を線量に線形連動させる較正係数。
    intensity_scale: float = 150.0
    # 最強ピーク位置における P/B（ピーク高さ / 直下の制動X線高さ）。
    # 第一原理値ではなく可視化用に調整した経験係数（要キャリブレーション）。
    peak_to_background: float = 30.0
    random_seed: int | None = None
