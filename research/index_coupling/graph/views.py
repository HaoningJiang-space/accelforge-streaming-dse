"""Graph rewrites that restrict how a multi-consumer tensor may be shared.

Both views apply the unchanged curve model (curve.py) to a rewritten graph, so
they differ from the graph curve only in multi-consumer sharing.

Chain view: a tensor may pass on chip to its first consumer only. Every later
consumer reads its own DRAM copy, and an intermediate with later consumers is
written to DRAM exactly once. That write is charged here and not again when the
plan also materializes the tensor for its first consumer. The first version
charged it twice; the chain columns of results/classify_small.jsonl have that
error.

FFM-like view (hypothesis, P14): FFM shares a tensor between einsums only through
its backing reservation (REVIEW_NOTES_2.md E1), and a DRAM-backed tensor fetched
by several consumers is charged once per consumer. So a multi-consumer
intermediate either stays on chip for all its consumers (shared backing) or is
materialized: written once and read separately by each consumer. Multi-consumer
graph inputs are always read separately. The curve is the Pareto union over
which intermediates are materialized.
"""
from itertools import combinations

from research.index_coupling.graph.curve import curve, pareto
from research.index_coupling.graph.model import Graph


def chain_view(graph):
    produced = graph.produced()
    seen, ops, extra, written = set(), [], 0, set()
    for op in graph.ops:
        access = {}
        out = graph.output(op)
        for t, dims in graph.access[op].items():
            if t != out and t in seen:
                access[f'{t}@{op}'] = dims
            else:
                access[t] = dims
                if t != out:
                    seen.add(t)
        ops.append((op, access))
    for t in seen:
        if t in produced and len(graph.consumers(t)) > 1:
            extra += graph.size(t, ())
            written.add(t)
    return Graph(graph.sizes, ops), extra, frozenset(written)


def chain_curve(graph, **kwargs):
    rewritten, extra, written = chain_view(graph)
    return tuple((c, t + extra) + tuple(rest) for c, t, *rest in curve(rewritten, written=written, **kwargs))


def separate(graph, tensors):
    # Every consumer of each tensor in `tensors` reads its own DRAM copy; an
    # intermediate with no consumer left becomes a graph output (written once).
    ops = []
    for op in graph.ops:
        out = graph.output(op)
        ops.append((op, {(f'{t}@{op}' if t in tensors and t != out else t): d
                         for t, d in graph.access[op].items()}))
    return Graph(graph.sizes, ops)


def multi_consumer(graph):
    # (graph inputs, intermediates) read by more than one einsum.
    produced = graph.produced()
    multi = [t for t in graph.tensors(graph.ops) if len(graph.consumers(t)) > 1]
    return {t for t in multi if t not in produced}, sorted(t for t in multi if t in produced)


def ffm_like_part(graph, materialized, separate_inputs=True, **kwargs):
    # One member of the FFM-like union: these intermediates are materialized.
    # separate_inputs=False leaves multi-consumer graph inputs to the curve model
    # (shared on chip, or read once per group), as for copy-wrapped inputs (P14-FFN').
    inputs, _ = multi_consumer(graph)
    return curve(separate(graph, (inputs if separate_inputs else set()) | set(materialized)),
                 split_shared=False, **kwargs)


def ffm_like_curve(graph, **kwargs):
    _, inter = multi_consumer(graph)
    points = []
    for k in range(len(inter) + 1):
        for chosen in combinations(inter, k):
            points += [(c, t, ()) for c, t, *_ in ffm_like_part(graph, chosen, **kwargs)]
    return tuple(p[:2] for p in pareto(points))
