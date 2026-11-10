"""Price every plan of tiny graphs, not only Pareto witnesses.

Replay of frontier witnesses cannot reveal a plan that the solver overpriced and
discarded. Here graph/curve.py runs with Pareto pruning disabled (every point is
kept, and sibling curves combine by full Cartesian product instead of the
staircase merge), so it returns every plan of its grammar with its model price.
Each plan is executed by simulate_nest.py; a plan passes when its peak and
traffic equal the model's and its outputs are valid. Per-tensor transfers of
failing plans are reported.

Usage (designated server, capped): python -m research.index_coupling.audit_all_plans
    [--legacy] [--limit N]
"""
import argparse
import json
import sys
from collections import Counter

import research.index_coupling.graph.curve as cm
from research.index_coupling.graph.model import coupling, fork, residual
from research.index_coupling.simulate_nest import simulate

GRAPHS = [
    ('coupling_same_2222', coupling(2, 2, 2, 2, False)),
    ('coupling_cross_2222', coupling(2, 2, 2, 2, True)),
    ('fork_kk_2222', fork(2, 2, 2, 2, 'kk')),
    ('fork_kki_2222', fork(2, 2, 2, 2, 'kki')),
    ('residual_222_d2', residual(2, 2, 2, 2, False)),
    ('residual_222_d2_x', residual(2, 2, 2, 2, True)),
    ('residual_222_d3_x', residual(2, 2, 2, 3, True)),
]


def keep_all(points, max_capacity=float('inf'), grid=None):
    return tuple(p for p in points if p[0] <= max_capacity)


def product_max_sum(a, b, max_capacity=float('inf'), grid=None):
    return tuple((max(p[0], q[0]), p[1] + q[1], cm.cat(p[2], q[2]))
                 for p in a for q in b if max(p[0], q[0]) <= max_capacity)


def audit(name, graph, legacy, limit):
    plans = cm.curve(graph, witness=True, legacy_nested_writes=legacy)
    seen, bad, checked = set(), [], 0
    for c, q, w in plans:
        if w in seen:
            continue
        seen.add(w)
        if checked >= limit:
            break
        checked += 1
        a = simulate(graph, w)
        if not a['valid'] or (a['peak'], a['traffic']) != (c, q):
            bad.append(dict(model=[c, q], executed=[a['peak'], a['traffic']], valid=a['valid'],
                            reads=a['reads'], writes=a['writes'], witness=w))
    kinds = Counter((b['model'][1] - b['executed'][1]) for b in bad)
    return dict(graph=name, legacy=legacy, plans=len(plans), distinct=len(seen), checked=checked,
                failures=len(bad), traffic_error_counts={str(k): v for k, v in kinds.items()},
                examples=bad[:3])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy', action='store_true')
    parser.add_argument('--limit', type=int, default=200000)
    parser.add_argument('--only')
    args = parser.parse_args()
    cm.pareto = keep_all
    cm.combine_max_sum = product_max_sum
    total = 0
    for name, graph in GRAPHS:
        if args.only and name != args.only:
            continue
        out = audit(name, graph, args.legacy, args.limit)
        total += out['failures']
        print(json.dumps(out, default=list), flush=True)
    sys.exit(1 if total else 0)
