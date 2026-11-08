from math import isclose
from random import Random

from research.physical_cost.serving_ddr import CK, DDR
from research.physical_cost.serving_softmax import dense, online


def test_blocked_attention_with_appended_token():
    rng = Random(710)
    query = (30, 8, -30, 11)
    keys = [tuple(rng.randint(-20, 20) for _ in query) for _ in range(32)]
    values = [tuple(rng.random() for _ in query) for _ in keys]
    old = dense(query, keys, values)
    keys.append(query)
    values.append((2, 3, 4, 5))
    expected = dense(query, keys, values)
    assert old != expected
    for tile in (1, 4, 7, 33, 128):
        assert all(isclose(a, b, rel_tol=1e-13) for a, b in zip(online(query, keys, values, tile), expected))


def test_ddr_closed_open_conflicting_and_direction_change():
    ddr = DDR(record=True)
    # Closed row: ACT 0, RD 16, data 32..36. Same-group row hit: RD 22.
    assert ddr.burst(0, False, 0) == (32 * CK, 36 * CK)
    assert ddr.burst(1, False, 0) == (38 * CK, 42 * CK)
    # Same bank, different row: PRE 39, ACT 55, WR 71, then read turnaround.
    assert ddr.burst(2048, True, 0) == (83 * CK, 87 * CK)
    assert ddr.burst(2049, False, 0) == (112 * CK, 116 * CK)
    assert [x.op for x in ddr.trace] == ["ACT", "RD", "RD", "PREpb", "ACT", "WR", "RD"]
