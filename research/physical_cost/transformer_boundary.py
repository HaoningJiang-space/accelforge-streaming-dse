"""Frozen full-block boundary panels; exhaustive remapping, no new search rule."""

import argparse
from dataclasses import asdict
import gzip
from hashlib import sha256
import json
import multiprocessing as mp
import os
from pathlib import Path
from time import monotonic, perf_counter

from research.physical_cost.serving_exhaustive import inputs, limit_memory, write_atomic
from research.physical_cost.serving_trace import run
from research.physical_cost.transformer_serving import Workload, Plan, compile_program, placement, plans


def cases():
    for context in (8192, 12288):
        for requests in (4, 6):
            for kind in ("prefill", "decode"):
                yield f"c{context}-n{requests}-{kind}", Workload(
                    512 if kind == "prefill" else 64,
                    tuple(context + 17 * j for j in range(requests)),
                    1 if kind == "prefill" else 4,
                    (2_000_000, *(j * 120_000 for j in range(requests))))


def setup(sram, ledger):
    hardware, macros, manifest = inputs(sram, ledger)
    assert manifest["device"] == "itrs-lstp"
    hardware = tuple(h for h in hardware if h.x in (16, 32, 64) and h.x * h.y in (1024, 2048, 4096)
                     and h.global_banks in (4, 8, 12, 16, 24))
    manifest["space_sha256"] = sha256(repr(hardware).encode()).hexdigest()
    for name in ("transformer_serving.py", "transformer_boundary.py"):
        manifest["evaluator_sha256"][name] = sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
    manifest["hardware"] = [asdict(h) for h in hardware]
    manifest["grammar"] = "rows16/32,tile128/512,all residency masks,decode cache full/quarter/eighth prefixes,partition,online/dense,pin/stream,priority0/1; legal phase-buffer reuse"
    return hardware, macros, manifest


def evaluate(task):
    index, hw, work, macros, phase = task
    start = perf_counter()
    best, ties, visited, feasible = None, [], 0, 0
    evaluator_seconds = 0.0
    for plan in plans(work, phase):
        visited += 1
        program = compile_program(hw, work, plan, phase)
        if program is None:
            continue
        begin = perf_counter()
        outcome = run(program, macros, track_requests=True)
        evaluator_seconds += perf_counter() - begin
        feasible += 1
        if best is None or outcome["edp"] < best["edp"]:
            best = {**outcome, "plan": asdict(plan)}
            ties = [asdict(plan)]
        elif outcome["edp"] == best["edp"]:
            ties.append(asdict(plan))
    seconds = perf_counter() - start
    return {"index": index, "phase": phase, "generated": visited, "evaluated": feasible,
            "best": best, "tied_plans": ties, "wall_seconds": seconds,
            "generation_seconds": seconds - evaluator_seconds, "evaluator_seconds": evaluator_seconds}


def collect(pool, tasks, output, deadline, *, resume=True):
    rows, pending = {}, []
    for task in tasks:
        i, *_, phase = task
        path = output / f"{phase}-{i}.json.gz"
        if resume and path.exists():
            with gzip.open(path, "rt") as stream:
                rows[i] = json.load(stream)
        else:
            pending.append(task)
    # Static submission order only; no score, bound, or selective evaluation.
    results = pool.imap_unordered(evaluate, pending)
    count = len(rows) + len(pending)
    while len(rows) < count:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Only {len(rows)}/{count} complete architectures in {output}")
        try:
            row = results.next(timeout=min(remaining, 1.0))
        except mp.TimeoutError:
            continue
        rows[row["index"]] = row
        write_atomic(output / f"{row['phase']}-{row['index']}.json.gz", row)
        print(output.name, row["phase"], len(rows), "/", count, "pairs", row["evaluated"], flush=True)
    return [rows[i] for i in sorted(rows)]


def ties(rows):
    legal = [r for r in rows if r["best"] is not None]
    if not legal:
        return []
    best = min(row["best"]["edp"] for row in legal)
    return [row["index"] for row in legal if row["best"]["edp"] == best]


