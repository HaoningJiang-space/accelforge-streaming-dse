"""End-to-end comparison in STREAM's complete one-core DAG evaluation pipeline."""

import argparse
from copy import deepcopy
from hashlib import sha256
from importlib.metadata import version
from itertools import combinations
import json
from math import isclose, isfinite, prod
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

from stream.api import SolveOptions, evaluate_mapping
from stream.ir.infeasibility import InfeasibleAllocationError
from stream.workload.node import ComputationNode
from stream.workload.normalization import expand_normalizations

from research.external_stream.dag import build, verify_graph
from research.external_stream.dag_memo import native_memo
from research.external_stream.hardware import project
from research.runtime.dag_cases import CASES
from research.runtime.strip_codesign import add, pareto


GEOMETRIES = ((32, 192), (48, 128), (64, 96))
BUDGETS = (131072, 135168)


def cut_sets(order):
    for count in range(len(order)):
        yield from combinations(order[:-1], count)


def graph_order(workload):
    return tuple(node.name for node in workload.dataflow_sort() if isinstance(node, ComputationNode))


def group_record(allocation):
    names = tuple(layer for group in allocation["fusion"]["groups"] for layer in group["layers"])
    e = float(allocation["performance"]["energy"]["total_pj"])
    t = float(allocation["latency"]["total"])
    if not (isfinite(e) and e > 0 and isfinite(t) and t > 0):
        raise ValueError("incomplete STREAM energy/latency accounting")
    solve = {key: allocation["solve"][key] for key in ("status", "mip_gap", "objective")}
    schedule = {key: value for key, value in allocation.items() if key not in {"solve", "roofline"}}
    fingerprint = sha256(json.dumps(schedule, sort_keys=True).encode()).hexdigest()
    return dict(operators=names, energy_pj=e, cycles=t, work=allocation["performance"]["aggregate"],
                memory=allocation["performance"]["memory_occupancy"],
                placements=allocation["edge_placements"], tiling=allocation["tiling"], solve=solve,
                allocation_sha256=fingerprint)


def evaluate(workload, shape, cuts, limit):
    t0 = perf_counter()
    with TemporaryDirectory(prefix="stream-common-dag-") as tmp:
        path = Path(tmp)
        hardware = project(path, *shape)
        args = {} if cuts is None else {"fusion_cut_points": list(cuts)}
        try:
            estimate = evaluate_mapping(str(hardware), deepcopy(workload), str(path / "out"),
                                        options=SolveOptions(time_limit_s=limit, tile_search=True,
                                                             artifacts=False, stage_options=args))
        except (InfeasibleAllocationError, RuntimeError) as error:
            cause = error.__cause__
            failure = error if isinstance(error, InfeasibleAllocationError) else cause
            if not isinstance(failure, InfeasibleAllocationError):
                raise
            return dict(shape=shape, cuts=cuts, feasible=False, status=failure.report.status, reason=str(error),
                        wall_s=perf_counter()-t0)
        allocations = estimate.context.get("group_allocations")
        groups = [group_record(allocations[index]) for index in sorted(allocations)]
        order = graph_order(workload)
        macs = {node.name: prod(workload.get_dimension_size(dim) for dim in workload.get_dims(node))
                for node in workload.get_computation_nodes() if node.type == "MatMul"}
        if sorted(name for group in groups for name in group["operators"]) != sorted(order):
            raise AssertionError("STREAM duplicated or omitted a DAG operator")
        if cuts is not None:
            bounds = (0, *(order.index(cut)+1 for cut in cuts), len(order))
            expected = [set(order[a:b]) for a, b in zip(bounds, bounds[1:])]
            if [set(group["operators"]) for group in groups] != expected:
                return dict(shape=shape, cuts=cuts, feasible=False, status="PARTITION_MISMATCH",
                            expected_groups=[sorted(names) for names in expected],
                            actual_groups=[group["operators"] for group in groups], wall_s=perf_counter()-t0)
        for group in groups:
            on_chip = [p for p in group["memory"] if p["cores"]]
            if (len(on_chip) != 1 or on_chip[0]["capacity_bits"] != shape[2] * 8
                    or on_chip[0]["resident_bits"] > shape[2] * 8):
                raise AssertionError("STREAM violates the declared SRAM ceiling")
            if (group["work"]["peak_macs_per_cycle"] != shape[0] * shape[1]
                    or group["work"]["total_mac_ops"] != sum(macs.get(name, 0) for name in group["operators"])):
                raise AssertionError("STREAM changed the PE budget or GEMM work")
        if estimate.dispatch_cycles != 0 or not isclose(sum(g["cycles"] for g in groups), estimate.cycles):
            raise AssertionError("dispatch or graph cycles are not additive")
    energy = sum(g["energy_pj"] for g in groups)
    return dict(shape=shape, cuts=cuts, feasible=True, energy_pj=energy, cycles=estimate.cycles,
                edp=energy * estimate.cycles, groups=groups, wall_s=perf_counter()-t0)


