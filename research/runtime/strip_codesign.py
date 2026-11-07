"""Exact connected-segment search for a row-streamed dense GEMM chain."""

from bisect import bisect_right
from dataclasses import dataclass
from functools import cache
from itertools import product

from research.joint_budget.protocol import Hardware


PE_COUNT = 6144
CAPACITIES = (128 * 1024, 132 * 1024 - 1, 132 * 1024, 256 * 1024)
GEOMETRIES = tuple((x, PE_COUNT // x) for x in range(1, PE_COUNT + 1) if PE_COUNT % x == 0)
# Energy units are 4 fJ. Time units are 1/1536 ns. All coefficients are exact.
DRAM = (14060, 40)
GB_READ = (498, 3)
GB_WRITE = (586, 12)
COMPUTE = (21, 1536)


@dataclass(frozen=True)
class Segment:
    start: int
    stop: int
    rows: int
    pinned: tuple[bool, ...]
    tiles: tuple[tuple[int, int], ...]


def ceildiv(a, b):
    return (a + b - 1) // b


def add(a, b):
    return a[0] + b[0], a[1] + b[1]


def charge(words, unit):
    return words * unit[0], words * unit[1]


def boundary_cost(rows, k, n):
    return add(charge(rows * (k + n), DRAM),
               add(charge(rows * k, GB_WRITE), charge(rows * n, GB_READ)))


def stage_cost(rows, k, n, k_blocks, n_blocks, bands, pin):
    weight = k * n
    loads = weight * (1 if pin else bands)
    reads = weight * bands + rows * (k * n_blocks + n * (k_blocks - 1))
    writes = loads + rows * n * k_blocks
    macs = rows * weight
    cycles = rows * k_blocks * n_blocks
    return (
        loads * DRAM[0] + reads * GB_READ[0] + writes * GB_WRITE[0] + macs * COMPUTE[0],
        loads * DRAM[1] + reads * GB_READ[1] + writes * GB_WRITE[1] + cycles * COMPUTE[1],
    )


def evaluate(rows, widths, hardware, plan):
    """Price an entire mapping and require a legal allocation and full chain."""
    total = (0, 0)
    start = 0
    peak = 0
    for group in plan:
        length = group.stop - group.start
        if (group.start != start or not 0 < length <= len(widths) - 1 - start
                or not 1 <= group.rows <= rows
                or len(group.pinned) != length or len(group.tiles) != length):
            raise ValueError("invalid connected segment")
        pairs = list(zip(widths[group.start:group.stop], widths[group.start+1:group.stop+1]))
        pinned_bytes = sum(k * n for (k, n), pin in zip(pairs, group.pinned) if pin)
        total = add(total, boundary_cost(rows, widths[start], widths[group.stop]))
        for (k, n), pin, (p, q) in zip(pairs, group.pinned, group.tiles):
            if not (1 <= p <= min(hardware.py, k) and 1 <= q <= min(hardware.px, n)):
                raise ValueError("tile exceeds fanout or tensor extent")
            peak = max(peak, pinned_bytes + group.rows * (k + n) + (0 if pin else p * q))
            total = add(total, stage_cost(rows, k, n, ceildiv(k, p), ceildiv(n, q),
                                          ceildiv(rows, group.rows), pin))
        start = group.stop
    if start != len(widths) - 1 or peak > hardware.capacity_bytes:
        raise ValueError("incomplete plan or SRAM budget exceeded")
    return total, peak


@cache
def representatives(extent, maximum):
    """Smallest tile for each attainable count of equally stepped blocks."""
    tiles = []
    p = 1
    while p <= min(extent, maximum):
        tiles.append(p)
        quotient = (extent - 1) // p
        if quotient == 0:
            break
        p = (extent - 1) // quotient + 1
    return tuple(tiles)


def pareto(candidates):
    best_time = float("inf")
    for cost, plan in sorted(candidates, key=lambda entry: entry[0]):
        if cost[1] < best_time:
            best_time = cost[1]
            yield cost, plan


@cache
def tile_options(k, n, x, y, room):
    ps, qs = representatives(k, x), representatives(n, y)
    if room is None or ps[-1] * qs[-1] <= room:
        return ((ps[-1], qs[-1]),)
    # For a fixed p a larger feasible q weakly improves both objectives.
    choices = []
    best_q = 0
    for p in reversed(ps):
        index = bisect_right(qs, room // p)
        if index and qs[index - 1] > best_q:
            best_q = qs[index - 1]
            choices.append((p, best_q))
    return tuple(choices)


def segment_frontier(rows, widths, hardware, start, stop):
    pairs = tuple(zip(widths[start:stop], widths[start+1:stop+1]))
    initial_cost = boundary_cost(rows, widths[start], widths[stop])
    fastest = tuple(tile_options(k, n, hardware.py, hardware.px, None)[0] for k, n in pairs)
    if all(rows * (k + n) + p * q <= hardware.capacity_bytes
           for (k, n), (p, q) in zip(pairs, fastest)):
        cost = initial_cost
        for (k, n), (p, q) in zip(pairs, fastest):
            cost = add(cost, stage_cost(rows, k, n, ceildiv(k, p), ceildiv(n, q), 1, False))
        return ((cost, Segment(start, stop, rows, (False,) * len(pairs), fastest)),)
    @cache
    def optimistic(bands):
        cost = initial_cost
        for (k, n), (p, q) in zip(pairs, fastest):
            cost = add(cost, stage_cost(rows, k, n, ceildiv(k, p), ceildiv(n, q), bands, False))
        return cost

    def lower(bands, pinned):
        base = optimistic(bands)
        discount = charge((bands - 1) * pinned, add(DRAM, GB_WRITE))
        return base[0] - discount[0], base[1] - discount[1]

    masks = []
    for pins in product((False, True), repeat=len(pairs)):
        pinned = sum(k * n for (k, n), pin in zip(pairs, pins) if pin)
        available = hardware.capacity_bytes - pinned
        row_limit = min((available - int(not pin)) // (k + n)
                        for (k, n), pin in zip(pairs, pins))
        if row_limit > 0:
            e, t = lower(ceildiv(rows, row_limit), pinned)
            masks.append((e * t, pinned, pins, row_limit))
    candidates = []
    for _, pinned, pins, row_limit in sorted(masks):
        available = hardware.capacity_bytes - pinned
        for b in reversed(representatives(rows, row_limit)):
            bands = ceildiv(rows, b)
            e, t = lower(bands, pinned)
            # This relaxes tile storage but keeps compulsory traffic. Narrower
            # strips can only increase both bounds for the same pin pattern.
            if any(cost[0] <= e and cost[1] <= t for cost, _ in candidates):
                break
            frontier = [(initial_cost, ())]
            unrestricted = True
            for (k, n), pin, tile in zip(pairs, pins, fastest):
                room = None if pin else available - b * (k + n)
                unrestricted &= room is None or tile[0] * tile[1] <= room
                tile_scores = [(stage_cost(rows, k, n, ceildiv(k, p), ceildiv(n, q),
                                           bands, pin), (p, q))
                               for p, q in tile_options(k, n, hardware.py, hardware.px, room)]
                frontier = list(pareto((add(cost, delta), tiles + (tile,))
                                       for cost, tiles in frontier for delta, tile in tile_scores))
            candidates = list(pareto(candidates + [
                (cost, Segment(start, stop, b, pins, tiles)) for cost, tiles in frontier
            ]))
            # Shorter strips increase weight reloads and cannot improve
            # fanout once every stage can use its fastest tile.
            if unrestricted:
                break
    return tuple(pareto(candidates))


def dynamic_search(rows, widths, budget, geometries=GEOMETRIES, fuse=True):
    """Keep the joint energy/time frontier until the final product objective."""
    capacities = [c for c in CAPACITIES if c <= budget]
    pairs = tuple(zip(widths, widths[1:]))
    compulsory = boundary_cost(rows, widths[0], widths[-1])

    def bound(geometry):
        x, y = geometry
        score = compulsory
        for k, n in pairs:
            score = add(score, stage_cost(rows, k, n, ceildiv(k, y), ceildiv(n, x), 1, False))
        return score[0] * score[1]

    best = None
    for x, y in sorted(geometries, key=bound):
        if best is not None and bound((x, y)) >= best[0][0] * best[0][1]:
            break
        hardware = Hardware(x, y, max(capacities))
        states = [[((0, 0), ())]]
        for stop in range(1, len(widths)):
            joins = []
            for start in range(0 if fuse else stop - 1, stop):
                segments = segment_frontier(rows, widths, hardware, start, stop)
                joins.extend((add(a, b), left + (right,))
                             for a, left in states[start] for b, right in segments)
            states.append(list(pareto(joins)))
        for cost, plan in states[-1]:
            if best is not None and cost[0] * cost[1] >= best[0][0] * best[0][1]:
                continue
            actual, peak = evaluate(rows, widths, hardware, plan)
            if actual != cost:
                raise AssertionError("dynamic search disagrees with common evaluator")
            best = cost, Hardware(x, y, min(c for c in capacities if c >= peak)), plan
    tile_options.cache_clear()
    if best is None:
        raise ValueError("no feasible joint design")
    return best
