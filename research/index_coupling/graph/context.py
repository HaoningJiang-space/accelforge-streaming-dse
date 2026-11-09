"""Retention contexts above a partition: loops legal over a whole span.

In the curve grammar a group may loop over rank v only if every op in it uses v
and every tensor produced and consumed inside it carries v (otherwise a consumer
would read partial results). For a contiguous span S this gives the span-legal
ranks R(S), computable from the graph's incidence alone. Every plan for S is a
chain of loops over R(S) (each choosing which tensors lacking the rank stay
resident) that ends at a nontrivial partition or a leaf. So the contexts in
which a cut tensor's retain/spill choice is made are indexed by R(S) tilings
and the kept-set choices along the chain.

lifted_curve composes such chains over an arbitrary bottom curve, independently
of the recursion in curve.py.
"""
from functools import lru_cache
from itertools import product

from research.index_coupling.graph.curve import pareto
from research.index_coupling.graph.model import Graph


def span_ranks(graph, ops):
    common = set.intersection(*(graph.rank_vars((op,)) for op in ops))
    outputs = {graph.output(op) for op in ops}
    inside = outputs & {t for op in ops for t in list(graph.access[op])[:-1]}
    return {v for v in common if all(v in graph.dims(t) for t in inside)}


def with_extent(graph, v, extent):
    return Graph(dict(graph.sizes, **{v: extent}), [(op, graph.access[op]) for op in graph.ops])


def compulsory(graph, external=frozenset()):
    inputs, outputs = graph.consumed() - graph.produced(), graph.produced() - graph.consumed()
    return sum(graph.size(t, ()) for t in (inputs | outputs) - external)


def lifted_curve(graph, v, bottom):
    # bottom(graph_at_extent, external) -> curve of that graph with compulsory
    # traffic included (the convention of curve.curve). Returns the envelope over
    # all power-of-two loop chains on v (including the empty chain) above bottom.
    lacking = sorted(t for t in graph.tensors(graph.ops) if v not in graph.dims(t))

    @lru_cache(maxsize=None)
    def at(extent, kept):
        g = with_extent(graph, v, extent)
        base = compulsory(g, kept)
        points = [(c, t - base, ()) for c, t in bottom(g, kept)]
        b = extent // 2
        while b >= 1:
            trips = extent // b
            free = [t for t in lacking if t not in kept]
            for bits in product((True, False), repeat=len(free)):
                keep = frozenset(t for t, k in zip(free, bits) if k)
                cap = sum(graph.size(t, ()) for t in keep)
                # Lacking tensors are inputs here; refetching costs (trips-1)·size.
                # An accumulated output lacking v would cost spill_cost per refetch.
                if any(t in graph.produced() for t, k in zip(free, bits) if not k):
                    raise NotImplementedError('accumulated output lacking the lifted rank')
                extra = sum((trips - 1) * graph.size(t, ()) for t, k in zip(free, bits) if not k)
                points += [(cap + c, extra + trips * t, ()) for c, t, _ in at(b, kept | keep)]
            b //= 2
        return pareto(points)

    top = compulsory(graph)
    return tuple((c, top + t) for c, t, _ in at(graph.sizes[v], frozenset()))
