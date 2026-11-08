"""Isolate prefill/KV capacity, bank contention and idle leakage."""

import argparse
from dataclasses import asdict
import gzip
from itertools import product
import json
from pathlib import Path
from subprocess import check_output
import sys
from time import perf_counter

from research.physical_cost.banked_scale import DeepArchitecture
from research.physical_cost.concurrent_search import CASES
from research.physical_cost.concurrent_serving import Workload, compile_program, plans
from research.physical_cost.concurrent_validation import RAMULATOR_REVISION, replay
from research.physical_cost.external_ddr import SystemLedger
from research.physical_cost.serving_trace import run


NEAR_CAPACITY = Workload(192, (529, 829), 3, (18_000_000, 0, 120_000))
SHAPES = ((64, 32, 12, 16384), (64, 64, 3, 65536), (16, 64, 12, 16384), (32, 64, 4, 65536))
MODES = {
    "physical": (True, True),
    "capacity_only": (False, True),
    "ports_only": (True, False),
    "both": (False, False),
}
OBJECTIVES = ("edp", "without_idle_leakage_edp", "active_edp", "dynamic_edp")


def idle_ps(arrivals, completions):
    """Time with no outstanding request, including any initial gap."""
    done = idle = 0
    for start, stop in sorted(zip(arrivals, completions, strict=True)):
        assert stop >= start
        idle += max(0, start - done)
        done = max(done, stop)
    return idle


def leakage_breakdown(hw, macros, work, outcome):
    idle = idle_ps(work.arrivals_ps, outcome["request_completion_ps"])
    elapsed = outcome["elapsed_ps"]
    sram_idle = round(hw.sram_totals(macros, "leak_mw") * idle * 1000)
    phy_idle = round(hw.phy_idle_mw * idle * 1000)
    active_leakage = outcome["standby_aj"] - sram_idle - phy_idle
    assert 0 <= active_leakage <= outcome["standby_aj"]
    active = outcome["dynamic_aj"] + active_leakage
    return {"idle_ps": idle, "idle_sram_leakage_aj": sram_idle, "idle_phy_aj": phy_idle,
            "active_standby_aj": active_leakage,
            "without_idle_leakage_edp": active * elapsed, "active_edp": active * (elapsed - idle),
            "dynamic_edp": outcome["dynamic_aj"] * elapsed}


def remap(hw, macros, work, device, modes):
    start = perf_counter()
    rows = {name: {"candidates": 0, "best": {}} for name in modes}
    for plan in plans(work):
        program = compile_program(hw, work, plan, share_capacity=False)
        if program is None:
            continue
        physical = max(program.used) * 64 <= hw.global_capacity
        for ports in sorted({m[1] for m in modes.values()}):
            eligible = [name for name, (capacity, shared) in modes.items()
                        if shared == ports and (physical or not capacity)]
            if not eligible:
                continue
            result = run(program, macros, share_ports=ports, track_requests=True)
            result.update(leakage_breakdown(hw, macros, work, result))
            for name in eligible:
                row = rows[name]
                row["candidates"] += 1
                for objective in OBJECTIVES:
                    incumbent = row["best"].get(objective)
                    if incumbent is None or (result[objective], plan) < (incumbent[1][objective], incumbent[0]):
                        row["best"][objective] = plan, result

    for name, row in rows.items():
        capacity, ports = modes[name]
        plan, result = row["best"]["edp"]
        audit = replay(macros, work, hw, plan, device, share_capacity=capacity, share_ports=ports)
        assert audit["result"]["edp"] == result["edp"]
        assert audit["oracle"]["completion_by_request_ps"] == result["request_completion_ps"]
        assert ports or audit["oracle"]["cross_side_port_waits"] == 0
        physical_plan = rows["physical"]["best"]["edp"][0]
        program = compile_program(hw, work, physical_plan)
        common = run(program, macros, share_ports=ports, track_requests=True)
        common.update(leakage_breakdown(hw, macros, work, common))
        # A feasible physical plan is byte-identical when only the cap is relaxed.
        assert common["actions"] == rows["physical"]["best"]["edp"][1]["actions"]
        if ports:
            assert common == rows["physical"]["best"]["edp"][1]
        row["physical_winner_replay"] = common
        row["oracle"] = audit["oracle"]
    for row in rows.values():
        row["best"] = {objective: {"plan": asdict(plan), **result}
                       for objective, (plan, result) in row["best"].items()}
    return {"hardware": asdict(hw), "area_mm2": hw.total_area_mm2(macros),
            "seconds": perf_counter() - start, "modes": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sram", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("ramulator_checkout", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    revision = check_output(["git", "-C", args.ramulator_checkout, "rev-parse", "HEAD"], text=True).strip()
    if revision != RAMULATOR_REVISION:
        parser.error(f"Expected Ramulator revision {RAMULATOR_REVISION}, found {revision}")
    sys.path.insert(0, str(args.ramulator_checkout / "python"))
    from ramulator.dram import DDR4

    macros = {int(k): v for k, v in json.loads(args.sram.read_text())["macros"].items()}
    ledger = SystemLedger(json.loads(args.ledger.read_text()))
    cap = ledger.reference_overhead() + 4.5
    device = DDR4(org_preset="DDR4_8Gb_x8", timing_preset="DDR4_2400R", rank=1)
    hardware = [ledger.price(DeepArchitecture(*shape, 1024, ddr_word_ns=4)) for shape in SHAPES]
    assert all(hw.total_area_mm2(macros) <= cap for hw in hardware)
    report = {"area_cap_mm2": cap, "ramulator_revision": revision, "cases": {}}
    for name, work in (("overlap", CASES["overlap"]), ("near_capacity", NEAR_CAPACITY),
                       ("delayed", CASES["delayed"])):
        modes = MODES if name != "delayed" else {"physical": MODES["physical"]}
        results = []
        for hw in hardware:
            result = remap(hw, macros, work, device, modes)
            results.append(result)
            print(name, hw.x, hw.y, hw.global_banks, result["seconds"],
                  [row["best"]["edp"]["edp"] for row in result["modes"].values()], flush=True)
        report["cases"][name] = {"workload": asdict(work), "architectures": results}
    args.output.write_bytes(gzip.compress(json.dumps(report, indent=2).encode(), mtime=0))


if __name__ == "__main__":
    main()
