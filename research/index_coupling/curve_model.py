"""Capacity-traffic Pareto curve from loop nests, without FFM search.

Extends nest_model.py. Instead of forcing zero extra traffic, a tensor may
be left out of the buffer and pay DRAM traffic:
- In a group looping over v with tile b (T = extent/b trips), a tensor lacking v
  is either kept whole (capacity) or refetched every trip: an input pays
  (T-1)·size extra reads; an accumulated output pays 2·(T-1)·size (partial sums
  written and read back). An intermediate produced and consumed inside the same
  group must not lack v (its consumer would read partial sums), so v is illegal.
- A tensor used by several sibling groups is either kept across them or goes
  through DRAM: an intermediate is written once and read by each consuming group;
  a graph input is read once per group.
- Loops may be split by powers of two; inner levels see the tile extent.
- written: intermediates whose single DRAM write the caller charges; passing
  them via DRAM then costs only the reads.
- split_shared=False forbids a multi-consumer intermediate from going via DRAM.
- write_through=False forbids an intermediate from both feeding a consumer in its
  producer's group on chip and going to DRAM for another group.
Compulsory traffic (graph inputs read once, graph outputs written once) is added
at the top. Every einsum in a group must iterate the group's loop (no recompute).
The result is a Pareto set over this restricted model, not a lower bound.
"""
from functools import lru_cache
from itertools import product
from math import floor, log, prod


_CAT = object()  # witness concatenation node; flattened once at the end


def cat(a, b):
    return b if not a else a if not b else (_CAT, a, b)


def flatten(witness):
    out, stack = [], [witness]
    while stack:
        w = stack.pop()
        if w and w[0] is _CAT:
            stack.extend((w[2], w[1]))
        else:
            out.extend(w)
    return tuple(out)


def pareto(points, max_capacity=float('inf'), grid=None):
    # points: (capacity, traffic, witness); keep the first witness per Pareto point.
    # With grid g > 1, only the lowest-traffic point per capacity bucket [g^k, g^(k+1))
    # is kept: every dropped point has a kept one with traffic no higher and capacity
    # less than g times larger. Kept points stay exact and executable.
    out, best = [], float('inf')
    for point in sorted(points, key=lambda p: (p[0], p[1])):
        if point[0] > max_capacity:
            break
        if point[1] < best:
            if grid and out and bucket(out[-1][0], grid) == bucket(point[0], grid):
                out.pop()
            out.append(point)
            best = point[1]
    return tuple(out)


def bucket(capacity, grid):
    return floor(log(capacity, grid)) if capacity > 0 else -1


def combine_max_sum(a, b, max_capacity=float('inf'), grid=None):
    # a, b are Pareto staircases (capacity ascending, traffic descending). The best
    # pair within capacity c is the staircase value of each at c, so one sweep over
    # the union of capacities replaces the |a|·|b| cross product.
    out, i, j = [], -1, -1
    for c in sorted({p[0] for p in a} | {p[0] for p in b}):
        if c > max_capacity:
            break
        while i + 1 < len(a) and a[i + 1][0] <= c:
            i += 1
        while j + 1 < len(b) and b[j + 1][0] <= c:
            j += 1
        if i >= 0 and j >= 0:
            out.append((max(a[i][0], b[j][0]), a[i][1] + b[j][1], cat(a[i][2], b[j][2])))
    return pareto(out, grid=grid)


