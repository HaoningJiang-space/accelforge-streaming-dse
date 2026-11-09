"""Search-free plateau model: minimum buffer for zero extra DRAM traffic.

An execution is a recursive loop nest over the einsums in their given order.
At each level, the current einsum sequence is split into consecutive groups and
each group opens one loop over a rank variable t.
- A tensor touched by the group but not indexed by t stays whole (at the current
  slice granularity) for the group, otherwise it would be refetched or spilled.
- A tensor touched by two or more groups at this level stays whole from its
  first to its last group, for the same reason.
- Recursion ends when every tensor in a group is a scalar; each remaining
  scalar that is not already held costs one element.
Peak = max over groups of (whole tensors live across groups + held tensors of
the group + the group's inner peak). The plateau prediction is the minimum peak.
This is a constructive model of a restricted mapspace, not a lower bound.
"""
from functools import lru_cache
from math import prod


class Graph:
    def __init__(self, sizes, ops):
        # ops: list of (name, {tensor: (rank variables, ...)}); output listed last.
        self.sizes = sizes
        self.ops = tuple(name for name, _ in ops)
        self.access = {name: acc for name, acc in ops}

    def tensors(self, ops):
        return {t for op in ops for t in self.access[op]}

    def dims(self, tensor):
        for op in self.ops:
            if tensor in self.access[op]:
                return self.access[op][tensor]
        raise KeyError(tensor)

    def size(self, tensor, sliced):
        # Each projection is a list of distinct rank variables; sizes come from them.
        return prod(self.sizes[v] for v in self.dims(tensor) if v not in sliced)

    def rank_vars(self, ops):
        return {v for op in ops for dims in self.access[op].values() for v in dims}


def plateau(graph):
    # Rank variables are renamed per einsum in AccelForge, but a tensor's dimension
    # identity is what matters: we key slicing by tensor dimension names.
    @lru_cache(maxsize=None)
    def peak(ops, sliced, external):
        live = graph.tensors(ops) - external
        unsliced = {v for t in live for v in graph.dims(t) if v not in sliced}
        if not unsliced:
            return len(live)
        best = float('inf')
        n = len(ops)
        for mask in range(1 << (n - 1)):
            groups, start = [], 0
            for i in range(n - 1):
                if mask >> i & 1:
                    groups.append(ops[start:i + 1])
                    start = i + 1
            groups.append(ops[start:])
            span = {}
            for g, group in enumerate(groups):
                for t in graph.tensors(group) - external:
                    first, last = span.get(t, (g, g))
                    span[t] = (min(first, g), max(last, g))
            shared = {t for t, (a, b) in span.items() if b > a}
            worst = 0
            for g, group in enumerate(groups):
                across = sum(graph.size(t, sliced) for t in shared if span[t][0] <= g <= span[t][1])
                inside = graph.tensors(group) - external - shared
                choices = {v for t in inside | (graph.tensors(group) & shared)
                           for v in graph.dims(t) if v not in sliced}
                group_best = float('inf')
                if not choices:
                    group_best = len(inside)
                for v in choices:
                    held = {t for t in inside if v not in graph.dims(t)}
                    cost = sum(graph.size(t, sliced) for t in held)
                    cost += peak(group, sliced | {v}, external | shared | frozenset(held))
                    group_best = min(group_best, cost)
                worst = max(worst, across + group_best)
                if worst >= best:
                    break
            best = min(best, worst)
        return best

    return peak(graph.ops, frozenset(), frozenset())


def coupling(ni, nj, nk, nl, cross):
    # Tensor dimensions are named by the rank they index (I, J, K, L).
    ev = {'D': ('L', 'I'), 'X': ('I', 'K'), 'V': ('L', 'K')} if cross else \
         {'X': ('I', 'K'), 'D': ('K', 'L'), 'V': ('I', 'L')}
    return Graph(dict(I=ni, J=nj, K=nk, L=nl), [
        ('EX', {'A': ('I', 'J'), 'B': ('J', 'K'), 'X': ('I', 'K')}),
        ('EU', {'X': ('I', 'K'), 'C': ('K', 'L'), 'U': ('I', 'L')}),
        ('EV', ev),
    ])


def ffn(m, d, f):
    # Copy einsums (is_copy_operation) reserve no buffer in AccelForge; they only
    # make a multi-consumer input shareable. They are modeled as aliases: X, W1, W2
    # and dY are inputs read once, kept whole by the cross-group rule when needed.
    ops = [
        ('EH', {'X': ('M', 'D'), 'W1': ('D', 'F'), 'H': ('M', 'F')}),
        ('EZ', {'H': ('M', 'F'), 'Z': ('M', 'F')}),
        ('EY', {'Z': ('M', 'F'), 'W2': ('F', 'E'), 'Y': ('M', 'E')}),
        ('EdW2', {'Z': ('M', 'F'), 'dY': ('M', 'E'), 'dW2': ('F', 'E')}),
        ('EdZ', {'dY': ('M', 'E'), 'W2': ('F', 'E'), 'dZ': ('M', 'F')}),
        ('EdH', {'dZ': ('M', 'F'), 'H': ('M', 'F'), 'dH': ('M', 'F')}),
        ('EdW1', {'X': ('M', 'D'), 'dH': ('M', 'F'), 'dW1': ('D', 'F')}),
        ('EdX', {'dH': ('M', 'F'), 'W1': ('D', 'F'), 'dX': ('M', 'D')}),
    ]
    return Graph(dict(M=m, D=d, F=f, E=d), ops)


if __name__ == '__main__':
    import sys
    for label, graph, measured in [
        ('square n=4 same', coupling(4, 4, 4, 4, False), 21),
        ('square n=8 cross', coupling(8, 8, 8, 8, True), 73),
        ('square n=16 same', coupling(16, 16, 16, 16, False), 273),
        ('T2 64,8,8,8 same', coupling(64, 8, 8, 8, False), 201),
        ('T2 64,8,8,8 cross', coupling(64, 8, 8, 8, True), 201),
        ('T3 8,32,32,32 cross', coupling(8, 32, 32, 32, True), 265),
        ('FFN M8 D4 F8', ffn(8, 4, 8), 147),
        ('FFN M16 D4 F8', ffn(16, 4, 8), 147),
        ('FFN M4 D4 F16', ffn(4, 4, 16), 81),
    ]:
        print(f'{label:22s} model {plateau(graph):6} measured {measured}', flush=True)
