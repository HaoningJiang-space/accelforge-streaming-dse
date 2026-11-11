"""Work-weighted sufficiency census of candidate sharing keys (before building any cache).

For each case, every symmetry-representative global order is solved natively
with the C2-audit recorder, which stores each memoised state's exact frontier
and exclusive work. Natively, each order has its own cache, so a state seen in
k orders costs k times its work.

A candidate sharing key maps states to classes. A class is *sufficient* when
all its members have the same frontier, so one computation could serve them
all exactly. For each key we report the share of classes that are sufficient
and the work it could remove: for every sufficient class, total member work
minus its costliest member. This is a ceiling for any implementation of that
key, before lookup, memory or witness costs.

Keys:
- order_local: native (state identity within one order); ceiling 0 by definition;
- cross_order: the same state across orders (the Gate 2 pool);
- unordered_ops: ignore the internal order of a span's operators;
- renamed: SpanNames alpha-equivalence (tensor/operator renaming), across orders;
- renamed_unordered: both.

Usage: python -m research.dag_mapping.work_census OUT.jsonl [CASE ...]
"""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

from research.index_coupling.c2_bound_audit import BaselineRecorder, COUNTERS
from research.index_coupling.census_tools import graph_of
from research.index_coupling.graph.span_names import SpanNames
from .bench_reuse import graph_for, select_orders
from .boundary import resized

DAG_CASES = ('fork_join_tiny', 'two_stage_join', 'asymmetric_join', 'mixed_join')
CHAIN_CASES = ('ffn_forward_l1_m8', 'ffn_forward_l2_m8')


def record(case):
    """(graph, list of (order index, node)) for every representative order."""
    if case in CHAIN_CASES:
        graph = graph_of(case)
        orders = (graph.ops,)
    else:
        graph = graph_for(case)
        orders, _, _ = select_orders(graph, True)
    nodes = []
    for index, order in enumerate(orders):
        recorder = BaselineRecorder()
        data = recorder.run(resized(graph, graph.sizes, order) if case not in CHAIN_CASES else graph)
        nodes.extend((index, n) for n in data['nodes'])
    return graph, len(orders), nodes


def keys(graph):
    names = SpanNames(graph)

    def renamed(s):
        state, _ = names.state(tuple(s['ops']), tuple(s['ext']), frozenset(s['external']), frozenset(s['owned']))
        ops, ext, external, owned = state
        return ops, ext, tuple(sorted(external)), tuple(sorted(owned))

    def base(s):
        return s['stage'], s['constrained']

    return {
        'order_local': lambda i, s: (i, base(s), tuple(s['ops']), tuple(s['ext']),
                                     tuple(s['external']), tuple(s['owned'])),
        'cross_order': lambda i, s: (base(s), tuple(s['ops']), tuple(s['ext']),
                                     tuple(s['external']), tuple(s['owned'])),
        'unordered_ops': lambda i, s: (base(s), frozenset(s['ops']), tuple(s['ext']),
                                       tuple(s['external']), tuple(s['owned'])),
        'renamed': lambda i, s: (base(s), renamed(s)),
        'renamed_unordered': lambda i, s: (base(s), frozenset(renamed(s)[0]), renamed(s)[1:]),
    }


def census(case):
    graph, n_orders, nodes = record(case)
    total = {k: sum(n['work'][k] for _, n in nodes) for k in COUNTERS}
    out = dict(case=case, orders=n_orders, states=len(nodes), total_work=total, keys={})
    for name, key in keys(graph).items():
        classes = defaultdict(list)
        for i, n in nodes:
            classes[key(i, n['state'])].append(n)
        sufficient = saved = 0
        saved_work = Counter()
        insufficient_work = Counter()
        multi = 0
        for members in classes.values():
            if len(members) < 2:
                continue
            multi += 1
            same = len({tuple(map(tuple, m['points'])) for m in members}) == 1
            for k in COUNTERS:
                excess = sum(m['work'][k] for m in members) - max(m['work'][k] for m in members)
                (saved_work if same else insufficient_work)[k] += excess
            sufficient += same
        out['keys'][name] = dict(
            classes=len(classes), multi_member_classes=multi, sufficient_multi=sufficient,
            removable_fraction={k: round(saved_work[k] / total[k], 4) if total[k] else None for k in COUNTERS},
            blocked_by_insufficiency={k: round(insufficient_work[k] / total[k], 4) if total[k] else None
                                      for k in COUNTERS})
    # Where the expensive work sits: DP transitions by span length and entry.
    by_span = Counter()
    for _, n in nodes:
        by_span[(n['state']['stage'], len(n['state']['ops']))] += n['work']['dp_transitions']
    ranked = sorted((n['work']['dp_transitions'] for _, n in nodes), reverse=True)
    top = max(1, len(ranked) // 100)
    out['dp_by_stage_and_span'] = {f'{s}:{l}': v for (s, l), v in sorted(by_span.items())}
    out['dp_share_of_top_1pct_states'] = round(sum(ranked[:top]) / max(1, sum(ranked)), 4)
    out['dp_share_of_top_10pct_states'] = round(sum(ranked[:max(1, len(ranked) // 10)]) / max(1, sum(ranked)), 4)
    return out


def main(argv):
    out = Path(argv[0])
    cases = argv[1:] or list(DAG_CASES + CHAIN_CASES)
    with out.open('w') as stream:
        for case in cases:
            row = census(case)
            stream.write(json.dumps(row) + '\n')
            stream.flush()
            print(json.dumps(dict(case=case, orders=row['orders'], states=row['states'],
                                  keys={k: v['removable_fraction']['dp_transitions'] for k, v in row['keys'].items()})),
                  flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
