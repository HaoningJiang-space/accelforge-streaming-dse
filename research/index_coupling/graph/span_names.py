"""Conservative alpha-equivalence of ordered spans, within one graph.

Ranks, access order, operator order, global tensor roles and consumer counts
are preserved. Only tensor/operator names change; no scheduling is reordered.
"""
from functools import lru_cache


class SpanNames:
    def __init__(self, graph):
        self.graph = graph
        self.produced = graph.produced()
        self.consumed = graph.consumed()
        self.consumers = {t: len(graph.consumers(t)) for t in graph.tensors(graph.ops)}
        self.representatives = {}
        # Instance-local cache: it must not retain completed curve invocations.
        self.lookup = lru_cache(maxsize=None)(self._lookup)

    def _lookup(self, ops):
        ids, names, incidence = {}, [], []
        for op in ops:
            row = []
            for tensor, dims in self.graph.access[op].items():
                if tensor not in ids:
                    ids[tensor] = len(names)
                    names.append(tensor)
                row.append((ids[tensor], tuple(dims)))
            incidence.append(tuple(row))
        roles = tuple((t in self.produced, t in self.consumed, self.consumers[t]) for t in names)
        signature = (tuple(incidence), roles)
        representative, rep_names = self.representatives.setdefault(signature, (ops, tuple(names)))
        return (representative, dict(zip(names, rep_names)),
                (dict(zip(representative, ops)), dict(zip(rep_names, names))))

    def state(self, ops, ext, external, owned):
        rep, forward, backward = self.lookup(ops)
        if rep == ops:
            return (ops, ext, external, owned), None
        return (rep, ext, frozenset(forward[t] for t in external),
                frozenset(forward[t] for t in owned)), backward
