from dataclasses import replace
from math import isclose
from random import Random

from research.physical_cost.banked_scale import DeepArchitecture
from research.physical_cost.concurrent_search import candidates
from research.physical_cost.concurrent_serving import Plan, compile_program, placement
from research.physical_cost.cotenancy_ablation import NEAR_CAPACITY, idle_ps
from research.physical_cost.serving_ddr import CK, DDR
from research.physical_cost.serving_distribution import select, stage_gate
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


def test_architecture_probes_keep_cutoff_ties_and_reuse_the_anchor():
    rows = [(i, [(min(i, 7), "anchor"), (20, "other")]) for i in range(9)]
    scores = {}
    ranked = candidates(rows, "af_probe", scores)
    for i in range(9):
        assert next(ranked) == (i, "anchor")
        scores[i] = 100 - i
    assert list(ranked) == [(i, "other") for i in reversed(range(9))]


def test_capacity_ablation_only_relaxes_cross_side_reservation():
    hw = DeepArchitecture(64, 64, 3, 65536, 1024)
    full = Plan(32, 96, 2, 3, False, True, 0)
    assert placement(hw, NEAR_CAPACITY, full) is None
    assert placement(hw, NEAR_CAPACITY, full, share_capacity=False) is not None
    cold = replace(full, resident=0)
    assert placement(hw, NEAR_CAPACITY, cold).regions == placement(
        hw, NEAR_CAPACITY, cold, share_capacity=False
    ).regions
    small = replace(hw, global_bank_bytes=16384)
    assert placement(small, NEAR_CAPACITY, full, share_capacity=False) is None


def test_idle_leakage_union_keeps_within_request_stalls_active():
    assert idle_ps((20, 0, 3, 21), (23, 8, 10, 25)) == 10
    assert idle_ps((4, 5, 11), (10, 12, 15)) == 4


def test_decode_first_releases_prefill_capacity_and_keeps_decode_arrival_offsets():
    hw = DeepArchitecture(64, 64, 3, 65536, 1024)
    work = replace(NEAR_CAPACITY, arrivals_ps=(18_000_000, 2_000_000, 2_120_000))
    plan = Plan(32, 96, 2, 3, False, True, 0)
    assert compile_program(hw, work, plan) is None
    decode = compile_program(hw, work, plan, phase="decode")
    assert all(task.owner > 0 for task in decode.tasks)
    assert not any(slot.startswith("p") for slot in decode.regions)
    assert {task.release for task in decode.tasks if task.label == "initial k"} == {0, 120_000}


def test_distribution_breaks_stage_ties_on_training_episodes_only():
    train = {"name": "train", "training": True, "episode": [7, 8],
             "decode": [1, 1], "prefill": [2, 1], "oracle": 7}
    test = {"name": "test", "training": False, "episode": [30, 9],
            "decode": [3, 1], "prefill": [2, 1], "oracle": 9}
    rows = [train, test]
    selection = select(rows, 2)
    assert selection["decode"]["training_ties"] == [0, 1]
    assert selection["decode"]["index"] == 0
    assert selection["decode"]["test"]["mean_edp"] == 30
    assert stage_gate(rows, selection)["passed"] is False