def summarize(episode, decode):
    # Strong stage-first may inspect the common episode's feasibility. It is
    # not forced to select an architecture that cannot execute the workload.
    feasible = {row["index"] for row in episode if row["best"] is not None}
    shared, selected = ties(episode), ties([row for row in decode if row["index"] in feasible])
    lookup = {r["index"]: r for r in episode}
    remapped = [lookup[i] for i in selected if lookup[i]["best"] is not None]
    best = min(r["best"]["edp"] for r in episode if r["best"])
    baseline = min((r["best"]["edp"] for r in remapped), default=None)
    return {"episode_winners": shared, "decode_ties": selected, "unfiltered_decode_ties": ties(decode),
            "decode_episode_ties": ties(remapped), "oracle_edp": best,
            "decode_first_edp": baseline, "regret": None if baseline is None else baseline / best - 1,
            "episode_pairs": sum(r["evaluated"] for r in episode),
            "decode_pairs": sum(r["evaluated"] for r in decode)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sram", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--memory-gib", type=int, default=12)
    parser.add_argument("--seconds", type=float, default=7200)
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--cold-repeats", type=int, default=0)
    parser.add_argument("--method-seconds", type=float, default=1800)
    args = parser.parse_args()
    assert 0 < args.workers <= (os.cpu_count() or 1) and args.seconds > 0
    limit_memory(args.memory_gib * 2**30, args.workers)
    deadline = monotonic() + args.seconds
    hardware, macros, manifest = setup(args.sram, args.ledger)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, work in cases():
        if args.cases and name not in args.cases:
            continue
        out = args.output / name
        out.mkdir(exist_ok=True)
        config = {**manifest, "workload": json.loads(json.dumps(asdict(work)))}
        stamp = out / "manifest.json"
        if stamp.exists() and json.loads(stamp.read_text()) != config:
            raise ValueError("Checkpoint source or workload differs")
        write_atomic(stamp, config)
        reference = {}
        with mp.get_context("spawn").Pool(args.workers) as pool:
            for phase in ("episode", "decode"):
                begin = monotonic()
                tasks = [(i, h, work, macros, phase) for i, h in enumerate(hardware)]
                reference[phase] = collect(pool, tasks, out, deadline)
                reference[phase + "_seconds_this_run"] = monotonic() - begin
        summary = summarize(reference["episode"], reference["decode"])
        report = {**config, "reference": reference, "summary": summary}
        write_atomic(args.output / f"{name}.json.gz", report)
        print(name, "EXACT", summary, flush=True)
        if args.cold_repeats:
            report["cold_trials"] = []
            for repeat in range(args.cold_repeats):
                for method in (("decode-first", "episode-sweep") if repeat % 2 == 0 else ("episode-sweep", "decode-first")):
                    directory = out / f"trial-{repeat}-{method}"
                    directory.mkdir(exist_ok=True)
                    start = monotonic()
                    # No profiles, references or candidate caches from above are used.
                    hws, costs, _ = setup(args.sram, args.ledger)
                    until = min(deadline, start + args.method_seconds)
                    with mp.get_context("spawn").Pool(args.workers) as pool:
                        chosen = range(len(hws))
                        decoding = []
                        if method == "decode-first":
                            # Include generation/placement in the cold-start clock;
                            # no episode objective from the reference may leak in.
                            feasible = [i for i, h in enumerate(hws)
                                        if any(placement(h, work, p) is not None for p in plans(work))]
                            decoding = collect(pool, [(i, h, work, costs, "decode") for i, h in enumerate(hws)],
                                               directory, until, resume=False)
                            chosen = ties([r for r in decoding if r["index"] in feasible])
                        remaps = collect(pool, [(i, hws[i], work, costs, "episode") for i in chosen],
                                         directory, until, resume=False)
                    best = min((r["best"]["edp"] for r in remaps if r["best"]), default=None)
                    trial = {"repeat": repeat, "method": method, "budget_seconds": args.method_seconds,
                             "wall_seconds": monotonic() - start, "edp": best, "selected_architectures": list(chosen),
                             "completed_remaps": len(remaps), "evaluated": sum(r["evaluated"] for r in decoding + remaps),
                             "generation_worker_seconds": sum(r["generation_seconds"] for r in decoding + remaps)}
                    report["cold_trials"].append(trial)
                    write_atomic(args.output / f"{name}.json.gz", report)
                    print(name, "COLD", trial, flush=True)


if __name__ == "__main__":
    main()
