"""Compare a DAG-guided design search with full native SET annealing."""

import argparse
from collections import defaultdict
from itertools import combinations, product
import json
from math import ceil, isclose
from pathlib import Path
from random import Random
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


def routing(graph, tree):
    """Derive the forced DRAM edges from RA precedence, independently of SET."""
    index = {op.name: i for i, op in enumerate(graph.ops)}
    parents = [{index[name] for name in op.inputs if name in index} for op in graph.ops]
    leaves = {}
    paths = {}

    def assign(node, path):
        if "layer" in node:
            layer = node["layer"]
            leaves[layer] = node
            paths[layer] = path
            return {layer}
        descendants = []
        stages = []
        for position, child in enumerate(node["children"]):
            # The children already have known leaves. A spatial child's stage
            # is one past its latest direct producer child.
            child_ids = subtree_layers(child)
            inputs = set().union(*(parents[layer] for layer in child_ids))
            stage = (max((s+1 for prior, s in zip(descendants, stages) if prior & inputs), default=0)
                     if node["type"] == "S" else position)
            descendants.append(assign(child, (*path, (position, stage))))
            stages.append(stage)
        return set().union(*descendants)

    def subtree_layers(node):
        if "layer" in node:
            return {node["layer"]}
        return set().union(*(subtree_layers(child) for child in node["children"]))

    assign(tree, ())
    spills = set()
    drains = {index[name] for name in graph.outputs}
    for target, sources in enumerate(parents):
        direct = set()
        for src in sources:
            level, (left, right) = next((i, pair) for i, pair in enumerate(zip(paths[src], paths[target]))
                                        if pair[0][0] != pair[1][0])
            if level == 0 or right[1] > left[1]+1:
                spills.add((src, target))
                drains.add(src)
            else:
                direct.add(src)
        if "direct" in leaves[target] and direct != set(leaves[target]["direct"]):
            raise ValueError("SET and the independent RA walk disagree on a retained dependency")
    if any("drain" in leaf and bool(leaf["drain"]) != (layer in drains) for layer, leaf in leaves.items()):
        raise ValueError("SET and the independent RA walk disagree on DRAM writeback")
    return spills, drains


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
    routing(graph, tree)


def evaluate(graph, shape, capacity, trees, rounds, seed):
    binary = SET_ROOT / "build" / "dag_driver.exe"
    topology = shape[2] if len(shape) == 3 else 0
    args = [str(binary), *map(str, (*shape[:2], capacity, rounds, seed, topology))]
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
                or result["topology"] != topology or result["dram_ports"] != 4 or result["noc_links"] != 7
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


def nested_seeds(graph, flat):
    indices = {op.name: i for i, op in enumerate(graph.ops)}
    for groups, modes, profiles, _ in flat:
        if len(groups) != 1:
            continue
        order, = groups
        outer, = modes
        inner = "S" if outer == "T" else "T"
        for a, b in combinations(range(len(order)+1), 2):
            if not 2 <= b-a < len(order):
                continue
            leaves = [{"layer": indices[name]} for name in order]
            fused = {"type": inner, "children": leaves[a:b]}
            root = {"type": "T", "children": [{"type": outer, "children": [*leaves[:a], fused, *leaves[b:]]}]}
            spilled, drained = routing(graph, root)
            root["spill_words"] = graph.rows * (sum(graph.ops[i].width for i, _ in spilled)
                                                 + sum(graph.ops[i].width for i in drained))
            yield groups, modes, profiles, root


def predict(graph, shape, capacity, seed):
    """Rank by traffic, SRAM pressure and coarse Eyeriss row/column utilization."""
    groups, modes, profiles, tree = seed
    x, y = shape[:2]
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
        if "spill_words" in tree:
            inputs = sum(width for _, width in graph.inputs) * graph.rows
            traffic = sum(weights) + inputs + tree["spill_words"]
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
        groups, modes, _, tree = candidate
        if all(len(group) == 1 for group in groups):
            continue
        size = max(map(len, groups))
        buckets[size, "S" in modes, "spill_words" in tree].append((predict(graph, shape, capacity, candidate), candidate))
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


