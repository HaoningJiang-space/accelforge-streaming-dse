"""Curve model restricted to the sharing FFM can represent (hypothesis, P14).

FFM shares a tensor between einsums only through its backing reservation
(REVIEW_NOTES_2.md E1), and a DRAM-backed tensor fetched by several consumers
is charged once per consumer. So a multi-consumer intermediate either stays on
chip for all consumers (shared backing) or is materialized: written once and
read separately by each consumer. Multi-consumer graph inputs are always read
separately. The curve is the Pareto union over which intermediates are
materialized.
"""
from itertools import combinations

from research.index_coupling.curve_model import curve, pareto
from research.index_coupling.nest_model import Graph


def consumers(graph, t):
    return [op for op in graph.ops if t in graph.access[op] and list(graph.access[op])[-1] != t]


def separate(graph, tensors):
    # Every consumer of each tensor in `tensors` reads its own DRAM copy; an
    # intermediate with no consumer left becomes a graph output (written once).
    ops = []
    for op in graph.ops:
        out = list(graph.access[op])[-1]
        ops.append((op, {(f'{t}@{op}' if t in tensors and t != out else t): d
                         for t, d in graph.access[op].items()}))
    return Graph(graph.sizes, ops)


def ffm_like_curve(graph, **kwargs):
    produced = {list(graph.access[op])[-1] for op in graph.ops}
    multi = [t for t in graph.tensors(graph.ops) if len(consumers(graph, t)) > 1]
    inputs = {t for t in multi if t not in produced}
    inter = sorted(t for t in multi if t in produced)
    points = []
    for k in range(len(inter) + 1):
        for chosen in combinations(inter, k):
            g = separate(graph, inputs | set(chosen))
            points += [(c, t, ()) for c, t, *_ in curve(g, split_shared=False, **kwargs)]
    return tuple(p[:2] for p in pareto(points))
