"""Plateau model without FFM search: minimum buffer for zero extra DRAM traffic.

An execution is a recursive loop nest over the einsums in their given order.
At each level, the current einsum sequence is split into consecutive groups and
each group opens one loop over a rank variable t.
- A tensor touched by the group but not indexed by t stays whole (at the current
  slice granularity) for the group, otherwise it would be refetched or spilled.
- A tensor touched by two or more groups at this level stays whole from its
  first to its last group, for the same reason.
- The loop index must be iterated by every einsum in the group (no recomputation).
- Recursion ends when every tensor in a group is a scalar; each remaining
  scalar that is not already held costs one element.
Peak = max over groups of (whole tensors live across groups + held tensors of
the group + the group's inner peak). The plateau prediction is the minimum peak.
This is a constructive model of a restricted mapspace, not a lower bound.
"""
from functools import lru_cache


def plateau(graph, witness=False):
    """Minimum peak; with witness=True also return the nest that attains it."""
    # Slicing is keyed by tensor dimension names (I, J, K, L or M, D, F, E).
    @lru_cache(maxsize=None)
    def peak(ops, sliced, external):
        live = graph.tensors(ops) - external
        unsliced = {v for t in live for v in graph.dims(t) if v not in sliced}
        if not unsliced:
            return len(live), ('scalars', tuple(sorted(live)))
        best = (float('inf'), None)
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
            worst, parts = 0, []
            for g, group in enumerate(groups):
                across = {t: graph.size(t, sliced) for t in shared if span[t][0] <= g <= span[t][1]}
                inside = graph.tensors(group) - external - shared
                # A loop may only be opened over an index every einsum in the group
                # iterates; otherwise an einsum would be recomputed per iteration.
                choices = set.intersection(*(graph.rank_vars((op,)) for op in group)) - sliced
                choices &= {v for t in inside | (graph.tensors(group) & shared) for v in graph.dims(t)}
                group_best = (float('inf'), None)
                if not {v for t in graph.tensors(group) - external for v in graph.dims(t)} - sliced:
                    group_best = (len(inside), ('scalars', tuple(sorted(inside))))
                for v in sorted(choices):
                    held = {t for t in inside if v not in graph.dims(t)}
                    inner = peak(group, sliced | {v}, external | shared | frozenset(held))
                    cost = sum(graph.size(t, sliced) for t in held) + inner[0]
                    if cost < group_best[0]:
                        group_best = (cost, ('loop', v, {t: graph.size(t, sliced) for t in sorted(held)}, inner[1]))
                worst = max(worst, sum(across.values()) + group_best[0])
                parts.append((group, across, group_best))
                if worst >= best[0]:
                    break
            if worst < best[0]:
                best = (worst, ('groups', parts))
        return best

    value, nest = peak(graph.ops, frozenset(), frozenset())
    return (value, nest) if witness else value


def show(nest, indent=0):
    pad = ' ' * indent
    if nest[0] == 'scalars':
        print(pad + 'scalars', nest[1])
    elif nest[0] == 'loop':
        print(pad + f'loop {nest[1]}, held {nest[2]}')
        show(nest[3], indent + 2)
    else:
        for group, across, (cost, inner) in nest[1]:
            print(pad + f'group {group}, kept across groups {across}, cost {cost}')
            show(inner, indent + 2)
