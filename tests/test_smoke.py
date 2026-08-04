"""スモークテスト。

xraylib が無い環境（内蔵フォールバック）でも通ることを意図している。
pytest でも、`python tests/test_smoke.py` 直接実行でも動作する。
"""

from __future__ import annotations

import numpy as np
import pytest

from eds_sim.config import (
    BeamConditions,
    ElementSpec,
    Layer,
    LayerConfig,
    SimulationConfig,
)
from eds_sim.composition import compound_density, parse_formula
from eds_sim.elements import xraylib_available
from eds_sim.spectrum import simulate


def test_bulk_simulation_produces_counts():
    cfg = SimulationConfig(
        beam=BeamConditions(15.0, 5.0, 120.0),
        elements=[ElementSpec("Si", 99.0), ElementSpec("Ti", 1.0)],
        random_seed=1,
    )
    r = simulate(cfg)
    assert r.energy_kev.shape == r.observed.shape
    assert np.isfinite(r.theoretical).all()
    assert (r.observed >= 0).all()
    assert r.max_counts > 0


def test_seed_is_reproducible():
    def run():
        return simulate(SimulationConfig(
            elements=[ElementSpec("Si", 99.0), ElementSpec("Ti", 1.0)],
            random_seed=7,
        )).observed
    assert np.array_equal(run(), run())


def test_thin_film_runs_with_layers():
    cfg = SimulationConfig(
        beam=BeamConditions(15.0, 5.0, 120.0),
        mode="thin_film",
        layer=LayerConfig(
            layers=[Layer("Au", 50.0), Layer("Ti", 10.0)],
            substrate_composition="Si",
        ),
        random_seed=2,
    )
    r = simulate(cfg)
    assert np.isfinite(r.theoretical).all()
    layers = {p.layer for p in r.peaks}
    # 少なくとも膜と基板のラベルが付く
    assert any(lab != "基板" for lab in layers)
    assert "基板" in layers


@pytest.mark.skipif(not xraylib_available(),
                    reason="質量吸収係数の定量精度に依存するため xraylib が必要")
def test_thicker_overlayer_attenuates_buried_layer():
    """上層 Au が厚いほど、埋もれた Ti のネット強度は減衰し最終的に 0 になる。"""
    def ti_net(au_nm: float) -> float:
        layers = [Layer("Au", au_nm), Layer("Ti", 10.0)] if au_nm > 0 else [Layer("Ti", 10.0)]
        r = simulate(SimulationConfig(
            beam=BeamConditions(20.0, 5.0, 120.0),
            mode="thin_film",
            layer=LayerConfig(layers=layers, substrate_composition="Si"),
            random_seed=2,
        ))
        e = r.energy_kev
        cands = [p for p in r.peaks if p.symbol == "Ti" and p.name.startswith("Ka")]
        if not cands:
            return 0.0
        p = max(cands, key=lambda x: x.rel_weight)
        return float(r.characteristic[int(np.argmin(np.abs(e - p.energy_kev)))])

    assert ti_net(1000.0) < ti_net(500.0) < ti_net(50.0)


def test_parse_formula_weight_fractions():
    fr = parse_formula("TiO2")
    assert abs(fr["Ti"] - 0.60) < 0.03
    assert abs(fr["O"] - 0.40) < 0.03
    assert abs(sum(fr.values()) - 1.0) < 1e-9


def test_compound_density_preset():
    assert abs(compound_density("SiO2") - 2.20) < 1e-6
    assert abs(compound_density("SiO2", 2.65) - 2.65) < 1e-6  # 上書き優先


@pytest.mark.parametrize("bad", ["Au(oops", "", "xyz", "123", "Zx2"])
def test_parse_formula_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        parse_formula(bad)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
