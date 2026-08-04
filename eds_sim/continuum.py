"""制動X線（バックグラウンド）モデル。

Kramers の法則:
    I(E) dE ∝ Z_bar * (E0 - E) / E
ここで E は光子エネルギー、E0 は入射電子エネルギー、Z_bar は
試料の平均原子番号。E >= E0 では 0（デュエーン・ハントの限界）。
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .config import ElementSpec
from .elements import atomic_number


def mean_atomic_number(elements: Sequence[ElementSpec]) -> float:
    """濃度重み付き平均原子番号。元素未指定なら軽元素マトリクス相当。"""
    if not elements:
        return 6.0  # 炭素相当のダミーマトリクス
    total = sum(max(e.concentration, 0.0) for e in elements)
    if total <= 0.0:
        return 6.0
    return sum(atomic_number(e.symbol) * max(e.concentration, 0.0)
               for e in elements) / total


def kramers_continuum(
    energy_kev: np.ndarray,
    e0_ev: float,
    elements: Sequence[ElementSpec],
) -> np.ndarray:
    """Kramers 制動X線の相対強度を返す（未規格化）。

    Args:
        energy_kev: エネルギー軸 [keV]
        e0_ev:      入射電子エネルギー [eV]
        elements:   試料組成（平均原子番号の算出に使用）

    Returns:
        各エネルギーでの制動X線相対強度（E>=E0 は 0）。
    """
    energy_kev = np.asarray(energy_kev, dtype=float)
    e0_kev = e0_ev / 1.0e3
    z_bar = mean_atomic_number(elements)

    # 0 割り回避のため下限をクリップ
    safe_e = np.clip(energy_kev, 1.0e-3, None)
    intensity = z_bar * (e0_kev - safe_e) / safe_e
    # デュエーン・ハント限界より高エネルギー、および負値をゼロに
    intensity = np.where(energy_kev < e0_kev, intensity, 0.0)
    intensity = np.clip(intensity, 0.0, None)
    return intensity
