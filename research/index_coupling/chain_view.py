"""Single-consumer (chain) view of a graph, as a chain-only model would see it.

Each tensor may pass on chip to its first consumer only; every later consumer
reads its own DRAM copy, and an intermediate with later consumers is also
written to DRAM once. This is the graph curve model applied to the rewritten
graph, so the two views differ only in multi-consumer sharing.
"""
from math import prod

from research.index_coupling.curve_model import curve
from research.index_coupling.nest_model import Graph


def chain_view(graph):
    produced = {list(graph.access[op])[-1] for op in graph.ops}
    seen, ops, extra = set(), [], 0
    for op in graph.ops:
        access = {}
        out = list(graph.access[op])[-1]
        for t, dims in graph.access[op].items():
            if t != out and t in seen:
                access[f'{t}@{op}'] = dims
            else:
                access[t] = dims
                if t != out:
                    seen.add(t)
        ops.append((op, access))
    for t in seen:
        consumers = [op for op in graph.ops if t in graph.access[op] and list(graph.access[op])[-1] != t]
        if t in produced and len(consumers) > 1:
            extra += prod(graph.sizes[v] for v in graph.dims(t))
    return Graph(graph.sizes, ops), extra


def chain_curve(graph, **kwargs):
    rewritten, extra = chain_view(graph)
    return tuple((c, t + extra) + tuple(rest) for c, t, *rest in curve(rewritten, **kwargs))
