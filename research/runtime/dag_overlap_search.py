"""Exact fusion and port-aware mapping search on topological DAG ideals."""

from collections import defaultdict
from itertools import product

from research.joint_budget.protocol import Hardware
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


def lower(graph, hardware, step, bands, pin):
    op = step.op
    if op.kind == "gemm":
        return lower_stage(graph.rows, graph.widths[op.inputs[0]], op.width, hardware.px,
                           hardware.py, bands, pin)
    return lower_pointwise(graph, op, hardware)


def choices(graph, hardware, step, b, pin, room, ideal=False):
    op = step.op
    if op.kind == "gemm":
        k = graph.widths[op.inputs[0]]
        if ideal:
            return ideal_stage(graph.rows, k, op.width, b, hardware.px, hardware.py, pin)
        return stage_frontier(graph.rows, k, op.width, b, hardware.px, hardware.py,
                              pin, room, step.live_width)
    limit = graph.rows * step.live_width + 3 * op.width if ideal else room
    return pointwise_frontier(graph.rows, op.width, b, hardware.px * hardware.py, limit, step.live_width)


def fits(graph, step, b, pin, tile, room):
    p, q = tile
    staging = p + 2 * q if p else 3 * q
    return b * step.live_width + (0 if pin else p * q) + staging <= room


def group_frontier(graph, hardware, order, profile):
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
                estimate = add(estimate, lower(graph, hardware, step, ceildiv(graph.rows, bmax), pin))
            room_options.append((estimate[0] * estimate[1], bmax, room, pins))
    frontier = []

    def dominated(cost):
        return any(e <= cost[0] and t <= cost[1] for (e, t), _ in frontier)

    for _, bmax, room, pins in sorted(room_options):
        for b in reversed(representatives(graph.rows, bmax)):
            bands = ceildiv(graph.rows, b)
            estimate = initial
            for step, pin in zip(profile, pins):
                estimate = add(estimate, lower(graph, hardware, step, bands, pin))
            if dominated(estimate):
                break
            ideal = compose(initial, (choices(graph, hardware, step, b, pin, room, ideal=True)
                                      for step, pin in zip(profile, pins)))
            wanted = [(cost, tiles) for cost, tiles in ideal if not dominated(cost)]
            if not wanted:
                continue
            if all(fits(graph, step, b, pin, tile, room) for _, tiles in wanted
                   for step, pin, tile in zip(profile, pins, tiles)):
                frontier = list(pareto(frontier + [
                    (cost, Group(order, b, tiles, pins)) for cost, tiles in wanted
                ]))
                continue
            largest = bmax if bands == 1 else min(bmax, (graph.rows - 1) // (bands - 1))
            for strip in range(b, largest+1):
                possible = compose(initial, (choices(graph, hardware, step, strip, pin, room)
                                             for step, pin in zip(profile, pins)))
                frontier = list(pareto(frontier + [
                    (cost, Group(order, strip, tiles, pins)) for cost, tiles in possible
                ]))
    return frontier


def lower_geometry(graph, hardware, profile):
    result = boundary(graph, profile)
    for step in profile:
        result = add(result, lower(graph, hardware, step, 1, False))
    return result[0] * result[1]


def exact_search(graph, budget, geometries=GEOMETRIES, *, prune_orders=True, singleton=False,
                 fixed_order=None, on_incumbent=None):
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
    for h in sorted(hardware, key=lambda hw: lower_geometry(graph, hw, complete)):
        bound = lower_geometry(graph, h, complete)
        if best is not None and bound >= best[0][0] * best[0][1]:
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
                    groups[order] = group_frontier(graph, h, order, profiles[order])
                states.setdefault(target, []).extend(
                    (add(a, b), left + (right,)) for a, left in states[done] for b, right in groups[order]
                )
        for cost, plan in states.get(terminal, ()):
            if best is None or cost[0] * cost[1] < best[0][0] * best[0][1]:
                if score(graph, h, plan) != cost:
                    raise AssertionError("DAG frontier disagrees with analytical evaluator")
                best = cost, h, plan
                if on_incumbent is not None:
                    on_incumbent(best)
    for cache in (tile_grid, ideal_stage, stage_frontier, pointwise_frontier):
        cache.cache_clear()
    if best is None:
        raise ValueError("no feasible DAG mapping")
    return best, examined
