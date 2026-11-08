from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

import pytest

from research.physical_cost.banked_oracle import addresses, audit
from research.physical_cost.banked_scale import (
    DeepArchitecture, Evaluator, breakpoints, catalog, certify_families, measure,
)
from research.physical_cost.banked_search import estimate, run_search
from research.physical_cost.banked_serving import (
    Access, Command, Life, Mapping, Program, Region, Workload, build, dispatch, mappings, price,
)
from research.physical_cost.mixed_gate import Architecture
from research.physical_cost.paid_area import PaidArchitecture


MACROS = {int(k): v for k, v in json.loads(
    (Path(__file__).parents[1] / "results/sram_45nm.json").read_text()
)["macros"].items()}
HW = Architecture(64, 32, 2, 65536, 1024)
WORK = Workload(rows=16, inner=64, columns=32, context=128, steps=2, decode_tile=64)
PLAN = Mapping(8, 16, 2, True, "striped", "P")


def test_a_single_read_port_serializes_two_reads_but_allows_a_write():
    def length(other_bank, direction):
        regions = {"a": Region((0,), (0,), 1), "b": Region((other_bank,), (1,), 1)}
        commands = [Command("P", "read", (), (Access("a", 0, 1, "r"),)),
                    Command("D", "move", (), (Access("b", 0, 1, direction),))]
        program = Program(HW, WORK, PLAN, regions, commands, [])
        _, ticks, _, waits = dispatch(program, price(program, MACROS))
        return ticks, waits

    assert length(0, "r") == (2, 1)
    assert length(1, "r") == (1, 0)
    assert length(0, "w") == (1, 0)


def test_resident_kv_is_live_during_prefill_and_rejects_aliasing():
    program = build(HW, WORK, PLAN)
    costs = price(program, MACROS)
    value, elapsed, starts, _ = dispatch(program, costs)
    independently = audit(program, MACROS, starts)
    assert (independently["edp"], independently["ns"]) == (value, elapsed)
    assert independently["kv_prefill_co_resident_ns"] > 0
    p = program.regions["P0"]
    aliases = {**program.regions, "P0": replace(p, starts=program.regions["KV"].starts)}
    with pytest.raises(AssertionError, match="Overlapping live SRAM allocations"):
        audit(replace(program, regions=aliases), MACROS, starts)


def test_word_oracle_rejects_conflicts_and_same_word_read_write():
    regions = {"a": Region((0,), (0,), 1), "b": Region((0,), (1,), 1)}
    write_a = Command("P", "write", (), (Access("a", 0, 1, "w"),))
    write_b = Command("D", "write", (), (Access("b", 0, 1, "w"),))
    conflict = Program(HW, WORK, PLAN, regions, [write_a, write_b], [])
    with pytest.raises(AssertionError, match="Port conflict"):
        audit(conflict, MACROS, [0, 0])

    read_a = Command("D", "read", (0,), (Access("a", 0, 1, "r"),))
    alias = Program(HW, WORK, PLAN, regions, [write_a, read_a, write_a], [Life("a", 0, 2)])
    with pytest.raises(AssertionError, match="Simultaneous read and write"):
        audit(alias, MACROS, [0, 1, 1])


def test_one_fewer_line_makes_the_same_mapping_infeasible():
    program = build(HW, WORK, PLAN)
    end = max(row for region in program.regions.values()
              for _, row in addresses(region, 0, region.words)) + 1
    assert build(replace(HW, global_bank_bytes=end * 64), WORK, PLAN) is not None
    assert build(replace(HW, global_bank_bytes=(end - 1) * 64), WORK, PLAN) is None


def test_complete_value_reservation_is_addressed_and_cannot_release_early():
    work = replace(WORK, reserve_values=True)
    program = build(HW, work, PLAN)
    costs = price(program, MACROS)
    value, _, starts, _ = dispatch(program, costs)
    replay = audit(program, MACROS, starts)
    assert replay["edp"] == value >= estimate(HW, work, PLAN, MACROS)[0]
    assert replay["resident_value_bytes"] == work.context * work.head
    assert replay["full_kv_prefill_co_resident_ns"] == replay["kv_prefill_co_resident_ns"] > 0
    key = next(life for life in program.lives if life.slot == "KV")
    released = [replace(life, last=key.last) if life.slot == "V" else life for life in program.lives]
    with pytest.raises(AssertionError, match="complete value cache"):
        audit(replace(program, lives=released), MACROS, starts)


