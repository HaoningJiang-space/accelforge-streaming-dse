from itertools import product

from research.joint_budget.protocol import Hardware
from research.runtime import strip_codesign as dse
from research.runtime.strip_trace import replay


def test_rectangular_fused_trace_matches_analytic_and_hand_counts():
    shape = (2, 5, 3)
    h = Hardware(2, 3, 50)
    plan = (dse.Segment(0, 2, 2, (True, False), ((2, 2), (3, 2))),)
    cost, peak, words = replay(3, shape, h, plan, scalar=True)
    assert dse.evaluate(3, shape, h, plan) == (cost, peak)
    assert replay(3, shape, h, plan) == (cost, peak, words)
    assert peak == 10 + 2 * (5 + 3) + 3 * 2
    assert words[0, "RF", "W0", "write"] == 2 * 2 * 5
    assert words[0, "RF", "W0", "read"] == 3 * 2 * 5
    assert words[0, "DRAM", "W0", "read"] == 2 * 5
    assert words[1, "DRAM", "W1", "read"] == 2 * 5 * 3
    assert words[1, "SRAM", "T2", "read"] == 3 * 3 * 2  # Prior sum and final drain.
    assert not words[0, "DRAM", "T1", "write"]
    assert not words[1, "DRAM", "T1", "read"]


def test_full_tiny_grammar_agrees_with_exhaustive_trace(monkeypatch):
    rows, widths = 3, (2, 3, 2)
    geometries = ((2, 3), (3, 2))
    monkeypatch.setattr(dse, "CAPACITIES", (12, 17))
    for capacity in dse.CAPACITIES:
        oracle = []
        for x, y in geometries:
            h = Hardware(x, y, capacity)

            def segments(start, stop):
                pairs = list(zip(widths[start:stop], widths[start+1:stop+1]))
                tiles = [[(p, q) for p in range(1, min(k, y)+1)
                          for q in range(1, min(n, x)+1)] for k, n in pairs]
                for b, pins, *layout in product(range(1, rows+1),
                                                 product((False, True), repeat=len(pairs)), *tiles):
                    yield dse.Segment(start, stop, b, pins, tuple(layout))

            for plan in [*((g,) for g in segments(0, 2)),
                         *product(segments(0, 1), segments(1, 2))]:
                try:
                    (e, t), _, _ = replay(rows, widths, h, plan, scalar=True)
                except ValueError as error:
                    assert str(error) == "wave exceeds physical SRAM capacity"
                else:
                    oracle.append(e * t)
        (e, t), _, _ = dse.dynamic_search(rows, widths, capacity, geometries)
        assert e * t == min(oracle)
