from research.joint_budget.protocol import Hardware
from research.runtime.strip_codesign import Segment
from research.runtime.strip_native_timing import service
from research.runtime.strip_overlap import Calendar, audit


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
