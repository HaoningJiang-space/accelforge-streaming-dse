"""Exact fusion and port-aware mapping search on topological DAG ideals."""

from collections import defaultdict
from itertools import product

from research.joint_budget.protocol import Hardware
from research.runtime import dag_roofline
from research.runtime.dag_model import Group, lifetimes
from research.runtime.dag_overlap_cost import boundary, pointwise_frontier, score
from research.runtime.strip_codesign import (
    CAPACITIES, COMPUTE, DRAM, GB_READ, GB_WRITE, GEOMETRIES, add, ceildiv,
    pareto, representatives,
)
from research.runtime.strip_overlap_cost import stage_frontier, tile_grid
from research.runtime.strip_overlap_search import compose, ideal_stage, lower_stage


def transition_orders(graph, prune_orders=True):
    """Enumerate all possible next groups and remove dominated storage orders."""
    bits = {op.name: 1 << i for i, op in enumerate(graph.ops)}
    deps = {op.name: sum(bits.get(x, 0) for x in op.inputs) for op in graph.ops}
    full = sum(bits.values())
    profiles = {}
    table = {0: None}
    for done in range(full):
        if done not in table:
            continue
        by_target = defaultdict(list)

        def extend(mask, order):
            for name, bit in bits.items():
                if not mask & bit and not deps[name] & ~mask:
                    target = mask | bit
                    new = (*order, name)
                    by_target[target].append(new)
                    extend(target, new)

        extend(done, ())
        result = []
        for target, orders in by_target.items():
            table.setdefault(target, None)
            retained = []
            for order in orders:
                if order not in profiles:
                    profiles[order] = tuple(lifetimes(graph, order))
                width = tuple(step.live_width for step in sorted(profiles[order], key=lambda s: s.op.name))
                if prune_orders:
                    if any(all(a <= b for a, b in zip(other, width)) for other, _ in retained):
                        continue
                    retained = [(other, path) for other, path in retained
                                if not all(a <= b for a, b in zip(width, other))]
                retained.append((width, order))
            result.extend((target, order) for _, order in retained)
        table[done] = tuple(result)
    table[full] = ()
    return table, profiles, full


def lower_pointwise(graph, op, hardware):
    words = graph.rows * op.width
    lanes = hardware.px * hardware.py
    return (words * (2 * GB_READ[0] + GB_WRITE[0] + COMPUTE[0]),
            graph.rows * ceildiv(op.width, lanes) * COMPUTE[1])


def lower(graph, hardware, step, bands, pin, overlap="finite"):
    op = step.op
    if op.kind == "gemm":
        k, n = graph.widths[op.inputs[0]], op.width
        energy, ticks = lower_stage(graph.rows, k, n, hardware.px, hardware.py, bands, pin)
        if overlap == "prefetch" and not pin:
            dma = k*n*bands*DRAM[1]
            fill = k*n*bands*GB_READ[1]
            ticks = fill + max(dma, ticks-dma-fill)
        return energy, ticks
    return lower_pointwise(graph, op, hardware)


def choices(graph, hardware, step, b, pin, room, ideal=False, overlap="finite"):
    op = step.op
    if op.kind == "gemm":
        k = graph.widths[op.inputs[0]]
        if ideal and overlap != "serial":
            return ideal_stage(graph.rows, k, op.width, b, hardware.px, hardware.py, pin)
        if ideal:
            room = b * step.live_width + min(k, hardware.py) * min(op.width, hardware.px)
        return stage_frontier(graph.rows, k, op.width, b, hardware.px, hardware.py,
                              pin, room, step.live_width, overlap)
    limit = graph.rows * step.live_width + 3 * op.width if ideal else room
    return pointwise_frontier(graph.rows, op.width, b, hardware.px * hardware.py, limit, step.live_width, overlap)


def fits(graph, step, b, pin, tile, room, overlap):
    p, q = tile
    staging = (p + 2 * q if p else 3 * q) if overlap == "finite" else 0
    return b * step.live_width + (0 if pin else p * q) + staging <= room