def sweep(workload, shapes, limit, extreme_cuts=False):
    start = perf_counter()
    order = graph_order(workload)
    trials = []
    # Give the reference its unmodified full-system default at every shape.
    requested = (cuts for cuts in cut_sets(order)
                 if not extreme_cuts or min(len(cuts), len(order)-1-len(cuts)) <= 1)
    for cuts in (None, *requested):
        for shape in shapes:
            report = evaluate(workload, shape, cuts, limit)
            report["elapsed_s"] = perf_counter() - start
            trials.append(report)
    return dict(wall_s=perf_counter()-start, trials=trials)


def intervals(workload, order):
    for stop in range(1, len(order)+1):
        for start in range(stop):
            cuts = tuple(order[index] for index in (start-1, stop-1)
                         if 0 <= index < len(order)-1)
            wanted = set(order[start:stop])
            subs = workload.split_fusion_groups(cut_points=list(cuts))
            matches = [sub for sub in subs if set(graph_order(sub)) == wanted]
            if len(matches) != 1:
                raise AssertionError("native group extraction changed the DAG interval")
            yield start, stop, matches[0]


def compose(workload, shapes, limit):
    t0 = perf_counter()
    order = graph_order(workload)
    all_groups = tuple(intervals(workload, order))
    choices = []
    parts = []
    for shape in shapes:
        frontier = [[((0, 0), ())]]
        by_stop = {stop: [] for stop in range(1, len(order)+1)}
        for start, stop, sub in all_groups:
            group = evaluate(sub, shape, (), limit)
            group.update(operators=order[start:stop], first=start, stop=stop)
            parts.append(group)
            by_stop[stop].append(group)
        for stop in range(1, len(order)+1):
            candidates = []
            for group in by_stop[stop]:
                if group["feasible"]:
                    cost = group["energy_pj"], group["cycles"]
                    cut = (order[stop-1],) if stop < len(order) else ()
                    candidates.extend((add(value, cost), path + cut)
                                      for value, path in frontier[group["first"]])
            frontier.append(list(pareto(candidates)))
        if frontier[-1]:
            (e, t), cuts = min(frontier[-1], key=lambda entry: entry[0][0] * entry[0][1])
            choices.append((e * t, shape, cuts))
    if not choices:
        raise ValueError("STREAM did not find a feasible partition")
    prediction, shape, cuts = min(choices)
    winner = evaluate(workload, shape, cuts, limit)
    return dict(wall_s=perf_counter()-t0, intervals=parts, predicted_edp=prediction, winner=winner)


def check(workload, reference, factored):
    order = graph_order(workload)
    parts = {(tuple(row["shape"]), frozenset(row["operators"])): row for row in factored["intervals"]}
    mismatches = []
    for whole in reference["trials"]:
        if whole["cuts"] is None:
            continue
        shape = tuple(whole["shape"])
        mask = [0, *(order.index(cut)+1 for cut in whole["cuts"]), len(order)]
        isolated = [parts[shape, frozenset(order[i:j])] for i, j in zip(mask, mask[1:])]
        if whole["feasible"] != all(g["feasible"] for g in isolated):
            mismatches.append(dict(shape=shape, cuts=whole["cuts"], reason="feasibility differs"))
        elif whole["feasible"]:
            for group, local in zip(whole["groups"], isolated, strict=True):
                if (set(group["operators"]) != set(local["operators"])
                        or not isclose(group["energy_pj"], local["energy_pj"], rel_tol=1e-10)
                        or not isclose(group["cycles"], local["cycles"], rel_tol=1e-10)):
                    mismatches.append(dict(shape=shape, cuts=whole["cuts"], group=group["operators"],
                                           reason="group cost depends on surrounding cut choices"))
    valid = [row for row in reference["trials"] if row["feasible"]]
    best = min(valid, key=lambda row: row["edp"])
    winner = factored["winner"]
    same = winner["feasible"] and isclose(winner["edp"], best["edp"], rel_tol=1e-10)
    predicted = winner["feasible"] and isclose(winner["edp"], factored["predicted_edp"], rel_tol=1e-10)
    return dict(reference_best=best, best_equal=same, prediction_equal=predicted,
                interval_equivalence=not mismatches, mismatches=mismatches)


def memoized(workload, shapes, limit, extreme_cuts=False):
    with native_memo() as stats:
        result = sweep(workload, shapes, limit, extreme_cuts)
    return dict(**result, reuse=stats)


