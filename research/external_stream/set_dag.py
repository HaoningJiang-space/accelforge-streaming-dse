"""Compare a DAG-guided design search with full native SET annealing."""

import argparse
from collections import defaultdict
from itertools import combinations, product
import json
from math import ceil, isclose
from pathlib import Path
import subprocess
from time import perf_counter

from research.runtime.dag_cases import CASES
from research.runtime.dag_model import lifetimes
from research.runtime.dag_overlap_search import transition_orders


SHAPES = ((16, 64), (32, 32), (64, 16))
CAPACITIES = (131072, 135168, 262144, 524288)
CORES = 6
SET_ROOT = Path(__file__).resolve().parents[2] / "libraries" / "set-isca2023"


def encode_graph(graph):
    (external, width), = graph.inputs
    positions = {external: -1, **{op.name: i for i, op in enumerate(graph.ops)}}
    lines = [f"{graph.rows} {width} {len(graph.ops)}"]
    for op in graph.ops:
        left, right = [positions[name] for name in op.inputs] + [-1] * (2-len(op.inputs))
        k = graph.widths[op.inputs[0]] if op.kind == "gemm" else 0
        lines.append(f"{op.name} {op.kind} {op.width} {k} {left} {right}")
    return "\n".join(lines) + "\n"


def encode_tree(tree):
    if "layer" in tree:
        return f"L {tree['layer']}\n"
    return f"{tree['type']} {len(tree['children'])}\n" + "".join(map(encode_tree, tree["children"]))


def check_tree(graph, tree):
    seen = {name for name, _ in graph.inputs}

    def check(node):
        if "layer" in node:
            op = graph.ops[node["layer"]]
            if op.name in seen or not set(op.inputs) <= seen:
                raise ValueError("SET RA leaf is duplicated or precedes its producer")
            seen.add(op.name)
        else:
            if node["type"] not in ("S", "T") or not node["children"]:
                raise ValueError("invalid SET RA cut")
            for child in node["children"]:
                check(child)

    check(tree)
    if seen != graph.widths.keys():
        raise ValueError("SET dropped an operator")


def evaluate(graph, shape, capacity, trees, rounds, seed):
    binary = SET_ROOT / "build" / "dag_driver.exe"
    args = [str(binary), *map(str, (*shape, capacity, rounds, seed))]
    start = perf_counter()
    payload = encode_graph(graph) + f"{len(trees)}\n" + "".join(map(encode_tree, trees))
    process = subprocess.run(args, input=payload, encoding="utf-8",
                             capture_output=True, timeout=120)
    if process.returncode:
        raise RuntimeError(process.stderr or process.stdout or str(process.returncode))
    result, = (json.loads(line.removeprefix("RESULT ")) for line in process.stdout.splitlines()
               if line.startswith("RESULT "))
    if result["feasible"]:
        check_tree(graph, result["tree"])
        macs = graph.rows * sum(graph.weight_words(op) for op in graph.ops)
        if (result["cores"] != CORES or result["macs_per_core"] * CORES != 6144
                or result["sram_per_core"] != capacity//CORES
                or result["mac_ops"] != macs or result["evaluations"] != len(trees)+rounds
                or not isclose(result["dram_energy"], result["dram_accesses"] * 60, rel_tol=1e-12)
                or not isclose(result["energy"], sum(result[k] for k in ("local_energy", "noc_energy", "dram_energy")),
                               rel_tol=1e-10)
                or not isclose(result["edp"], result["energy"] * result["cycles"], rel_tol=1e-12)):
            raise ValueError("native SET budget or objective differs from the shared contract")
    return dict(shape=shape, wall_s=perf_counter()-start, **result)


def make_tree(indices, groups, modes):
    children = []
    for order, mode in zip(groups, modes, strict=True):
        leaves = [{"layer": indices[name]} for name in order]
        children.append(leaves[0] if len(leaves) == 1 else {"type": mode, "children": leaves})
    return {"type": "T", "children": children}


def seed_pool(graph):
    """Every ordered cut subset, with temporal or spatial execution in each group."""
    transitions, profiles, terminal = transition_orders(graph, prune_orders=False)
    indices = {op.name: i for i, op in enumerate(graph.ops)}
    for end, order in transitions[0]:
        if end != terminal:
            continue
        for count in range(len(order)):
            for cuts in combinations(range(1, len(order)), count):
                ends = (0, *cuts, len(order))
                groups = tuple(order[i:j] for i, j in zip(ends, ends[1:]))
                for modes in product(*[("T", "S") if len(group) > 1 else ("T",) for group in groups]):
                    yield groups, modes, tuple(profiles[group] for group in groups), make_tree(indices, groups, modes)


