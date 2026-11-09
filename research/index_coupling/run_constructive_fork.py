"""Run the constructive fork experiment on the experiment server; emit auditable JSONL."""
import argparse
from collections import Counter
import json
from multiprocessing import Pool
from pathlib import Path
import platform
import statistics
import subprocess
from time import perf_counter

from .constructive_fork import Plan, candidates, execute, frontier

RESULTS = Path(__file__).parent / "results"


def emit(**record):
    print(json.dumps(record, allow_nan=False), flush=True)


def at(points, capacity):
    return min((q for c, q in points if c <= capacity), default=None)


def needed(points, traffic):
    return min((c for c, q in points if q <= traffic), default=None)


def points(plans):
    return [(p.metrics()["peak"], p.metrics()["traffic"]) for p in plans]


def validate():
    count = 0
    for shape in ((1, 1, 1, 1), (2, 3, 4, 5), (5, 3, 3, 2), (4, 4, 4, 4)):
        for cross in (False, True):
            for plan in candidates(shape, cross, all_tiles=True):
                expected, actual = plan.metrics(), execute(plan)
                for key in ("peak", "traffic", "reads", "writes"):
                    assert expected[key] == actual[key], (plan, key, expected, actual)
                count += 1
    emit(kind="validation", schedules=count, numeric_and_traffic_passed=True)


def sweep():
    records = [json.loads(line) for line in (RESULTS / "coupling_sweep.jsonl").read_text().splitlines()]
    for r in records:
        shape = tuple(r["shape"])
        for cross in (False, True):
            name = "cross" if cross else "same"
            reference = r[name + "_wt"]
            for all_tiles in (False, True):
                start = perf_counter()
                plans = list(candidates(shape, cross, all_tiles))
                selected = frontier(plans)
                seconds = perf_counter()-start
                predicted = points(selected)
                coverage = Counter()
                comparisons = []
                for c, q in reference:
                    value = at(predicted, c)
                    status = ("uncovered" if value is None else
                              "equal" if value == q else "worse" if value > q else "better")
                    coverage[status] += 1
                    comparisons.append([c, q, value])
                # Report the preselected midpoint target, including unfavorable cases.
                target = Plan(shape, False, "rows", max(1, shape[0]//2)).metrics()["traffic"]
                emit(kind="sweep", shape=shape, cross=cross, all_tiles=all_tiles,
                     candidates=len(plans), frontier=predicted, seconds=seconds,
                     coverage=dict(coverage), comparisons=comparisons,
                     midpoint_target=target, midpoint_reference_capacity=needed(reference, target),
                     midpoint_constructive_capacity=needed(predicted, target))


def focus():
    from .curve_model import curve
    from .nest_model import coupling
    from .simulate_nest import simulate
    specs = [((8,8,8,8), 9*8*8), ((16,16,16,16), 9*16*16),
             ((32,4,32,16), 3456), ((32,8,32,4), 3840)]
    for shape, target in specs:
        for cross in (False, True):
            graph = coupling(*shape, cross)
            times = []
            for _ in range(11):
                start = perf_counter()
                plans = frontier(candidates(shape, cross))
                times.append(perf_counter()-start)
            chosen = min((p for p in plans if p.metrics()["traffic"] <= target),
                         key=lambda p: p.metrics()["peak"])
            actual = execute(chosen)
            assert all(actual[k] == chosen.metrics()[k] for k in ("peak", "traffic", "reads", "writes"))
            start = perf_counter()
            exact = curve(graph, witness=True)
            curve_seconds = perf_counter()-start
            ref = min((row for row in exact if row[1] <= target), key=lambda row: row[0])
            replay = simulate(graph, ref[2])
            assert (replay["peak"], replay["traffic"]) == ref[:2]
            emit(kind="focus", shape=shape, cross=cross, target=target,
                 constructive=chosen.record(), constructive_execution=actual,
                 reference=dict(capacity=ref[0], traffic=ref[1], witness=ref[2], execution=replay),
                 full_reference_curve=[row[:2] for row in exact],
                 constructive_median_seconds=statistics.median(times),
                 constructive_timing_repetitions=len(times), full_curve_seconds=curve_seconds)


def replay_improvement(item):
    plan, targets = item
    actual = execute(plan)
    assert all(actual[k] == plan.metrics()[k] for k in ("peak", "traffic", "reads", "writes"))
    return dict(kind="improvement_execution", plan=plan.record(), targets=targets, execution=actual)


def audit(union=False):
    # Post-observation validation: audit EVERY knot at which the wider family
    # beats the archived power-of-two grammar, not only the best improvement.
    chosen = {}
    for line in (RESULTS / "coupling_sweep.jsonl").read_text().splitlines():
        record = json.loads(line)
        shape = tuple(record["shape"])
        for cross in (False, True):
            plans = frontier(candidates(shape, cross, all_tiles=True))
            reference = record[("cross" if cross else "same") + "_wt"]
            capacities = {c for c, _ in reference}
            if union:
                capacities.update(p.metrics()["peak"] for p in plans)
            for cap in sorted(capacities):
                traffic = at(reference, cap)
                eligible = [p for p in plans if p.metrics()["peak"] <= cap]
                if not eligible:
                    continue
                best = min(eligible, key=lambda p: p.metrics()["traffic"])
                if best.metrics()["traffic"] < traffic:
                    chosen.setdefault(best, []).append(dict(capacity=cap, reference_traffic=traffic))
    emit(kind="improvement_audit_size", union_breakpoints=union,
         plans=len(chosen), points=sum(map(len, chosen.values())))
    with Pool(4) as pool:
        for result in pool.imap(replay_improvement, chosen.items()):
            emit(**result)


def audit_union():
    audit(union=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("validate", "sweep", "focus", "audit", "audit_union"))
    args = parser.parse_args()
    emit(kind="metadata", mode=args.mode, host=platform.node(), python=platform.python_version(),
         commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
         tracked_dirty=bool(subprocess.check_output(["git", "diff", "--name-only", "HEAD"], text=True)),
         reference_commit="c82f2ee8", semantics="unit-byte cells, exact integer arithmetic, no recomputation")
    globals()[args.mode]()


if __name__ == "__main__":
    main()
