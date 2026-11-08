"""Compare complete remapping and interleaved search on the same serving space."""

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, replace
import gzip
from heapq import merge
from itertools import groupby, product, zip_longest
import json
from math import ceil
from pathlib import Path
from random import Random
from time import perf_counter

from research.physical_cost.banked_scale import DeepArchitecture
from research.physical_cost.concurrent_serving import HEADS, WIDTH, Workload, compile_program, placement, plans
from research.physical_cost.external_ddr import SystemLedger
from research.physical_cost.serving_ddr import BURST, CK
from research.physical_cost.serving_trace import run
from research.runtime.strip_codesign import ceildiv


CASES = {
    "oracle": Workload(32, (41, 71), 2, (500_000, 0, 120_000)),
    "overlap": Workload(96, (500, 769), 3, (2_000_000, 0, 120_000)),
    "delayed": Workload(96, (500, 769), 3, (100_000_000, 0, 120_000)),
    "pressure": Workload(160, (769, 1211), 4, (8_000_000, 0, 160_000)),
}
METHODS = ("af_top2", "af_window", "af_complete", "joint")


def hardware_grid(macros, ledger, cap):
    candidates = (ledger.price(DeepArchitecture(x, mac // x, banks, bank_bytes, 1024, ddr_word_ns=4))
                  for mac, x, banks, bank_bytes in product((512, 1024, 2048, 4096), (8, 16, 32, 64),
                                                         (2, 3, 4, 6, 8, 10, 12, 16, 20, 24),
                                                         (16384, 65536)))
    return tuple(sorted(hw for hw in candidates if hw.total_area_mm2(macros) <= cap))


def traffic(work, mask):
    reads = 4 * WIDTH + work.rows + 2 * work.steps
    writes = work.rows + 12 * work.steps
    for req, context in enumerate(work.contexts):
        if mask & (1 << req):
            reads += 2 * context
        else:
            reads += work.steps * (2 * context + work.steps + 1)
    return reads, writes


def features(work, plan):
    reads, writes = traffic(work, plan.resident)
    tiles = Counter()
    for context, step in product(work.contexts, range(work.steps)):
        n = context + step + 1
        full, tail = divmod(n, plan.tile)
        tiles[plan.tile] += full
        if tail:
            tiles[tail] += 1
    scan = sum(n * count for n, count in tiles.items())
    blocks = sum(tiles.values())
    return reads, writes, tiles, scan, blocks


def proxy(hw, macros, work, plan, shape):
    """Rank using whole-episode traffic, feasible placements and tile costs."""
    reads, writes, tiles, scan, blocks = shape
    x, y = hw.x, hw.y
    stripe = ceildiv(WIDTH * ceildiv(WIDTH, x), 8)
    prefill_tiles = ceildiv(work.rows, plan.rows)
    projection = (work.rows + 6 * work.steps) * ceildiv(WIDTH, x) * ceildiv(WIDTH, y)
    projection += stripe * (work.rows + prefill_tiles + 12 * work.steps)
    qk = 0
    for n, count in tiles.items():
        local = ceildiv((WIDTH // HEADS) * ceildiv(n, x), 8)
        qk += count * HEADS * (ceildiv(n, x) * ceildiv(WIDTH // HEADS, y) + 2 * local)
    soft_ops = HEADS * (18 * scan + 24 * blocks) if plan.online else HEADS * 32 * scan
    av_ops = 8 * WIDTH * scan + (8 * (WIDTH + HEADS) * blocks if plan.online else 0)
    core = projection + qk + ceildiv(soft_ops, x) + ceildiv(av_ops, x * y)
    if plan.online:
        core += 2 * work.steps * ceildiv(16 * WIDTH, x)
    macro = macros[hw.global_bank_bytes]
    sram_period = ceil(max(macro["access_ns"], macro["cycle_ns"]))
    d_banks = hw.global_banks // 2 if plan.partition else hw.global_banks
    bank_work = ceildiv(2 * scan + reads + 8 * blocks, d_banks) * sram_period
    link = ceildiv(CK * (5 * reads + 18 * writes), 1000)
    # The late prefill arrival is known to both methods.
    elapsed = max(core, link, bank_work, max(work.arrivals_ps) // 1000) + min(core, link) // 2
    energy = (reads * hw.ddr_read_aj + writes * hw.ddr_write_aj
              + (soft_ops + av_ops + (work.rows + 6 * work.steps) * WIDTH**2 + WIDTH * scan) * 84_000
              + round(hw.standby_mw(macros) * elapsed * 1_000_000))
    return energy * elapsed


def prepare(hardware, macros, work):
    feasible = {}
    space = tuple((plan, features(work, plan)) for plan in plans())
    rows = []
    for i, hw in enumerate(hardware):
        mappings = []
        for plan, shape in space:
            key = hw.global_banks, hw.global_capacity, replace(plan, priority=0)
            if key not in feasible:
                feasible[key] = placement(hw, work, plan) is not None
            if feasible[key]:
                mappings.append((proxy(hw, macros, work, plan, shape), plan))
        if mappings:
            rows.append((i, sorted(mappings)))
    return sorted(rows, key=lambda row: (row[1][0][0], row[0]))


def candidates(rows, method, probes):
    if method == "joint":
        streams = []
        for index, mappings in rows:
            # Interleave hardware and mapping hypotheses. Penalize revisiting
            # one hardware slightly to diversify the early fine evaluations.
            streams.append([(score * (250 + rank), rank, index, plan)
                            for rank, (score, plan) in enumerate(mappings)])
        for _, _, index, plan in merge(*streams):
            yield index, plan
        return
    if method == "af_probe":
        cutoff = rows[min(7, len(rows) - 1)][1][0][0]
        for index, mappings in rows:
            if mappings[0][0] > cutoff:
                break
            yield index, mappings[0][1]
        # Rank the probed architectures by their measured anchor. The
        # remaining architectures stay in the queue in proxy order.
        probes = dict(probes)
        rows = sorted(rows, key=lambda row: (row[0] not in probes,
                      probes.get(row[0], row[1][0][0]), row[0]))
        rows = [(index, mappings[1:] if index in probes else mappings) for index, mappings in rows]
        rows = [row for row in rows if row[1]]
        group_key = lambda row: (row[0] not in probes, probes.get(row[0], row[1][0][0]))
    else:
        group_key = lambda row: row[1][0][0]
    for _, tied in groupby(rows, key=group_key):
        # Process all architectures tied at the boundary. A wall deadline can
        # interrupt a group, with no architecture removed from that group.
        group = [tuple((index, plan) for _, plan in mappings) for index, mappings in tied]
        for row in zip_longest(*group):
            yield from (item for item in row if item is not None)


def search(macros, ledger, cap, work, method, budgets, limit=None):
    start = perf_counter()
    hardware = hardware_grid(macros, ledger, cap)
    if limit:
        hardware = tuple(hardware[i * (len(hardware) - 1) // (limit - 1)] for i in range(limit))
    rows = prepare(hardware, macros, work)
    all_candidates = sum(len(mappings) for _, mappings in rows)
    all_architectures = len(rows)
    if method == "af_top2":
        cutoff = rows[min(1, len(rows) - 1)][1][0][0]
        rows = [row for row in rows if row[1][0][0] <= cutoff]
    elif method == "af_window":
        cutoff = rows[0][1][0][0]
        rows = [row for row in rows if row[1][0][0] * 10 <= cutoff * 11]
    ranked_at = perf_counter() - start
    available = {index: len(mappings) for index, mappings in rows}
    evaluated = Counter()
    best = None
    best_time = None
    history = []
    probes = {}
    probe_cutoff = rows[min(7, len(rows) - 1)][1][0][0] if method == "af_probe" else -1
    probe_indexes = {index for index, mappings in rows if mappings[0][0] <= probe_cutoff}
    generation_seconds = evaluation_seconds = 0.0
    deadline = max(budgets) if budgets else float("inf")
    for index, plan in candidates(rows, method, probes):
        before = perf_counter()
        if before - start >= deadline:
            break
        program = compile_program(hardware[index], work, plan)
        assert program is not None
        compiled_at = perf_counter()
        result = run(program, macros)
        done_at = perf_counter()
        generation_seconds += compiled_at - before
        evaluation_seconds += done_at - compiled_at
        elapsed = done_at - start
        if elapsed > deadline:
            break
        if index in probe_indexes and index not in probes:
            probes[index] = result["edp"]
        evaluated[index] += 1
        if best is None or result["edp"] < best["edp"]:
            best = {**result, "hardware": asdict(hardware[index]), "plan": asdict(plan), "index": index}
            best_time = elapsed
        history.append((elapsed, best["edp"], best["index"],
                        evaluated[index] == available[index]))
    wall = perf_counter() - start
    checkpoints = {}
    for budget in budgets:
        prefix = [row for row in history if row[0] <= budget]
        if prefix:
            checkpoints[str(budget)] = {"edp": prefix[-1][1], "index": prefix[-1][2],
                                        "evaluated": len(prefix), "complete_architectures": sum(r[3] for r in prefix)}
        else:
            checkpoints[str(budget)] = None
    return {"area_legal_architectures": len(hardware), "feasible_architectures": all_architectures,
            "feasible_candidates": all_candidates, "selected_architectures": list(available),
            "ranking_seconds": ranked_at, "wall_seconds": wall, "time_to_best": best_time,
            "mapping_generation_seconds": generation_seconds, "evaluation_seconds": evaluation_seconds,
            "evaluated": sum(evaluated.values()), "opened_architectures": len(evaluated),
            "ranking_probes": len(probes),
            "complete_architectures": sum(evaluated[i] == n for i, n in available.items()),
            "all_mappings_evaluated": all_candidates == sum(evaluated.values()),
            "checkpoints": checkpoints, "best": best}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sram", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=("overlap", "delayed", "pressure"))
    parser.add_argument("--methods", nargs="+", choices=(*METHODS, "af_probe"), default=METHODS)
    parser.add_argument("--budgets", type=float, nargs="+", default=(2, 5, 12))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--oracle-size", type=int, default=0)
    args = parser.parse_args()
    if min(args.budgets) <= 0 or args.repeats < 1 or args.oracle_size == 1 or args.oracle_size < 0:
        parser.error("Use positive budgets and repeats and at least two architectures for the oracle")
    macros = {int(k): v for k, v in json.loads(args.sram.read_text())["macros"].items()}
    ledger = SystemLedger(json.loads(args.ledger.read_text()))
    cap = ledger.reference_overhead() + 4.5
    report = {"area_cap_mm2": cap, "ddr_data_rate_gb_s": 19.2, "ddr_pricing_panel_gb_s": 16,
              "budgets": args.budgets, "cases": {}}
    for name in args.cases:
        work = CASES[name]
        cell = {"workload": asdict(work), "trials": []}
        report["cases"][name] = cell
        for repeat in range(args.repeats):
            order = list(args.methods)
            Random(repeat).shuffle(order)
            trial = {}
            for method in order:
                trial[method] = search(macros, ledger, cap, work, method, args.budgets)
                row = trial[method]
                print(name, repeat, method, row["evaluated"], row["complete_architectures"],
                      row["time_to_best"], row["best"]["edp"] if row["best"] else None, flush=True)
            cell["trials"].append(trial)
    if args.oracle_size:
        exact = search(macros, ledger, cap, CASES["oracle"], "af_complete", (), args.oracle_size)
        assert exact["all_mappings_evaluated"]
        report["small_oracle"] = exact
        print("small_oracle", exact["evaluated"], exact["best"]["edp"], flush=True)
    args.output.write_bytes(gzip.compress(json.dumps(report, indent=2).encode(), mtime=0))


if __name__ == "__main__":
    main()
