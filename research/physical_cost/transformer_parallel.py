"""Shard exhaustive mappings equally across workers, without pruning or ranking."""

from collections import defaultdict
import gzip
from hashlib import sha256
from itertools import islice
import json
import multiprocessing as mp
from pathlib import Path
from time import monotonic

from research.physical_cost import transformer_boundary as boundary
from research.physical_cost.transformer_serving import Plan


SHARDS = 3


def evaluate_shard(task):
    original = boundary.plans
    shard, total, base = task
    try:
        boundary.plans = lambda work, phase: islice(original(work, phase), shard, None, total)
        row = boundary.evaluate(base)
        return shard, row
    finally:
        boundary.plans = original


def combine(parts):
    best = [row for row in parts if row["best"] is not None]
    row = {k: parts[0][k] for k in ("index", "phase")}
    for field in ("generated", "evaluated", "wall_seconds", "generation_seconds", "evaluator_seconds"):
        row[field] = sum(p[field] for p in parts)
    row["best"], row["tied_plans"] = None, []
    if best:
        value = min(p["best"]["edp"] for p in best)
        best = [p for p in best if p["best"]["edp"] == value]
        row["best"] = min((p["best"] for p in best), key=lambda b: Plan(**b["plan"]))
        row["tied_plans"] = [p for b in best for p in b["tied_plans"]]
    row["shards"] = len(parts)
    return row


def collect(pool, tasks, output, deadline, *, resume=True):
    rows, pending = {}, []
    parts = defaultdict(dict)
    for task in tasks:
        i, *_, phase = task
        path = output / f"{phase}-{i}.json.gz"
        if resume and path.exists():
            rows[i] = json.loads(gzip.decompress(path.read_bytes()))
        else:
            pending.extend((shard, SHARDS, task) for shard in range(SHARDS))
    count = len(rows) + len(pending) // SHARDS
    results = pool.imap_unordered(evaluate_shard, pending)
    while len(rows) < count:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Only {len(rows)}/{count} complete architectures")
        try:
            shard, part = results.next(timeout=min(1.0, remaining))
        except mp.TimeoutError:
            continue
        index = part["index"]
        parts[index][shard] = part
        if len(parts[index]) == SHARDS:
            row = combine([parts[index][s] for s in range(SHARDS)])
            boundary.write_atomic(output / f"{row['phase']}-{index}.json.gz", row)
            rows[index] = row
            print(output.name, row["phase"], len(rows), "/", count, "pairs", row["evaluated"], flush=True)
    return [rows[i] for i in sorted(rows)]


def main():
    boundary.collect = collect
    original_write = boundary.write_atomic
    driver_hash = sha256(Path(__file__).read_bytes()).hexdigest()

    def write(path, report):
        if "reference" in report:
            report["execution_driver"] = {"module": __name__, "sha256": driver_hash, "shards": SHARDS,
                                           "per_architecture_seconds_are_worker_sums": True}
        return original_write(path, report)

    boundary.write_atomic = write
    boundary.main()


if __name__ == "__main__":
    main()
