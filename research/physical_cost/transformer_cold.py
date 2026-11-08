"""Fresh equal-budget block remapping with the same feasibility check on both sides."""

import argparse
from hashlib import sha256
import multiprocessing as mp
from pathlib import Path
from time import monotonic

from research.physical_cost.serving_exhaustive import limit_memory, write_atomic
from research.physical_cost.transformer_boundary import cases, setup, ties
from research.physical_cost.transformer_parallel import collect
from research.physical_cost.transformer_serving import Plan, placement


def feasible(hw, work):
    # For a fixed pin/layout choice, rows=16, tile=128, no KV retention
    # and online scores minimize every reservation in this grammar. The
    # allocator always stripes each region from its first bank, so larger
    # reservations cannot reduce any bank's occupancy. Test all four layouts.
    return any(placement(hw, work, Plan(16, 128, 0, part, True, pin, 0)) is not None
               for part in (False, True) for pin in (False, True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sram", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, default=18)
    parser.add_argument("--memory-gib", type=int, default=12)
    parser.add_argument("--budget", type=float, default=900)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--cases", nargs="+")
    args = parser.parse_args()
    limit_memory(args.memory_gib * 2**30, args.workers)
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"budget_seconds": args.budget, "workers": args.workers, "trials": [],
              "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "timing_claim": "completion within a common cap; no speedup claim from one repetition"}
    for name, work in cases():
        if args.cases and name not in args.cases:
            continue
        for repeat in range(args.repeats):
            for method in (("decode-first", "episode-sweep") if repeat % 2 == 0 else ("episode-sweep", "decode-first")):
                start = monotonic()
                hardware, macros, manifest = setup(args.sram, args.ledger)
                legal = [i for i, h in enumerate(hardware) if feasible(h, work)]
                generated = monotonic() - start
                directory = args.output / f"{name}-{repeat}-{method}"
                directory.mkdir(exist_ok=True)
                with mp.get_context("spawn").Pool(args.workers) as pool:
                    decoded, selected = [], legal
                    if method == "decode-first":
                        decoded = collect(pool, [(i, hardware[i], work, macros, "decode") for i in legal],
                                          directory, start + args.budget, resume=False)
                        selected = ties(decoded)
                    mapped = collect(pool, [(i, hardware[i], work, macros, "episode") for i in selected],
                                     directory, start + args.budget, resume=False)
                minimum = min(row["best"]["edp"] for row in mapped if row["best"])
                row = {"case": name, "repeat": repeat, "method": method, "edp": minimum,
                       "wall_seconds": monotonic() - start, "area_legal": len(hardware),
                       "episode_feasible": legal, "selected_architectures": selected,
                       "completed_remaps": len(mapped), "selection_and_feasibility_seconds": generated,
                       "generation_worker_seconds": sum(r["generation_seconds"] for r in decoded + mapped),
                       "generated": sum(r["generated"] for r in decoded + mapped),
                       "evaluated": sum(r["evaluated"] for r in decoded + mapped),
                       "space_sha256": manifest["space_sha256"], "evaluator_sha256": manifest["evaluator_sha256"]}
                assert row["wall_seconds"] <= args.budget
                report["trials"].append(row)
                write_atomic(args.output / "cold.json.gz", report)
                print(name, "COLD", method, row["wall_seconds"], minimum, flush=True)


if __name__ == "__main__":
    main()
