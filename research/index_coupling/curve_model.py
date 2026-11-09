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
Compulsory traffic (graph inputs read once, graph outputs written once) is added
at the top. Every einsum in a group must iterate the group's loop (no recompute).
The result is a Pareto set over this restricted model, not a lower bound.
"""
from functools import lru_cache
from itertools import product
from math import prod


def pareto(points):
    # points: (capacity, traffic, witness); keep the first witness per Pareto point.
    out, best = [], float('inf')
    for point in sorted(points, key=lambda p: (p[0], p[1])):
        if point[1] < best:
            out.append(point)
            best = point[1]
    return tuple(out)


def combine_max_sum(a, b):
    return pareto((max(c1, c2), t1 + t2, w1 + w2) for c1, t1, w1 in a for c2, t2, w2 in b)


def curve(graph, witness=False):
    dims_of = {}
    for op in graph.ops:
        for t, d in graph.access[op].items():
            dims_of.setdefault(t, d)
    produced = {t for op in graph.ops for t in [list(graph.access[op])[-1]]}
    consumed = {t for op in graph.ops for t in list(graph.access[op])[:-1]}
    names = sorted(graph.sizes)

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
                extra = 0
                for t, k in zip(shared, keep_bits):
                    if k:
                        continue
                    gs = users[t]
                    writers = [g for g in gs if any(output_of(op) == t for op in groups[g])]
                    if writers and t in consumed:
                        extra += size(t, ext) * (1 + len(gs) - len(writers))
                    elif writers:
                        extra += 2 * size(t, ext) * (len(writers) - 1)
                    else:
                        extra += size(t, ext) * (len(gs) - 1)
                dropped = tuple(t for t, k in zip(shared, keep_bits) if not k)
                level = ((0, extra, (('groups', tuple(groups), 'kept', tuple(sorted(kept)), 'via DRAM', dropped),)),)
                for g, group in enumerate(groups):
                    across = sum(size(t, ext) for t in kept if min(users[t]) <= g <= max(users[t]))
                    inner = group_curve(group, ext, external | frozenset(kept))
                    level = combine_max_sum(level, tuple((across + c, t, w) for c, t, w in inner))
                    if not level:
                        break
                results.extend(level)
        return pareto(results)

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
                        note = (('loop', group, v, f'tile {b} x{trips}', 'kept', tuple(sorted(kept)),
                                 'refetched', tuple(t for t, k in zip(lacking, keep_bits) if not k)),)
                        results.extend((cap + c, extra + trips * t, note + w) for c, t, w in inner)
                b //= 2
        return pareto(results)

    ext0 = tuple(graph.sizes[v] for v in names)
    inputs = consumed - produced
    outputs = produced - consumed
    compulsory = sum(size(t, ext0) for t in inputs | outputs)
    points = solve(graph.ops, ext0, frozenset())
    return tuple((c, compulsory + t) + ((w,) if witness else ()) for c, t, w in points)
