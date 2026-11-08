import json
from dataclasses import replace
from itertools import product
from pathlib import Path

from research.physical_cost.banked_scale import DeepArchitecture
from research.physical_cost.external_ddr import SystemLedger
from research.physical_cost.serving_trace import run
from research.physical_cost.transformer_serving import Workload, Plan, compile_program
from research.physical_cost.transformer_validation import numerical
from research.physical_cost.transformer_boundary import summarize


ROOT = Path(__file__).resolve().parents[1]


def test_full_block_causal_prefill_matches_incremental_decode_and_online_attention():
    for width in (64, 128):
        assert numerical(width)["max_absolute_error"] < 2e-5


def test_full_block_actions_stage_deletion_and_cache_persistence():
    work = Workload(19, (29, 37), 2, (0, 0, 120000))
    hw = DeepArchitecture(32, 64, 16, 65536, 1024)
    for pin, online, resident in product((True, False), (True, False), (0, 7)):
        plan = Plan(16, 128, resident, False, online, pin, 1)
        p = compile_program(hw, work, plan)
        per_token = 10 * work.width**2 + 2 * work.width**2 // work.heads
        assert p.matrix_macs == (work.rows + len(work.contexts) * work.steps) * per_token
        labels = {task.label for task in p.tasks}
        assert {"LN1", "LN2", "GELU", "residual1", "residual2", "out", "up", "down"} <= labels
        for phase, count in (("decode", len(work.contexts) * work.steps), ("prefill", work.rows)):
            stage = compile_program(hw, work, plan, phase)
            assert stage.matrix_macs == count * per_token
            assert all((task.owner > 0) == (phase == "decode") for task in stage.tasks)
        writes = [t for t in p.tasks if t.label.startswith("append")]
        assert sum(t.accesses[0].words for t in writes) == 2 * (work.rows + len(work.contexts) * work.steps) * work.width // work.heads // 16


def test_trace_and_fast_evaluator_agree_for_complete_block():
    macros = {int(k): v for k, v in json.loads((ROOT / "results/sram_45nm_lstp.json").read_text())["macros"].items()}
    ledger = SystemLedger(json.loads((ROOT / "results/paid_ledger.json").read_text()))
    hw = ledger.price(DeepArchitecture(32, 64, 16, 65536, 1024, ddr_word_ns=4))
    work = Workload(19, (29, 37), 2, (200000, 0, 120000))
    for pin, online, resident in product((True, False), (True, False), (0, 7)):
        program = compile_program(hw, work, Plan(16, 128, resident, False, online, pin, 1))
        exact, fast = run(program, macros, record=True), run(program, macros)
        exact["trace"] = None
        assert exact == fast


def test_partial_kv_retention_saves_only_repeated_prefix_reads():
    macros = {int(k): v for k, v in json.loads((ROOT / "results/sram_45nm_lstp.json").read_text())["macros"].items()}
    hw = DeepArchitecture(32, 64, 16, 65536, 1024)
    work = Workload(19, (2049,), 2, (0, 0))
    cold = Plan(16, 128, 0, False, True, True, 1)
    cached = replace(cold, resident=2, cache_divisor=4)
    cold_result = run(compile_program(hw, work, cold), macros)
    cached_result = run(compile_program(hw, work, cached), macros)
    assert cold_result["actions"]["ddr_read"] - cached_result["actions"]["ddr_read"] == 2 * 512
    assert cold_result["actions"]["ddr_write"] == cached_result["actions"]["ddr_write"]


def test_decode_first_keeps_all_ties_after_common_feasibility_filter():
    def row(i, edp):
        return {"index": i, "best": None if edp is None else {"edp": edp}, "evaluated": int(edp is not None)}
    episode = [row(0, None), row(1, 10), row(2, 8), row(3, 7)]
    decode = [row(0, 1), row(1, 2), row(2, 2), row(3, 3)]
    result = summarize(episode, decode)
    assert result["unfiltered_decode_ties"] == [0]
    assert result["decode_ties"] == [1, 2]
    assert result["decode_first_edp"] == 8 and result["oracle_edp"] == 7
