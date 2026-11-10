"""Frozen P21d first-partition candidates from incidence alone.

No tensor size, curve, capacity, traffic, witness, or old cut menu is consulted.
See PROTOCOL.md for the exact adjacent-rank and last-crossing-use definitions.
"""
from research.index_coupling.graph.context import span_ranks


def structural_cuts(graph, ops=None):
    ops = graph.ops if ops is None else tuple(ops)
    n = len(ops)
    accesses, consumers, producers = {}, {}, {}
    for i, op in enumerate(ops):
        output = graph.output(op)
        for tensor in graph.access[op]:
            accesses.setdefault(tensor, []).append(i)
            if tensor == output:
                producers[tensor] = i
            else:
                consumers.setdefault(tensor, []).append(i)
    reasons = {k: [] for k in range(1, n)}
    for k in reasons:
        before, after = span_ranks(graph, ops[k-1:]), span_ranks(graph, ops[k:])
        if before != after:
            reasons[k].append(dict(kind='suffix_rank_change', before=sorted(before), after=sorted(after)))
        if k >= 2:
            before, after = span_ranks(graph, ops[:k-1]), span_ranks(graph, ops[:k])
            if before != after:
                reasons[k].append(dict(kind='prefix_rank_change', before=sorted(before), after=sorted(after)))
        for tensor in sorted(consumers):
            uses = consumers[tensor]
            if (uses[-1] == k-1 and len(accesses[tensor]) >= 2
                    and min(accesses[tensor]) < k-1):
                reasons[k].append(dict(kind='last_crossing_use', tensor=tensor,
                                      accesses=accesses[tensor], consumers=uses,
                                      producer=producers.get(tensor)))
    selected = [k for k in reasons if reasons[k]]
    return dict(ops=list(ops), positions=selected,
                excluded=[k for k in reasons if not reasons[k]],
                reasons=[dict(position=k, events=reasons[k]) for k in reasons],
                selected_positions=len(selected), total_positions=n-1,
                allowed_partitions=2**len(selected), total_partitions=2**(n-1),
                nontrivial_allowed_partitions=2**len(selected)-1,
                vacuous=len(selected)==n-1)
