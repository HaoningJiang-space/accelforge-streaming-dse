from itertools import product

import numpy as np

from research.physical_cost.mixed_gate import Architecture, assess


def phase(energy, latency):
    costs = np.array([energy]), np.array([latency])
    return costs, costs, 1


def test_independent_architectures_and_one_time_residency_charge():
    a = Architecture(16, 128, 4, 16384, 1024)
    b = Architecture(32, 64, 2, 65536, 1024)
    macros = {
        size: {"area_mm2": 1, "leak_mw": 0.01}
        for size in (1024, 16384, 65536)
    }
    costs = {
        a: ([phase(1, 3), phase(10, 8)], None),
        b: ([phase(8, 8), phase(2, 2)], (phase(1, 1), (6, 6, 3))),
    }
    steps = 16
    prefill = {a: (1, 3), b: (8, 8)}
    decode = {a: [(160, 128)], b: [(32, 32), (22, 19)]}

    def objective(prefill_hw, decode_hw):
        energy, latency = prefill[prefill_hw]
        return min((energy + e) * (latency + t) for e, t in decode[decode_hw])

    result = assess(costs, macros, 40, steps)
    assert result["shared_edp_pj_ns"] == min(objective(hw, hw) for hw in costs)
    assert result["independent_hardware_edp_pj_ns"] == min(
        objective(p, d) for p, d in product(costs, repeat=2)
    )
    assert result["resident_eligible_points"] == 1
    assert result["winner_uses_resident_kv"]