def test_exhaustive_tiny_domain_agrees_with_both_complete_searches():
    hardware = (HW, Architecture(32, 64, 4, 16384, 1024),
                replace(HW, weight_bytes_per_stripe=4096))
    exhaustive = []
    for h in hardware:
        for mapping in mappings():
            lower = estimate(h, WORK, mapping, MACROS)
            program = build(h, WORK, mapping)
            assert (program is None) == (lower is None)
            if program is None:
                continue
            costs = price(program, MACROS)
            assert lower[1] == costs.dynamic
            value, _, _, _ = dispatch(program, costs)
            assert value >= lower[0]
            exhaustive.append(value)
    for method in ("joint", "sweep", "binding", "grouped_sweep", "critical_joint"):
        result = run_search(hardware, WORK, MACROS, method)
        assert result["edp_aj_ns"] == min(exhaustive)
        if method == "critical_joint":
            assert result["critical_probes"] == 4 * len(hardware)
        if method in ("binding", "grouped_sweep"):
            assert result["candidates_dominated"] > 0


def test_scaled_shortlist_intervals_and_breakpoints_against_exhaustion():
    work = replace(WORK, reserve_values=True)
    base = DeepArchitecture(64, 32, 2, 16384, 1024)
    hardware = (base, replace(base, global_depth=2), replace(base, private_depth=2),
                replace(base, x=32, y=64, global_banks=4, global_bank_bytes=65536),
                replace(base, y=64), replace(base, y=128), replace(base, ddr_word_ns=4))
    plans = tuple(m for m in mappings() if m.resident and m.prefer == "P")
    reference = min(dispatch(program, price(program, MACROS))[0]
                    for hw in hardware for plan in plans for prefer in ("P", "D")
                    if (program := build(hw, work, replace(plan, prefer=prefer))) is not None)
    rows, _ = catalog(hardware, work, MACROS, plans)
    evaluator = Evaluator(work, MACROS, plans, rows)
    more_mac, saturated_mac, slow_ddr = hardware[-3:]
    assert rows[more_mac].timing == rows[saturated_mac].timing
    assert rows[base].timing != rows[more_mac].timing
    assert rows[base].timing != rows[slow_ddr].timing
    for hw in (base, more_mac, saturated_mac, slow_ddr):
        index = plans.index(PLAN)
        program = build(hw, work, PLAN)
        edp, elapsed, starts, _ = dispatch(program, price(program, MACROS))
        assert evaluator.schedule_time(hw, index, "P") == elapsed
        assert audit(program, MACROS, starts)["edp"] == edp
    assert len(breakpoints(hardware, rows)) < len(hardware)
    assert evaluator.exact(hardware)[0] == reference
    assert evaluator.joint(hardware, float("inf"), None, lambda score, plan: None)[0] == reference
    assert certify_families(evaluator, hardware, reference)[0]
    assert not certify_families(evaluator, hardware, reference + 1)[0]
    result = measure(hardware, rows, evaluator, {hw: evaluator.critical_score(hw) for hw in hardware})
    assert result["exact_edp"] == reference
    for item in result["shortlists"].values():
        assert item["certificate_lower"] <= reference <= item["edp"]
        if item["certified"]:
            assert item["edp"] == reference


def test_paid_ddr_read_write_and_idle_costs_reach_the_bound_and_replay():
    base = PaidArchitecture(64, 32, 2, 65536, 1024)
    paid = replace(base, ddr_read_aj=base.ddr_read_aj + 11, ddr_write_aj=base.ddr_write_aj + 29,
                   phy_idle_mw=7.0)
    program = build(paid, WORK, PLAN)
    costs = price(program, MACROS)
    score, _, starts, _ = dispatch(program, costs)
    original = price(build(base, WORK, PLAN), MACROS)
    transfers = Counter()
    for command in program.commands:
        if command.kind == "dma":
            for access in command.accesses:
                transfers[access.direction] += sum(count for bank, count in
                    program.regions[access.slot].counts(access.first, access.words) if bank == access.bank)
    assert costs.dynamic - original.dynamic == 11 * transfers["w"] + 29 * transfers["r"]
    assert costs.leak - original.leak == 7_000_000
    assert estimate(paid, WORK, PLAN, MACROS)[1] == costs.dynamic
    assert audit(program, MACROS, starts)["edp"] == score