def curve(graph, witness=False, max_capacity=float('inf'), grid=None, write_through=True,
          written=frozenset(), split_shared=True):
    # Points above max_capacity are dropped in every subproblem: capacities only grow
    # when subresults are combined, so the curve up to max_capacity is unchanged.
    dims_of = {}
    for op in graph.ops:
        for t, d in graph.access[op].items():
            dims_of.setdefault(t, d)
    produced = {t for op in graph.ops for t in [list(graph.access[op])[-1]]}
    consumed = {t for op in graph.ops for t in list(graph.access[op])[:-1]}
    names = sorted(graph.sizes)
    n_consumers = {t: sum(t in graph.access[op] and list(graph.access[op])[-1] != t for op in graph.ops)
                   for t in dims_of}

    def size(t, ext):
        return prod(ext[names.index(v)] for v in dims_of[t])

    def output_of(op):
        return list(graph.access[op])[-1]

    @lru_cache(maxsize=None)
    def solve(ops, ext, external):
        live = graph.tensors(ops) - external
        if all(size(t, ext) == 1 for t in live):
            return ((len(live), 0, ()),)
        results = []
        n = len(ops)
        for mask in range(1 << (n - 1)):
            groups, start = [], 0
            for i in range(n - 1):
                if mask >> i & 1:
                    groups.append(ops[start:i + 1])
                    start = i + 1
            groups.append(ops[start:])
            users = {}
            for g, group in enumerate(groups):
                for t in graph.tensors(group) - external:
                    users.setdefault(t, []).append(g)
            shared = sorted(t for t, gs in users.items() if len(gs) > 1)
            for keep_bits in product((True, False), repeat=len(shared)):
                kept = {t for t, k in zip(shared, keep_bits) if k}
                if not split_shared and any(not k and t in produced and n_consumers[t] > 1
                                            for t, k in zip(shared, keep_bits)):
                    # A multi-consumer intermediate either stays on chip for all its
                    # consumers or is fully materialized by rewriting (ffm_like.py).
                    continue
                if not write_through and any(
                        not k and any(output_of(op) == t for op in groups[g]) and
                        any(t in graph.access[op] and output_of(op) != t for op in groups[g])
                        for t, k in zip(shared, keep_bits) for g in users[t]):
                    # Write-through: t feeds a consumer in its producer's group on chip
                    # and also goes to DRAM for another group. FFM shares a tensor
                    # between einsums through one backing reservation only.
                    continue
                extra = 0
                for t, k in zip(shared, keep_bits):
                    if k:
                        continue
                    gs = users[t]
                    writers = [g for g in gs if any(output_of(op) == t for op in groups[g])]
                    if writers and t in consumed:
                        # The write is skipped for tensors whose one DRAM write the
                        # caller charges separately (chain_view.py).
                        extra += size(t, ext) * ((t not in written) + len(gs) - len(writers))
                    elif writers:
                        extra += 2 * size(t, ext) * (len(writers) - 1)
                    else:
                        extra += size(t, ext) * (len(gs) - 1)
                dropped = tuple(t for t, k in zip(shared, keep_bits) if not k)
                level = ((0, extra, (('groups', tuple(groups), 'kept', tuple(sorted(kept)), 'via DRAM', dropped),)
                          if witness else ()),)
                for g, group in enumerate(groups):
                    across = sum(size(t, ext) for t in kept if min(users[t]) <= g <= max(users[t]))
                    inner = group_curve(group, ext, external | frozenset(kept))
                    level = combine_max_sum(level, pareto(((across + c, t, w) for c, t, w in inner), max_capacity), max_capacity, grid)
                    if not level:
                        break
                results.extend(level)
        return pareto(results, max_capacity, grid)

    @lru_cache(maxsize=None)
    def group_curve(group, ext, external):
        live = graph.tensors(group) - external
        if all(size(t, ext) == 1 for t in live):
            return ((len(live), 0, ()),)
        common = set.intersection(*(graph.rank_vars((op,)) for op in group))
        inside_made = {output_of(op) for op in group} & {t for op in group for t in list(graph.access[op])[:-1]}
        results = []
        for v in common:
            i = names.index(v)
            extent = ext[i]
            if extent == 1 or any(v not in dims_of[t] for t in inside_made - external):
                continue
            lacking = sorted(t for t in live if v not in dims_of[t])
            b = extent // 2
            while b >= 1:
                if extent % b == 0:
                    trips = extent // b
                    inner_ext = ext[:i] + (b,) + ext[i + 1:]
                    for keep_bits in product((True, False), repeat=len(lacking)):
                        kept = frozenset(t for t, k in zip(lacking, keep_bits) if k)
                        cap = sum(size(t, ext) for t in kept)
                        extra = 0
                        for t, k in zip(lacking, keep_bits):
                            if not k:
                                accumulated = any(output_of(op) == t for op in group)
                                extra += (2 if accumulated else 1) * (trips - 1) * size(t, ext)
                        inner = solve(group, inner_ext, external | kept)
                        note = () if not witness else (('loop', group, v, f'tile {b} x{trips}', 'kept', tuple(sorted(kept)),
                                 'refetched', tuple(t for t, k in zip(lacking, keep_bits) if not k)),)
                        results.extend((cap + c, extra + trips * t, cat(note, w)) for c, t, w in inner)
                b //= 2
        return pareto(results, max_capacity, grid)

    ext0 = tuple(graph.sizes[v] for v in names)
    inputs = consumed - produced
    outputs = produced - consumed
    compulsory = sum(size(t, ext0) for t in inputs | outputs)
    points = solve(graph.ops, ext0, frozenset())
    return tuple((c, compulsory + t) + ((flatten(w),) if witness else ()) for c, t, w in points)