def group_frontier(graph, hardware, order, profile, overlap="finite"):
    initial = boundary(graph, profile)
    room_options = []
    for pins in product(*[(False, True) if step.op.kind == "gemm" else (False,) for step in profile]):
        room = hardware.capacity_bytes - sum(graph.weight_words(step.op)
                                             for step, pin in zip(profile, pins) if pin)
        bmax = min(graph.rows, *((room - int(step.op.kind == "gemm" and not pin)) // step.live_width
                                 for step, pin in zip(profile, pins)))
        if bmax > 0:
            estimate = initial
            for step, pin in zip(profile, pins):
                estimate = add(estimate, lower(graph, hardware, step, ceildiv(graph.rows, bmax), pin, overlap))
            room_options.append((estimate[0] * estimate[1], bmax, room, pins))
    frontier = []

    def dominated(cost):
        return any(e <= cost[0] and t <= cost[1] for (e, t), _ in frontier)

    for _, bmax, room, pins in sorted(room_options):
        bands_to_try = range(bmax, 0, -1) if overlap == "prefetch" else reversed(representatives(graph.rows, bmax))
        for b in bands_to_try:
            bands = ceildiv(graph.rows, b)
            estimate = initial
            for step, pin in zip(profile, pins):
                estimate = add(estimate, lower(graph, hardware, step, bands, pin, overlap))
            if dominated(estimate):
                break
            if overlap == "prefetch":
                possible = compose(initial, (choices(graph, hardware, step, b, pin, room, overlap=overlap)
                                             for step, pin in zip(profile, pins)))
                frontier = list(pareto(frontier + [(cost, Group(order, b, tiles, pins)) for cost, tiles in possible]))
                continue
            ideal = compose(initial, (choices(graph, hardware, step, b, pin, room, ideal=True, overlap=overlap)
                                      for step, pin in zip(profile, pins)))
            wanted = [(cost, tiles) for cost, tiles in ideal if not dominated(cost)]
            if not wanted:
                continue
            if all(fits(graph, step, b, pin, tile, room, overlap) for _, tiles in wanted
                   for step, pin, tile in zip(profile, pins, tiles)):
                frontier = list(pareto(frontier + [
                    (cost, Group(order, b, tiles, pins)) for cost, tiles in wanted
                ]))
                continue
            largest = bmax if bands == 1 else min(bmax, (graph.rows - 1) // (bands - 1))
            for strip in range(b, largest+1):
                possible = compose(initial, (choices(graph, hardware, step, strip, pin, room, overlap=overlap)
                                             for step, pin in zip(profile, pins)))
                frontier = list(pareto(frontier + [
                    (cost, Group(order, strip, tiles, pins)) for cost, tiles in possible
                ]))
    return frontier


def lower_geometry(graph, hardware, profile, overlap="finite"):
    result = boundary(graph, profile)
    for step in profile:
        result = add(result, lower(graph, hardware, step, 1, False, overlap))
    return result[0] * result[1]


def exact_search(graph, budget, geometries=GEOMETRIES, *, prune_orders=True, singleton=False,
                 fixed_order=None, on_incumbent=None, overlap="finite", stats=None, tied_shapes=None):
    if overlap not in {"finite", "free_staging", "serial", "roofline", "prefetch"}:
        raise ValueError("unknown overlap pricing mode")
    hardware = [Hardware(x, y, max(c for c in CAPACITIES if c <= budget)) for x, y in geometries]
    transitions, profiles, terminal = transition_orders(graph, prune_orders and fixed_order is None)
    topo = tuple(op.name for op in graph.ops)
    complete = profiles[topo]
    masks = {name: 1 << i for i, name in enumerate(topo)}
    order_prefixes = set()
    if fixed_order:
        done = 0
        for name in fixed_order:
            order_prefixes.add(done)
            done |= masks[name]
        order_prefixes.add(done)
    best = None
    examined = 0
    if tied_shapes is not None:
        tied_shapes.clear()
    group_prices = 0
    cache_functions = (tile_grid, ideal_stage, stage_frontier, pointwise_frontier)
    before = {cache.__name__: cache.cache_info() for cache in cache_functions} if stats is not None else {}
    def geometry_bound(hw):
        if overlap == "roofline":
            return dag_roofline.lower_geometry(graph, hw, complete)
        return lower_geometry(graph, hw, complete, overlap)

    for h in sorted(hardware, key=geometry_bound):
        bound = geometry_bound(h)
        if best is not None:
            optimum = best[0][0] * best[0][1]
            if bound > optimum or (bound == optimum and tied_shapes is None):
                break
        examined += 1
        states = {0: [((0, 0), ())]}
        groups = {}
        for done in sorted(transitions):
            if done not in states:
                continue
            states[done] = list(pareto(states[done]))
            for target, order in transitions[done]:
                if singleton and len(order) != 1:
                    continue
                if fixed_order and (target not in order_prefixes or
                                    fixed_order[done.bit_count():target.bit_count()] != order):
                    continue
                if order not in groups:
                    groups[order] = (dag_roofline.frontier(graph, h, order, profiles[order]) if overlap == "roofline"
                                     else group_frontier(graph, h, order, profiles[order], overlap))
                    group_prices += 1
                states.setdefault(target, []).extend(
                    (add(a, b), left + (right,)) for a, left in states[done] for b, right in groups[order]
                )
        for cost, plan in states.get(terminal, ()):
            if best is None or cost[0] * cost[1] < best[0][0] * best[0][1]:
                priced = dag_roofline.score(graph, h, plan) if overlap == "roofline" else score(graph, h, plan, overlap)
                if priced != cost:
                    raise AssertionError("DAG frontier disagrees with analytical evaluator")
                best = cost, h, plan
                if tied_shapes is not None:
                    tied_shapes.clear()
                if on_incumbent is not None:
                    on_incumbent(best)
            if tied_shapes is not None and cost[0] * cost[1] == best[0][0] * best[0][1]:
                tied_shapes.add((h.px, h.py))
    if stats is not None:
        stats.update(examined_geometries=examined, group_prices=group_prices,
                     transitions=sum(map(len, transitions.values())))
        for cache in cache_functions:
            start, end = before[cache.__name__], cache.cache_info()
            stats[cache.__name__] = dict(hits=end.hits-start.hits, misses=end.misses-start.misses)
    for cache in cache_functions:
        cache.cache_clear()
    if best is None:
        raise ValueError("no feasible DAG mapping")
    return best, examined
