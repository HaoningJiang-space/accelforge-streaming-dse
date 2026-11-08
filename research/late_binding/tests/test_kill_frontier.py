"""Small native replay and independent enumeration for the late-binding screen."""

from itertools import product

import numpy as np

from research.late_binding import kill_frontier as kill
from research.late_binding import late_binding_grid as grid
from research.tracking_audit import common


def tiny_bank(shape, bits, bandwidth):
    metrics = common.RU | common.af.Metrics.ACTIONS
    spec = common.build(common.Case("matmuls", "nvdla", (2, 16, 16)), 2, metrics)
    spec = kill.configure_spec(spec, shape, bits, bandwidth)
    bank = []
    for groups in kill.native_jobs(spec, metrics).values():
        signatures, energies = zip(*[
            kill.native_signature(job) for group in groups.values() for job in group
        ])
        bank.append((np.concatenate(signatures), np.concatenate(energies)))
    return bank


def brute_edp(bank, x, y, bits, bandwidth):
    layers = []
    for rows, energy in bank:
        feasible = (rows[:, 0] <= x) & (rows[:, 1] <= y) & (rows[:, 2] <= bits)
        times = [
            max(mac, dram, gb / bandwidth) for mac, dram, gb in rows[feasible, -3:]
        ]
        layers.append(zip(energy[feasible], times, strict=True))
    return min(
        ((e1 + e2) * (t1 + t2) for ((e1, t1), (e2, t2)) in product(*layers)),
        default=float("inf"),
    )


def test_native_late_binding_oracle():
    common.clear_switches()
    common.set_jobs(1)
    bank = tiny_bank((8, 16), 16 * 1024, 1.0)
    exact, epsilon = [], []
    for rows, energy in bank:
        front = kill.pareto_indices(rows)
        representative = front[kill.epsilon_indices(rows[front], np.sqrt(1.1))]
        exact.append((rows[front], energy[front]))
        epsilon.append((rows[representative], energy[representative]))

    for shape, bits, bandwidth in product(((4, 16), (8, 8)), (4096, 16384), (0.25, 1, 2)):
        hardware = (*shape, bits, bandwidth)
        raw = brute_edp(bank, *hardware)
        np.testing.assert_allclose(brute_edp(exact, *hardware), raw, rtol=1e-12)
        assert brute_edp(epsilon, *hardware) <= raw * (1.1 + 1e-12)
        native = brute_edp(tiny_bank(shape, bits, bandwidth), *shape, bits, 1)
        np.testing.assert_allclose(raw, native, rtol=1e-6, err_msg=f"hardware={hardware}")

    bound, masks = kill.graph_bound(exact)
    before, after = [], []
    (first, e_first), (second, e_second) = exact
    for i, j in product(range(len(first)), range(len(second))):
        x, y, bits = np.maximum(first[i, :3], second[j, :3])
        bandwidth = min(2, 2 * (1.5 - x * y / (32 * 192) - bits / (2 * 2**23)))
        if bandwidth < 0.25:
            continue
        times = sum(max(row[-3], row[-2], row[-1] / bandwidth) for row in (first[i], second[j]))
        edp = (e_first[i] + e_second[j]) * times
        before.append(edp)
        if masks[0][i] and masks[1][j]:
            after.append(edp)
    assert bound["relaxed_graph_edp_pj_ns"] <= min(before) * (1 + 1e-12)
    assert bound["incumbent_edp_pj_ns"] >= min(before) * (1 - 1e-12)
    assert min(after) == min(before)

    # A wins at slow bandwidth, B at fast bandwidth. A cannot delete B.
    # B also needs less SRAM, so epsilon cannot trade the two demands off.
    a = [1, 1, 65, 8] + [1] * len(kill.ACTIONS) + [8, 0, 2]
    b = [1, 1, 64, 8] + [1] * len(kill.ACTIONS) + [7, 0, 10]
    crossing = np.array([a, b], dtype=float)
    assert len(kill.pareto_indices(crossing)) == 2
    assert len(kill.epsilon_indices(crossing, np.sqrt(1.1))) == 2
    assert kill.latency(crossing, 1).argmin() == 0
    assert kill.latency(crossing, 2).argmin() == 1


def test_discrete_binding_against_architecture_and_mapping_sweep():
    specs = [
        [(4, 1, 1, 9, 3, 1, 9), (1, 3, 3, 7, 4, 1, 2), (2, 2, 2, 8, 5, 1, 5)],
        [(3, 2, 1, 4, 5, 2, 7), (1, 4, 3, 3, 7, 2, 1), (2, 1, 2, 5, 3, 2, 2)],
    ]
    banks = []
    for layer in specs:
        rows = np.array([[x, y, banks * 262144, 8, c, d, g]
                         for x, y, banks, _, c, d, g in layer], dtype=float)
        banks.append((rows, np.array([row[3] for row in layer], dtype=float)))
    budget = 2200
    expected = float("inf")
    for x, y, capacity, rate in product(range(1, 5), range(1, 5), range(1, 4), range(2, 17)):
        if x * y + 96 * capacity + 384 * rate <= budget:
            expected = min(expected, brute_edp(banks, x, y, capacity * 262144, rate / 8))
    optimum, witness, _, _ = grid.bind(banks, budget, float("inf"), {})
    np.testing.assert_allclose(optimum, expected, rtol=1e-12)
    np.testing.assert_allclose(grid.fixed_arch_edp(banks, witness, budget), expected, rtol=1e-12)
