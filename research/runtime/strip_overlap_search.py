"""Joint hardware and connected-segment optimization under overlapped service."""

from functools import lru_cache
from itertools import product

from research.joint_budget.protocol import Hardware
from research.runtime.strip_codesign import (
    CAPACITIES, COMPUTE, DRAM, GB_READ, GEOMETRIES, Segment, add, ceildiv, pareto,
    representatives, stage_cost,
)
from research.runtime.strip_overlap_cost import boundary, evaluate_overlap, stage_frontier, tile_grid


def lower_stage(rows, k, n, x, y, bands, pin):
    kb, nb = ceildiv(k, y), ceildiv(n, x)
    energy, _ = stage_cost(rows, k, n, kb, nb, bands, pin)
    # Each tile's DMA and RF fill finish before its compute starts.
    delay = (k * n * (1 if pin else bands) * DRAM[1] + k * n * bands * GB_READ[1]
             + rows * kb * nb * COMPUTE[1])
    return energy, delay


def lower_geometry(rows, widths, x, y):
    result = boundary(rows, widths[0], widths[-1])
    for k, n in zip(widths, widths[1:]):
        result = add(result, lower_stage(rows, k, n, x, y, 1, False))
    return result[0] * result[1]


@lru_cache(maxsize=2048)
def ideal_stage(rows, k, n, b, x, y, pin):
    room = rows * (k + n) + min(k, y) * min(n, x) + k + 2 * n
    return stage_frontier(rows, k, n, b, x, y, pin, room)


def compose(initial, options):
    partial = [(initial, ())]
    for stage_options in options:
        partial = list(pareto((add(cost, extra), tiles + (tile,))
                              for cost, tiles in partial for extra, tile in stage_options))
    return partial


def connected_frontier(rows, widths, h, start, stop):
    pairs = tuple(zip(widths[start:stop], widths[start+1:stop+1]))
    initial = boundary(rows, widths[start], widths[stop])
    frontier = []
    groups = []
    for pinned in product((False, True), repeat=len(pairs)):
        room = h.capacity_bytes - sum(k * n for (k, n), pin in zip(pairs, pinned) if pin)
        bmax = min(rows, *((room - int(not pin)) // (k + n) for (k, n), pin in zip(pairs, pinned)))
        if bmax < 1:
            continue
        lower = initial
        for (k, n), pin in zip(pairs, pinned):
            lower = add(lower, lower_stage(rows, k, n, h.px, h.py, ceildiv(rows, bmax), pin))
        groups.append((lower[0] * lower[1], bmax, room, pinned))

    for _, bmax, room, pinned in sorted(groups):
        for smallest in reversed(representatives(rows, bmax)):
            bands = ceildiv(rows, smallest)
            lower = initial
            for (k, n), pin in zip(pairs, pinned):
                lower = add(lower, lower_stage(rows, k, n, h.px, h.py, bands, pin))
            if any(e <= lower[0] and t <= lower[1] for (e, t), _ in frontier):
                break
            ideal = compose(initial, (ideal_stage(rows, k, n, smallest, h.px, h.py, pin)
                                      for (k, n), pin in zip(pairs, pinned)))
            wanted = [(cost, tiles) for cost, tiles in ideal
                      if not any(e <= cost[0] and t <= cost[1] for (e, t), _ in frontier)]
            if not wanted:
                continue
            # With all waves overlapped, a strip class is determined by its
            # number of bands. If its lower frontier fits, every other width
            # in that class is dominated, even with a different remainder.
            if all(smallest * (k + n) + (0 if pin else p * q) + p + 2 * q <= room
                   for _, tiles in wanted
                   for (k, n), pin, (p, q) in zip(pairs, pinned, tiles)):
                frontier = list(pareto(frontier + [
                    (cost, Segment(start, stop, smallest, pinned, tiles)) for cost, tiles in wanted
                ]))
                continue
            largest = bmax if bands == 1 else min(bmax, (rows - 1) // (bands - 1))
            for b in range(smallest, largest+1):
                partial = compose(initial, (stage_frontier(rows, k, n, b, h.px, h.py, pin, room)
                                            for (k, n), pin in zip(pairs, pinned)))
                frontier = list(pareto(frontier + [
                    (cost, Segment(start, stop, b, pinned, tiles)) for cost, tiles in partial
                ]))
    return frontier


def anchors(rows, widths, budget, geometries=GEOMETRIES):
    """One feasible streamed, fully fused start per geometry."""
    capacity = max(c for c in CAPACITIES if c <= budget)
    for x, y in geometries:
        pairs = tuple(zip(widths, widths[1:]))
        tiles = tuple((min(k, y), min(n, x)) for k, n in pairs)
        b = min(rows, *((capacity - p * q) // (k + n) for (p, q), (k, n) in zip(tiles, pairs)))
        if b > 0:
            plan = (Segment(0, len(pairs), b, (False,) * len(pairs), tiles),)
            hardware = Hardware(x, y, capacity)
            cost, _ = evaluate_overlap(rows, widths, hardware, plan)
            yield cost, hardware, plan


def exact_search(rows, widths, budget, geometries=GEOMETRIES, on_incumbent=None, fuse=True,
                 prefix_join=None, initial=None):
    capacity = max(c for c in CAPACITIES if c <= budget)
    geometry_bounds = sorted((lower_geometry(rows, widths, x, y), x, y) for x, y in geometries)
    stages = len(widths) - 1
    best = initial
    searched = 0
    for bound, x, y in geometry_bounds:
        if best is not None and bound >= best[0][0] * best[0][1]:
            break
        hardware = Hardware(x, y, capacity)
        searched += 1
        states = [[((0, 0), ())]]
        for stop in range(1, stages+1):
            candidates = []
            for start in range(0 if fuse else stop-1, stop):
                segment = connected_frontier(rows, widths, hardware, start, stop)
                if prefix_join is None:
                    candidates.extend((add(a, b), left + (right,))
                                      for a, left in states[start] for b, right in segment)
                else:
                    candidates.extend(prefix_join(states[start], segment))
            states.append(list(pareto(candidates)))
        for cost, plan in states[-1]:
            if best is not None and cost[0] * cost[1] >= best[0][0] * best[0][1]:
                continue
            actual, _ = evaluate_overlap(rows, widths, hardware, plan)
            if actual != cost:
                raise AssertionError("overlap search differs from its scalar evaluator")
            best = cost, hardware, plan
            if on_incumbent is not None:
                on_incumbent(best)
    stage_frontier.cache_clear()
    tile_grid.cache_clear()
    ideal_stage.cache_clear()
    if best is None:
        raise ValueError("no legal overlap plan")
    return best, searched
