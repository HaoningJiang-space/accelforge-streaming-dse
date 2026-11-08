"""Replay serving winners with independent word and DDR command checks."""

import argparse
from dataclasses import asdict, replace
import gzip
from itertools import product
import json
from pathlib import Path
from random import Random
from subprocess import check_output
import sys
from time import perf_counter

import numpy as np

from research.physical_cost.banked_scale import DeepArchitecture
from research.physical_cost.concurrent_search import CASES, hardware_grid, traffic
from research.physical_cost.concurrent_serving import HEADS, WIDTH, Plan, Workload, compile_program, placement, plans
from research.physical_cost.external_ddr import SystemLedger
from research.physical_cost.paid_area import PaidArchitecture
from research.physical_cost.serving_ddr import DDR
from research.physical_cost.serving_ddr_oracle import check
from research.physical_cost.serving_oracle import verify
from research.physical_cost.serving_softmax import dense, online
from research.physical_cost.serving_trace import run


RAMULATOR_REVISION = "7bead6cb7c4b03e095c6d4769ae3181a8e0bf6da"


def numerical(work, tile):
    rng = np.random.default_rng(710)
    error = 0.0
    count = 0
    for context in work.contexts:
        keys = rng.integers(-12, 13, (context + work.steps, HEADS, WIDTH // HEADS))
        values = rng.integers(-32, 33, keys.shape)
        queries = rng.integers(-12, 13, (work.steps, *keys.shape[1:]))
        for step, head in product(range(work.steps), range(HEADS)):
            stop = context + step + 1
            q, k, v = queries[step, head], keys[:stop, head], values[:stop, head]
            scores = k @ q / np.sqrt(k.shape[1])
            weights = np.exp(scores - scores.max())
            reference = weights @ v / weights.sum()
            for actual in (dense(q.tolist(), k.tolist(), v.tolist()),
                           online(q.tolist(), k.tolist(), v.tolist(), tile)):
                error = max(error, float(np.max(np.abs(reference - actual))))
                np.testing.assert_allclose(actual, reference, atol=1e-11, rtol=1e-11)
                count += 1
    return {"vectors_compared": count, "max_absolute_error": error}


def replay(macros, work, hw, plan, device, *, share_capacity=True, share_ports=True):
    program = compile_program(hw, work, plan, share_capacity=share_capacity)
    assert program is not None
    result = run(program, macros, record=True, share_ports=share_ports)
    summary = verify(program, work, result, device, macros, share_ports=share_ports)
    measured = result["actions"]
    assert traffic(work, plan.resident) == (measured["ddr_read"], measured["ddr_write"])
    del result["trace"]
    assert result == {k: v for k, v in run(program, macros, share_ports=share_ports).items() if k != "trace"}
    return {"workload": asdict(work), "hardware": asdict(hw), "plan": asdict(plan),
            "result": result, "oracle": summary}


def ddr_test(device):
    known = DDR(record=True)
    begin, end = known.burst(0, False, 0)
    assert (begin, end) == (26_656, 29_988)
    assert check(known.trace, device) == [(0, "RD", begin, end)]
    bad = [known.trace[0], replace(known.trace[1], cycle=known.trace[1].cycle - 1)]
    try:
        check(bad, device)
    except AssertionError:
        pass
    else:
        raise AssertionError("The command checker accepted an early read")
    rng = Random(6)
    mixed = DDR(record=True)
    expected = []
    for i in range(5000):
        address = rng.randrange(20000)
        write = rng.random() < 0.2
        expected.append((address, "WR" if write else "RD", *mixed.burst(address, write, 25000 * i)))
    assert check(mixed.trace, device) == expected
    return {"closed_row_first_ps": begin, "closed_row_last_ps": end, "commands": mixed.counts}


def remap_witnesses(macros, device, winners):
    """Remap the same witnessed architectures at both arrival spacings."""
    cases = ("overlap", "delayed")
    hardware = sorted({hw for name, hw, _ in winners if name in cases})
    result = []
    for name, hw in product(cases, hardware):
        work = CASES[name]
        best = None
        count = 0
        start = perf_counter()
        for plan in plans(work):
            program = compile_program(hw, work, plan)
            if program is None:
                continue
            outcome = run(program, macros)
            count += 1
            point = (outcome["edp"], plan)
            if best is None or point < best:
                best = point
        elapsed = perf_counter() - start
        summary = replay(macros, work, hw, best[1], device)
        assert summary["result"]["edp"] == best[0]
        result.append({"case": name, "candidates": count, "seconds": elapsed, **summary})
    return result


def exact_coverage(exact, hardware, macros, device, search_reports):
    name = exact["case"]
    work = CASES[name]
    grammar = tuple(plans(work))
    assert exact["workload"] == json.loads(json.dumps(asdict(work)))
    minima = {}
    evaluated = 0
    for index, (hw, row) in enumerate(zip(hardware, exact["architectures"], strict=True)):
        assert row["index"] == index and row["hardware"] == asdict(hw)
        count = sum(placement(hw, work, plan) is not None for plan in grammar)
        assert count == row["evaluated"]
        evaluated += count
        if count:
            minima[index] = row["best"]["edp"]
    assert (len(minima), evaluated) == (exact["feasible_architectures"], exact["evaluated"])
    optimum = min(minima.values())
    winners = [index for index, score in minima.items() if score == optimum]
    assert (optimum, winners) == (exact["best_edp"], exact["optimal_architectures"])
    replays = []
    for index in winners:
        best = exact["architectures"][index]["best"]
        audited = replay(macros, work, hardware[index], Plan(**best["plan"]), device)
        assert audited["result"]["edp"] == optimum
        replays.append(audited)
    comparison = {}
    for label, search in search_reports.items():
        if name not in search["cases"]:
            continue
        methods = {}
        for trial in search["cases"][name]["trials"]:
            for method, row in trial.items():
                if row["best"] is None:
                    continue
                incumbent = row["best"]
                assert incumbent["edp"] >= minima[incumbent["index"]]
                assert row["feasible_candidates"] == evaluated
                by_deadline = {budget: (None if value is None else value["edp"] / optimum - 1)
                               for budget, value in row["checkpoints"].items()}
                assert all(value is None or value >= 0 for value in by_deadline.values())
                methods.setdefault(method, []).append(by_deadline)
        comparison[label] = methods
    return {"evaluated": evaluated, "best_edp": optimum, "optimal_architectures": winners,
            "winner_replays": replays, "budget_regret": comparison}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sram", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("ramulator_checkout", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--search-results", type=Path, nargs="+")
    parser.add_argument("--exact-results", type=Path, nargs="+")
    parser.add_argument("--remap-witnesses", action="store_true")
    args = parser.parse_args()
    revision = check_output(["git", "-C", args.ramulator_checkout, "rev-parse", "HEAD"], text=True).strip()
    if revision != RAMULATOR_REVISION:
        parser.error(f"Expected Ramulator revision {RAMULATOR_REVISION}, found {revision}")
    sys.path.insert(0, str(args.ramulator_checkout / "python"))
    from ramulator.dram import DDR4

    macros = {int(k): v for k, v in json.loads(args.sram.read_text())["macros"].items()}
    ledger = SystemLedger(json.loads(args.ledger.read_text()))
    device = DDR4(org_preset="DDR4_8Gb_x8", timing_preset="DDR4_2400R", rank=1)
    hw = ledger.price(DeepArchitecture(16, 64, 6, 16384, 1024, ddr_word_ns=4))
    work = Workload(64, (75, 128), 3, (2_000_000, 0, 120_000))
    checks = [replay(macros, work, hw, Plan(16, 32, 2, mask, partition, stream, 1), device)
              for stream, mask, partition in product((False, True), range(4), (False, True))]
    numeric = {f"{name}/{tile}": numerical(case, tile)
               for name, case in CASES.items() for tile in (32, 96)}
    report = {"ramulator_revision": RAMULATOR_REVISION, "ddr": ddr_test(device),
              "numeric": numeric, "paired_layouts": checks}
    seen = {}
    search_reports = {}
    for path in args.search_results or ():
        with gzip.open(path, "rt") as file:
            search_results = json.load(file)
        search_reports[path.name] = search_results
        for name, cell in search_results["cases"].items():
            for trial in cell["trials"]:
                for row in trial.values():
                    best = row["best"]
                    if best is None:
                        continue
                    h, p = PaidArchitecture(**best["hardware"]), Plan(**best["plan"])
                    key = name, h, p
                    if key not in seen:
                        seen[key] = replay(macros, CASES[name], h, p, device)
                    assert seen[key]["result"]["edp"] == best["edp"]
        if "small_oracle" in search_results:
            best = search_results["small_oracle"]["best"]
            h, p = PaidArchitecture(**best["hardware"]), Plan(**best["plan"])
            key = "oracle", h, p
            if key not in seen:
                seen[key] = replay(macros, CASES["oracle"], h, p, device)
            assert seen[key]["result"]["edp"] == best["edp"]
    report["verified_winners"] = list(seen.values())
    if args.exact_results:
        hardware = hardware_grid(macros, ledger, ledger.reference_overhead() + 4.5)
        report["exact"] = {}
        for path in args.exact_results:
            with gzip.open(path, "rt") as file:
                exact = json.load(file)
            report["exact"][exact["case"]] = exact_coverage(exact, hardware, macros, device, search_reports)
            print("exact coverage verified", exact["case"], exact["evaluated"], flush=True)
    if args.remap_witnesses:
        if not args.search_results:
            parser.error("Witness remapping requires search results")
        report["remapped_witnesses"] = remap_witnesses(macros, device, seen)
    args.output.write_bytes(gzip.compress(json.dumps(report, indent=2).encode(), mtime=0))
    print("verified", len(checks), "paired layouts and", len(report.get("verified_winners", [])), "search winners")


if __name__ == "__main__":
    main()
