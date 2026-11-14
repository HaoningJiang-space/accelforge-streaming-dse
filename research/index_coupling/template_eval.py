"""Evaluate size-free single-operator templates at any extent with the grammar's loop rule.

A template is a sequence of loop levels (axis, kept, refetched) from
template_census.template. At extent s each level picks a tile from the halving
domain of the axis's current extent, or the whole extent (a vacuous level). A level with trips t contributes
  capacity: sizes of its kept tensors,
  traffic:  Q = t * Q_inner + (t - 1) * sum(cost(x) * size(x) for x in refetched),
with cost 2 for the produced tensor and 1 for inputs, sizes at the inner extents.
The leaf requires every non-resident tensor to be a scalar and holds one cell
for each. Compulsory traffic (each input read once, the output written once) is
added, as in curve(). Multi-operator groups are not handled here.
"""
from functools import lru_cache
from itertools import product
from math import prod

from research.index_coupling.graph.curve import pareto, tile_sizes


def evaluate(graph, template):
    """All (capacity, traffic) points the template reaches over its tile choices."""
    (op,) = graph.ops
    tensors = tuple(graph.access[op])
    out = graph.output(op)
    levels = [n for n in template if n[0] == 'loop']
    compulsory = sum(prod(graph.sizes[v] for v in graph.dims(t)) for t in tensors)

    @lru_cache(None)
    def walk(i, ext, resident):
        ext_d = dict(ext)
        size = lambda t: prod(ext_d[v] for v in graph.dims(t))
        if i == len(levels):
            live = [t for t in tensors if t not in resident]
            if any(size(t) != 1 for t in live):
                return ()
            return ((len(live), 0),)
        _, _, axis, kept, refetched = levels[i]
        results = []
        # tile == extent (one trip) makes the level vacuous, so templates also cover degenerate axes.
        for b in tile_sizes(ext_d[axis]) + (ext_d[axis],):
            trips = ext_d[axis] // b
            inner = tuple(sorted({**ext_d, axis: b}.items()))
            inner_d = dict(inner)
            isize = lambda t: prod(inner_d[v] for v in graph.dims(t))
            hold = sum(isize(t) for t in kept)
            extra = (trips - 1) * sum((2 if t == out else 1) * isize(t) for t in refetched)
            for c, q in walk(i + 1, inner, resident | frozenset(kept)):
                results.append((hold + c, trips * q + extra))
        return tuple(results)

    points = walk(0, tuple(sorted(graph.sizes.items())), frozenset())
    return [(c, q + compulsory) for c, q in points]


def frontier(graph, templates):
    return pareto([p for t in templates for p in evaluate(graph, t)])
