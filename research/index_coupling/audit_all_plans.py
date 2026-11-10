"""Execute unpruned plans lazily, with generation and wall-time budgets.

Counts derivations including duplicate witnesses; no unbounded deduplication set.
Only iterator exhaustion is complete coverage. A limited prefix is never a pass.
Usage: python -m research.index_coupling.audit_all_plans --only NAME
       [--legacy] [--limit N] [--nodes N] [--seconds S] [--mem-gib G]
"""
import argparse
import json
import resource
import signal
import sys
from collections import Counter
from time import monotonic

from research.index_coupling.graph.model import coupling, fork, residual
from research.index_coupling.graph.plan_stream import Budget, BudgetExceeded, iter_plans
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


def audit(name, graph, legacy=False, limit=200000, *, nodes=20_000_000, seconds=3600):
    if min(limit, nodes, seconds) <= 0:
        raise ValueError('audit budgets must be positive')
    begin = monotonic()
    budget = Budget(nodes, begin + seconds)
    plans = iter_plans(graph, legacy_nested_writes=legacy, budget=budget)
    checked, failures, examples, kinds = 0, 0, [], Counter()
    status = 'plan_limit'
    try:
        while checked < limit:
            try:
                c, q, w = next(plans)
            except StopIteration:
                status = 'complete'
                break
            a = simulate(graph, w)
            checked += 1
            if not a['valid'] or (a['peak'], a['traffic']) != (c, q):
                failures += 1
                kinds[q - a['traffic']] += 1
                if len(examples) < 3:
                    examples.append(dict(model=[c, q], executed=[a['peak'], a['traffic']],
                                         valid=a['valid'], reads=a['reads'], writes=a['writes'], witness=w))
    except BudgetExceeded as exc:
        status = str(exc)
    except MemoryError:
        status = 'memory'
    finally:
        plans.close()
    return dict(graph=name, legacy=legacy, status=status, complete=status == 'complete',
                counting='derivations_including_duplicates', checked=checked,
                expanded=budget.expanded, failures=failures,
                traffic_error_counts={str(k): v for k, v in kinds.items()}, examples=examples,
                seconds=monotonic() - begin,
                budgets=dict(plans=limit, nodes=nodes, seconds=seconds))


def timeout(_signum, _frame):
    raise BudgetExceeded('timeout')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy', action='store_true')
    parser.add_argument('--limit', type=int, default=200000)
    parser.add_argument('--nodes', type=int, default=20_000_000)
    parser.add_argument('--seconds', type=float, default=3600)
    parser.add_argument('--mem-gib', type=float, default=8)
    parser.add_argument('--only', choices=[name for name, _ in GRAPHS])
    args = parser.parse_args()
    if min(args.limit, args.nodes, args.seconds, args.mem_gib) <= 0:
        parser.error('budgets must be positive')
    cap = int(args.mem_gib * 2**30)
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    signal.signal(signal.SIGALRM, timeout)
    outputs = []
    for name, graph in GRAPHS:
        if args.only and name != args.only:
            continue
        signal.setitimer(signal.ITIMER_REAL, args.seconds)
        try:
            out = audit(name, graph, args.legacy, args.limit, nodes=args.nodes, seconds=args.seconds)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        outputs.append(out)
        print(json.dumps(out, default=list), flush=True)
    sys.exit(1 if any(o['failures'] for o in outputs) else
             2 if any(not o['complete'] for o in outputs) else 0)
