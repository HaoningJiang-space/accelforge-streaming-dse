from itertools import product

from research.joint_budget.protocol import Hardware
from research.runtime.strip_codesign import Segment
from research.runtime.strip_native_timing import service
from research.runtime.strip_overlap import Calendar, audit
from research.runtime.strip_overlap_cost import evaluate_overlap
from research.runtime import strip_overlap_search as search


def test_row_wave_intervals_allow_only_independent_port_overlap():
    serial, pipeline = Calendar(), Calendar()
    for calendar, enabled in ((serial, False), (pipeline, True)):
        calendar.wave(3, 2, 3, True, enabled)
        assert calendar.words == {"read": 15, "write": 9, "mac": 3}
    assert serial.now == 3 * (15 + 1536 + 36)
    assert pipeline.now == 15 + 3 * 1536 + 36
    assert pipeline.overlapped_ticks == serial.now - pipeline.now


def test_calendar_checks_staging_and_full_tail_traffic():
    rows, widths = 4, (3, 5)
    plan = (Segment(0, 1, 4, (False,), ((2, 3),)),)
    tight = audit(rows, widths, Hardware(3, 2, 38), plan)
    ample = audit(rows, widths, Hardware(3, 2, 46), plan)
    assert tight["overlapped_waves"] == 0
    assert ample["overlapped_waves"] == 4
    assert ample["peak_bytes"] == 43
    assert tight["service_ticks"] == ample["service_ticks"]
    assert ample["end_ticks"] < tight["end_ticks"]


def test_native_tail_fold_discards_required_dram_service():
    perfect = service(1, 64, 64, 1, 32, 32, False, True, True)
    tail = service(1, 64, 64, 1, 48, 48, False, True, True)
    assert perfect["MainMemory"] == (64 * 64 + 2 * 64) * 40
    assert tail["MainMemory"] == (48 * 48 + 2 * 64) * 40
    assert perfect["MAC"] == tail["MAC"] == 4 * 1536


def test_identical_actions_can_have_different_overlap():
    h = Hardware(8, 8, 84)
    small, large = [(Segment(0, 1, 4, (False,), ((size, size),)),) for size in (4, 5)]
    a, b = (audit(4, (7, 7), h, plan) for plan in (small, large))
    assert a["service_ticks"] == b["service_ticks"]
    assert a["serial_ticks"] == b["serial_ticks"]
    assert a["overlapped_waves"] == 4
    assert b["overlapped_waves"] < 4
    assert a["end_ticks"] < b["end_ticks"]


def test_overlap_search_agrees_with_unpruned_integer_space(monkeypatch):
    rows, widths = 5, (5, 7)
    geometries = ((3, 4), (4, 3), (2, 6))
    monkeypatch.setattr(search, "CAPACITIES", (36, 52, 81))
    for cap in search.CAPACITIES:
        all_scores = []
        for x, y in geometries:
            h = Hardware(x, y, cap)
            for b, pin, p, q in product(range(1, rows+1), (False, True),
                                        range(1, min(y, widths[0])+1), range(1, x+1)):
                if b * sum(widths) + (widths[0] * widths[1] if pin else p * q) > cap:
                    continue
                plan = (Segment(0, 1, b, (pin,), ((p, q),)),)
                candidate = audit(rows, widths, h, plan)
                (e, t), _ = evaluate_overlap(rows, widths, h, plan)
                assert t == candidate["end_ticks"]
                all_scores.append(e * t)
        (cost, _, _), _ = search.exact_search(rows, widths, cap, geometries)
        assert cost[0] * cost[1] == min(all_scores)