def controls(reference):
    valid = [row for row in reference["trials"] if row["feasible"]]
    best = min(valid, key=lambda row: row["edp"])
    stock = min((row for row in valid if row["cuts"] is None), key=lambda row: row["edp"], default=None)
    max_cuts = max(len(row["cuts"]) for row in reference["trials"] if row["cuts"] is not None)
    singleton = [row for row in valid if row["cuts"] is not None and len(row["cuts"]) == max_cuts]
    preset = min((row["edp"] for row in singleton), default=float("inf"))
    eligible = {tuple(row["shape"]) for row in singleton if isclose(row["edp"], preset, rel_tol=1e-12)}
    fixed = min((row for row in valid if tuple(row["shape"]) in eligible),
                key=lambda row: row["edp"], default=None)
    return dict(reference_best=best, stock=stock, singleton_first_shapes=sorted(eligible),
                singleton_first_best=fixed, singleton_first_gain=1-best["edp"]/fixed["edp"] if fixed else None)


def check_memo(reference, reused):
    expected = {(tuple(row["shape"]), row["cuts"]): row for row in reference["trials"]}
    observed = {(tuple(row["shape"]), row["cuts"]): row for row in reused["trials"]}
    if expected.keys() != observed.keys():
        raise AssertionError("the two methods searched different configurations")
    errors = []
    fields = ("feasible", "status", "cycles", "energy_pj", "groups", "expected_groups", "actual_groups")
    for key, row in expected.items():
        differences = [field for field in fields if row.get(field) != observed[key].get(field)]
        if differences:
            errors.append(dict(shape=key[0], cuts=key[1], fields=differences))
        if row.get("status") == "PARTITION_MISMATCH":
            errors.append(dict(shape=key[0], cuts=key[1], fields=["requested_partition"]))
    return dict(**controls(reference), mismatches=errors, equivalent=not errors)


def run(names, budgets, repeats, limit, method, extreme_cuts):
    results = []
    for name in names:
        graph = CASES[name]()
        # STREAM itself applies this canonical lexical ordering before reading cut names.
        workload = expand_normalizations(build(graph))
        manifest = verify_graph(workload, graph)
        for budget in budgets:
            shapes = tuple((x, y, budget) for x, y in GEOMETRIES)
            for trial in range(repeats):
                methods = (sweep, method) if trial % 2 == 0 else (method, sweep)
                outcome = {selected.__name__: (selected(workload, shapes, limit) if selected is compose
                                                else selected(workload, shapes, limit, extreme_cuts))
                           for selected in methods}
                alternate = outcome[method.__name__]
                evidence = (check(workload, outcome["sweep"], alternate) if method is compose
                            else check_memo(outcome["sweep"], alternate))
                record = dict(case=name, graph=manifest, budget=budget, trial=trial,
                              **outcome, checks=evidence)
                results.append(record)
                print(json.dumps(dict(case=name, budget=budget, trial=trial,
                    sweep_s=outcome["sweep"]["wall_s"], alternate_s=alternate["wall_s"],
                    equivalent=evidence.get("equivalent"), best_equal=evidence.get("best_equal"),
                    singleton_first_gain=evidence.get("singleton_first_gain"),
                    hits=alternate.get("reuse", {}).get("hits"),
                    mismatches=len(evidence["mismatches"]))), flush=True)
    stream_path = Path(__file__).resolve().parents[2] / "libraries" / "stream"
    revision = subprocess.check_output(["git", "-C", str(stream_path), "rev-parse", "HEAD"], text=True).strip()
    return dict(stream_revision=revision, geometries=GEOMETRIES, limit_per_allocation_s=limit, repeats=repeats,
                extreme_cuts=extreme_cuts,
                versions={pkg: version(pkg) for pkg in ("stream-dse", "zigzag-dse", "ortools")},
                cases=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=("glu", "diamond"))
    parser.add_argument("--budgets", nargs="+", type=int, choices=BUDGETS, default=(131072,))
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--limit", type=float, default=10)
    parser.add_argument("--method", choices=("compose", "memoized"), default="memoized")
    parser.add_argument("--extreme-cuts", action="store_true",
                        help="Use at most one cut or leave at most one boundary fused.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.repeats < 1:
        raise FileExistsError("a new report and a positive repetition count are required")
    method = {"compose": compose, "memoized": memoized}[args.method]
    if args.extreme_cuts and method is compose:
        parser.error("the isolation diagnostic requires every cut subset")
    result = run(args.cases, args.budgets, args.repeats, args.limit, method, args.extreme_cuts)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    if method is memoized and any(not row["checks"]["equivalent"] for row in result["cases"]):
        raise SystemExit("STREAM comparison failed the allocation-equivalence gate. See the saved report.")


if __name__ == "__main__":
    main()