def search(graph, capacity, rounds, seed, policy, anchors, pool, shapes=SHAPES):
    start = perf_counter()
    count = min(rounds//4, 16, rounds+1-len(anchors)-30, len(pool))
    if count < 0:
        raise ValueError("search budget cannot price the common anchors and run native SA")
    trials = []
    for shape in shapes:
        if policy == "guided":
            candidates = guided_seeds(graph, shape, capacity, pool, count)
        elif policy == "uniform":
            candidates = [record[-1] for record in Random(seed).sample(pool, count)]
        else:
            candidates = []
        seeds = [*anchors, *candidates]
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
    if budget_used != len(shapes) * (rounds+1):
        raise ValueError("SET searches did not use equal candidate budgets")
    return dict(best=best, replay=replay, evaluations=budget_used, wall_s=wall, trials=trials,
                common_anchors=len(anchors), extra_seeds=len(candidates))


def portfolio(graph, capacity, rounds, seed, anchors, policy, shapes=SHAPES):
    """Keep independent native root basins alive and allocate a common global budget."""
    start = perf_counter()
    basins = defaultdict(list)
    for tree in anchors:
        children = tree["children"]
        key = children[0]["type"] if len(children) == 1 else "layerwise"
        basins[key].append(tree)
    states = []
    trials = []
    for shape in shapes:
        for name, trees in basins.items():
            priced = evaluate(graph, shape, capacity, trees, 0, seed)
            trials.append(dict(basin=name, **priced))
            if priced["feasible"]:
                states.append(dict(basin=name, best=priced, steps=0, improvement=0))
    if not states:
        raise ValueError("no SET root basin can be seeded")
    if policy == "architecture_first":
        layerwise = [row for row in trials if row["basin"] == "layerwise" and row["feasible"]]
        optimum = min(row["edp"] for row in layerwise)
        fixed = {row["shape"] for row in layerwise if isclose(row["edp"], optimum, rel_tol=1e-12)}
        states = [state for state in states if state["best"]["shape"] in fixed]

    limit = len(shapes) * (rounds+1)
    remaining = limit-sum(row["evaluations"] for row in trials)
    blocks = min(4, remaining//31)
    if not blocks:
        raise ValueError("insufficient common search budget after pricing root basins")
    calls, extra = divmod(remaining, blocks)
    visited_shapes, visited_basins = set(), set()
    for index in range(blocks):
        def priority(state):
            best = state["best"]
            shape = tuple(best["shape"])
            if policy != "balanced":
                # Initial visits compare actual EDP across shape/basin pairs.
                # Subsequent visits reward measured improvement, while an
                # unvisited basin gets one opportunity at its strongest shape.
                floor = best["edp"] * (1-max(0.05, state["improvement"]))
                return (state["basin"] in visited_basins, floor, state["steps"], shape)
            return (shape in visited_shapes, state["steps"], best["edp"], shape)

        state = min(states, key=priority)
        previous = state["best"]
        shape = tuple(previous["shape"])
        budget = calls + int(index < extra)
        priced = evaluate(graph, shape, capacity, [previous["tree"]], budget-1, seed+index)
        if not priced["feasible"] or priced["edp"] > previous["edp"] * (1+1e-12):
            raise ValueError("native SET lost the incumbent when resuming a basin")
        trials.append(dict(basin=state["basin"], **priced))
        state.update(best=priced, steps=state["steps"]+1, improvement=1-priced["edp"]/previous["edp"])
        visited_shapes.add(shape)
        visited_basins.add(state["basin"])
    elapsed = perf_counter()-start
    winner = min((state["best"] for state in states), key=lambda row: row["edp"])
    replay = evaluate(graph, winner["shape"], capacity, [winner["tree"]], 0, seed)
    if not replay["feasible"] or any(not isclose(replay[k], winner[k], rel_tol=1e-12)
                                     for k in ("energy", "cycles", "edp")):
        raise ValueError("SET root-basin winner changed on fresh replay")
    total = sum(row["evaluations"] for row in trials)
    if total != limit:
        raise ValueError("SET root-basin budget was not conserved")
    return dict(best=winner, replay=replay, trials=trials, evaluations=total, wall_s=elapsed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=tuple(CASES))
    parser.add_argument("--capacities", nargs="+", type=int, choices=CAPACITIES, default=(524288,))
    parser.add_argument("--seeds", nargs="+", type=int, default=(11, 29, 47, 71, 101))
    parser.add_argument("--rounds", type=int, default=64)
    parser.add_argument("--portfolio", action="store_true")
    parser.add_argument("--topologies", action="store_true", help="Cross each array with three equal-resource meshes.")
    parser.add_argument("--nested", action="store_true", help="Include the same nested RA seeds in every method's pool.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.rounds < 48 or args.output.exists():
        parser.error("require at least 48 native rounds and a fresh report path")
    revision = subprocess.check_output(["git", "-C", str(SET_ROOT), "rev-parse", "HEAD"], text=True).strip()
    shapes = tuple((*shape, topology) for shape in SHAPES for topology in range(3)) if args.topologies else SHAPES
    cases = []
    for name, capacity, seed in product(args.cases, args.capacities, args.seeds):
        graph = CASES[name]()
        start = perf_counter()
        all_seeds = tuple(seed_pool(graph))
        initial = {"type": "T", "children": [{"layer": i} for i in range(len(graph.ops))]}
        anchors = [initial, *(candidate[-1] for candidate in all_seeds if len(candidate[0]) == 1)]
        pool = tuple(candidate for candidate in all_seeds if 1 < len(candidate[0]) < len(graph.ops))
        if args.nested:
            pool += tuple(nested_seeds(graph, all_seeds))
        domain_s = perf_counter()-start
        # Reverse method order on alternate seeds to limit process warm-up bias.
        methods = ("native", "uniform", "guided") if len(cases) % 2 == 0 else ("guided", "uniform", "native")
        outcomes = {mode: search(graph, capacity, args.rounds, seed, mode, anchors, pool, shapes) for mode in methods}
        chosen = "guided"
        if args.portfolio:
            portfolios = ("balanced", "architecture_first", "joint")
            for mode in (portfolios if len(cases) % 2 == 0 else reversed(portfolios)):
                outcomes[mode] = portfolio(graph, capacity, args.rounds, seed, anchors, mode, shapes)
            chosen = "joint"
        reference = min(result["best"]["edp"] for mode, result in outcomes.items() if mode != chosen)
        gain = 1 - outcomes[chosen]["best"]["edp"]/reference
        record = dict(case=name, capacity_bytes=capacity, seed=seed, edp_reduction=gain,
                      method=chosen, common_domain_s=domain_s, seed_pool_size=len(all_seeds), **outcomes)
        cases.append(record)
        print(name, capacity, seed, gain, flush=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(dict(set_revision=revision, shapes=shapes, rounds=args.rounds, nested=args.nested, cases=cases),
                              indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