def predict(graph, shape, capacity, seed):
    """Rank by traffic, SRAM pressure and coarse Eyeriss row/column utilization."""
    groups, modes, profiles, _ = seed
    x, y = shape
    bw = 6
    energy = delay = 0.0
    for order, mode, profile in zip(groups, modes, profiles, strict=True):
        # SET drains a shortcut even within a segment. At a temporal cut a
        # producer may hand off only to the immediately following child.
        positions = {name: i for i, name in enumerate(order)}
        stages = {}
        for name in order:
            stages[name] = max((stages[src] + 1 for src in graph.operators[name].inputs if src in stages), default=0)
        step = positions if mode == "T" else stages
        weights = [graph.weight_words(life.op) for life in profile]
        traffic = sum(weights)
        for life in profile:
            name = life.op.name
            traffic += graph.rows * sum(graph.widths[t] for t in life.fetch)
            users = graph.users[name]
            distant = [dst for dst in users if dst in step and step[dst] > step[name] + 1]
            traffic += graph.rows * graph.widths[name] * (bool(life.drain or distant) + len(distant))
        activation = max(life.live_width for life in profile) * graph.rows
        pressure = (activation + (max(weights) if mode == "T" else sum(weights))) / capacity
        waves = [ceil(graph.rows/x) * ceil(life.op.width/y) * max(1, weight//life.op.width)
                 for life, weight in zip(profile, weights, strict=True)]
        compute = sum(waves) / CORES
        energy += traffic * 60 + sum(weights) * graph.rows * 0.018
        delay += max(compute, traffic/bw) * max(1.0, pressure)**2
    return energy * delay


def guided_seeds(graph, shape, capacity, pool, count):
    """Interleave fusion degrees so a tight buffer cannot starve smaller groups."""
    buckets = defaultdict(list)
    for candidate in pool:
        groups, modes, _, _ = candidate
        if all(len(group) == 1 for group in groups):
            continue
        size = max(map(len, groups))
        buckets[size, "S" in modes].append((predict(graph, shape, capacity, candidate), candidate))
    ranked = [iter(item for _, item in sorted(bucket, key=lambda pair: pair[0]))
              for _, bucket in sorted(buckets.items(), key=lambda pair: min(item[0] for item in pair[1]))]
    result = []
    while len(result) < count and ranked:
        for iterator in ranked.copy():
            candidate = next(iterator, None)
            if candidate is None:
                ranked.remove(iterator)
                continue
            result.append(candidate[-1])
            if len(result) == count:
                break
    return result


def search(graph, capacity, rounds, seed, guided):
    start = perf_counter()
    initial = {"type": "T", "children": [{"layer": i} for i in range(len(graph.ops))]}
    pool = tuple(seed_pool(graph)) if guided else ()
    trials = []
    for shape in SHAPES:
        if guided:
            seeds = [initial, *guided_seeds(graph, shape, capacity, pool, min(rounds//4, 16))]
        else:
            seeds = [initial]
        remaining = rounds+1-len(seeds)
        result = evaluate(graph, shape, capacity, seeds, remaining, seed)
        if not result["feasible"]:
            raise ValueError(f"native annealing could not start at {shape}, {capacity}")
        trials.append(result)
    wall = perf_counter() - start
    best = min((row for row in trials if row["feasible"]), key=lambda row: row["edp"])
    replay = evaluate(graph, best["shape"], capacity, [best["tree"]], 0, seed)
    if not replay["feasible"] or any(not isclose(best[k], replay[k], rel_tol=1e-12) for k in ("cycles", "energy", "edp")):
        raise ValueError("full RA-tree replay disagrees with the winning evaluation")
    budget_used = sum(row["evaluations"] for row in trials)
    if budget_used != len(SHAPES) * (rounds+1):
        raise ValueError("SET searches did not use equal candidate budgets")
    return dict(best=best, replay=replay, evaluations=budget_used, wall_s=wall, trials=trials)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=tuple(CASES))
    parser.add_argument("--capacities", nargs="+", type=int, choices=CAPACITIES, default=(524288,))
    parser.add_argument("--seeds", nargs="+", type=int, default=(11, 29, 47, 71, 101))
    parser.add_argument("--rounds", type=int, default=64)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.rounds < 48 or args.output.exists():
        parser.error("require at least 48 native rounds and a fresh report path")
    revision = subprocess.check_output(["git", "-C", str(SET_ROOT), "rev-parse", "HEAD"], text=True).strip()
    cases = []
    for name, capacity, seed in product(args.cases, args.capacities, args.seeds):
        graph = CASES[name]()
        # Reverse method order on alternate seeds to limit process warm-up bias.
        methods = (False, True) if len(cases) % 2 == 0 else (True, False)
        outcomes = {"guided" if mode else "set": search(graph, capacity, args.rounds, seed, mode)
                    for mode in methods}
        gain = 1 - outcomes["guided"]["best"]["edp"]/outcomes["set"]["best"]["edp"]
        record = dict(case=name, capacity_bytes=capacity, seed=seed, edp_reduction=gain, **outcomes)
        cases.append(record)
        print(name, capacity, seed, gain, flush=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(dict(set_revision=revision, shapes=SHAPES, rounds=args.rounds, cases=cases),
                              indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
