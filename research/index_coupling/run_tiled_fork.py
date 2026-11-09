"""Scoped-retention ablation. Run only on eex005; outputs JSONL provenance."""
import argparse
from collections import Counter
from itertools import chain
import json
from multiprocessing import Pool
from pathlib import Path
import platform
import subprocess
from time import perf_counter

from .constructive_fork import Plan, candidates as strips, frontier
from .tiled_fork import TiledPlan, candidates as tiled, execute

RESULTS = Path(__file__).parent / "results"
MODES = ("strips", "tiles_no_retention", "tiles_scoped_retention")


def emit(**record):
    print(json.dumps(record, allow_nan=False), flush=True)


def at(points, capacity):
    return min((q for c, q in points if c <= capacity), default=None)


def needed(points, traffic):
    return min((c for c, q in points if q <= traffic), default=None)


def build(shape, cross, all_tiles, mode):
    start = perf_counter()
    alternatives = list(strips(shape, cross, all_tiles))
    if mode != "strips":
        alternatives.extend(tiled(shape, cross, all_tiles, retention=mode == "tiles_scoped_retention"))
    plans = frontier(alternatives)
    seconds = perf_counter()-start
    points = [(p.metrics()["peak"], p.metrics()["traffic"]) for p in plans]
    return plans, points, len(alternatives), seconds


def score(reference, actual, capacities):
    count, comparisons = Counter(), []
    for capacity in sorted(capacities):
        ref, value = at(reference, capacity), at(actual, capacity)
        status = ("uncovered" if value is None else "equal" if value == ref
                  else "worse" if value > ref else "better")
        count[status] += 1
        comparisons.append([capacity, ref, value])
    return dict(count), comparisons


def validate():
    count = 0
    for shape in ((1,1,1,1), (2,3,4,5), (5,3,3,2), (4,4,4,4)):
        for cross in (False, True):
            for plan in tiled(shape, cross, all_tiles=True):
                expected, actual = plan.metrics(), execute(plan)
                assert all(expected[k] == actual[k] for k in ("peak", "traffic", "reads", "writes")), (plan, expected, actual)
                count += 1
    rejected = 0
    for args in [((2,2,2,2), False, "I", 1, 1, ("B",)),
                 ((2,2,2,2), True, "K", 1, 1, ("D",)),
                 ((2,2,2,2), True, "K", 1, 1, ("B", "B")),
                 ((2,2,2,2), False, "I", 3, 1, ())]:
        try:
            TiledPlan(*args)
        except ValueError:
            rejected += 1
        else:
            raise AssertionError("accepted invalid interface/tile")
    # Prove this executable path does not obtain its answer from metrics().
    original = TiledPlan.metrics
    def forbidden(*args):
        raise AssertionError("executor called the analytic model")
    try:
        TiledPlan.metrics = forbidden
        execute(TiledPlan((3,2,5,2), True, "K", 2, 3, ("B", "V")))
    finally:
        TiledPlan.metrics = original
    emit(kind="validation", schedules=count, rejected_invalid=rejected,
         executor_independent_of_metrics=True, passed=True)


def cases():
    for line in (RESULTS / "coupling_sweep.jsonl").read_text().splitlines():
        record = json.loads(line)
        for cross in (False, True):
            yield tuple(record["shape"]), cross, record[("cross" if cross else "same")+"_wt"]


def sweep():
    for shape, cross, reference in cases():
        for all_tiles in (False, True):
            for mode in MODES:
                plans, points, count, seconds = build(shape, cross, all_tiles, mode)
                coverage, comparisons = score(reference, points, {c for c, _ in reference})
                union, union_comparisons = score(reference, points, {c for c, _ in chain(reference, points)})
                target = Plan(shape, False, "rows", max(1, shape[0]//2)).metrics()["traffic"]
                targets = [target] + ([3840] if shape == (32,8,32,4) else [])
                selected = []
                for q in targets:
                    plan = next((p for p in plans if p.metrics()["traffic"] <= q), None)
                    selected.append(dict(target=q, reference_capacity=needed(reference, q),
                                         capacity=needed(points, q), plan=plan.record() if plan else None))
                emit(kind="ablation", shape=shape, cross=cross, all_tiles=all_tiles, mode=mode,
                     candidates=count, seconds=seconds, frontier=points, coverage=coverage,
                     comparisons=comparisons, union_coverage=union, union_comparisons=union_comparisons,
                     targets=selected)


def replay(item):
    plan, reason = item
    actual = execute(plan)
    assert all(actual[k] == plan.metrics()[k] for k in ("peak", "traffic", "reads", "writes")), (plan, actual)
    return dict(kind="execution", plan=plan.record(), reason=reason, execution=actual)


def audit():
    chosen = {}
    for shape, cross, reference in cases():
        power, _, _, _ = build(shape, cross, False, "tiles_scoped_retention")
        for plan in power:
            if isinstance(plan, TiledPlan):
                chosen.setdefault(plan, set()).add("power_of_two_frontier")
        wider, points, _, _ = build(shape, cross, True, "tiles_scoped_retention")
        _, baseline, _, _ = build(shape, cross, True, "strips")
        for cap in sorted({c for c, _ in chain(reference, baseline, points)}):
            eligible = [p for p in wider if p.metrics()["peak"] <= cap]
            if not eligible:
                continue
            plan = min(eligible, key=lambda p: p.metrics()["traffic"])
            if not isinstance(plan, TiledPlan):
                continue
            q, ref, base = plan.metrics()["traffic"], at(reference, cap), at(baseline, cap)
            if q < ref:
                chosen.setdefault(plan, set()).add("wider_beats_archived")
            if base is None or q < base:
                chosen.setdefault(plan, set()).add("wider_improves_strips")
    emit(kind="audit_size", plans=len(chosen), reasons=dict(Counter(reason for reasons in chosen.values() for reason in reasons)))
    with Pool(4) as pool:
        for result in pool.imap(replay, ((plan, sorted(reason)) for plan, reason in chosen.items()), chunksize=1):
            emit(**result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("validate", "sweep", "audit"))
    args = parser.parse_args()
    emit(kind="metadata", mode=args.mode, host=platform.node(), python=platform.python_version(),
         commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
         tracked_dirty=bool(subprocess.check_output(["git", "diff", "--name-only", "HEAD"], text=True)),
         reference_commit="c82f2ee8", strip_baseline="52aee77d")
    globals()[args.mode]()


if __name__ == "__main__":
    main()
