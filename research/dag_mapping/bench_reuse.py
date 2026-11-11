"""Frozen cross-order closed-response audit and matched-baseline experiment."""
import argparse
import gc
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
from time import perf_counter

from research.index_coupling.graph.curve import curve, pareto
from research.index_coupling.simulate_nest import simulate
from .boundary import resized
from .hierarchy import analyze, decode
from .reuse import RegionSession
from .workloads import D1_CASES, dag_graph as graph_for, select_orders
from .artifacts import source_set, source_hashes, verify_sources


CASES = tuple(D1_CASES) + ('two_stage_join', 'asymmetric_join', 'mixed_join')
TIMED_CASES = ('residual_rectangle', 'fork_join_tiny', 'two_stage_join', 'asymmetric_join', 'mixed_join')
ARMS = ('native', 'prefix_all', 'sym_prefix', 'sym_shared', 'sym_analytic', 'sym_analytic_shared')
SOURCES = source_set(
    'research/dag_mapping/bench_reuse.py', 'research/dag_mapping/test_reuse.py',
    'research/dag_mapping/INTERFACE_PLAN.md',
)


def run_arm(name, arm, *, profile=False, audit=False):
    started = perf_counter()
    graph = graph_for(name)
    orders, all_orders, automorphisms = select_orders(graph, arm.startswith('sym_'))
    requested = arm in ('sym_shared', 'sym_analytic_shared')
    # With one representative and one root query there is no cross-order work.
    enabled = requested and len(orders) > 1
    analytic = arm in ('sym_analytic', 'sym_analytic_shared')
    session = None if arm == 'native' else RegionSession(
        graph, shared=enabled, unit=analytic, certificate=analytic, audit=audit)
    setup = perf_counter() - started
    started = perf_counter()
    aggregate, per_order, work = [], [], []
    for order in orders:
        ledger = {} if profile else None
        if session is None:
            points = curve(resized(graph, graph.sizes, order), witness=True,
                           scalar_leaf='v2', partitions='dp', stats=ledger)
        else:
            points = session.query(order, stats=ledger)
        aggregate.extend((c, q, (order, notes)) for c, q, notes in points)
        per_order.append(dict(order=order, frontier=[list(p[:2]) for p in points]))
        if profile:
            work.append(ledger)
    selected = pareto(aggregate)
    recovery_start = perf_counter()
    witnesses = [dict(order=order, notes=session.recover(notes) if session else notes)
                 for _, _, (order, notes) in selected]
    recovery = perf_counter() - recovery_start
    generation = perf_counter() - started
    memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    replay_start = perf_counter()
    replays = []
    for (c, q, _), witness in zip(selected, witnesses):
        ordered = resized(graph, graph.sizes, witness['order'])
        checked = analyze(ordered, decode(ordered, witness['notes']))
        actual = simulate(ordered, witness['notes'], scalar_leaf='v2')
        if (not actual['valid'] or (actual['peak'], actual['traffic']) != (c, q)
                or (checked['peak'], checked['traffic']) != (c, q)):
            raise AssertionError('destination-parent witness replay mismatch')
        replays.append(dict(point=[c, q], actual=actual))
    fields = ('dp_transitions', 'loop_choices', 'pareto_candidates', 'exact_checks', 'exact_hits',
              'separator_checks', 'separator_hits')
    summary = {k: sum(s.get(k, 0) for s in work) for k in fields} if profile else None
    if profile:
        summary.update(local_solve_misses=sum(s['solve_cache']['misses'] for s in work),
                       local_group_misses=sum(s['group_cache']['misses'] for s in work))
    return dict(case=name, arm=arm, all_orders=all_orders, searched_orders=len(orders),
                automorphisms=automorphisms, sharing_enabled=enabled,
                setup_seconds=setup, generation_seconds=generation,
                inclusive_seconds=setup+generation, recovery_seconds=recovery,
                replay_seconds=perf_counter()-replay_start, pre_replay_peak_rss_kib=memory,
                frontier=[list(p[:2]) for p in selected], order_frontiers=per_order,
                witnesses=witnesses, replays=replays, work=summary,
                pool=session.pool.summary() if enabled else None)


def audit_case(name):
    rows, reference = [], None
    for arm in ARMS:
        row = run_arm(name, arm, profile=True, audit=arm in ('sym_shared', 'sym_analytic_shared'))
        if reference is None:
            reference = {tuple(r['order']): r['frontier'] for r in row['order_frontiers']}
            frontier = row['frontier']
        if row['frontier'] != frontier:
            raise AssertionError(f'root frontier differs: {name}/{arm}')
        for per_order in row['order_frontiers']:
            if per_order['frontier'] != reference[tuple(per_order['order'])]:
                raise AssertionError(f'per-order frontier differs: {name}/{arm}')
        if row['pool'] and row['pool']['hits'] != row['pool']['verified']:
            raise AssertionError('unaudited pool hit')
        rows.append(row)
        gc.collect()
    return dict(arms=rows, equal=True)


def worker(args):
    if args.out.exists():
        raise ValueError('preserve prior output')
    resource.setrlimit(resource.RLIMIT_AS, (3*2**30, 3*2**30))
    def timeout(*_):
        raise TimeoutError('120-second worker limit')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(120)
    result = dict(case=args.case, arm=args.arm, mode=args.mode, revision=args.revision,
                  python=platform.python_version(), hash_seed=os.environ.get('PYTHONHASHSEED'),
                  source_sha256=source_hashes(SOURCES))
    try:
        if args.mode == 'audit':
            result.update(audit_case(args.case))
        else:
            result.update(run_arm(args.case, args.arm, profile=args.mode == 'work'))
        result['status'] = 'complete'
    except Exception as exc:
        result.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.alarm(0)
        args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('case', 'arm', 'mode', 'status')}), flush=True)
    return int(result['status'] != 'complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'worker'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--arm', choices=ARMS, default='sym_shared')
    parser.add_argument('--mode', choices=('audit', 'time', 'work'), default='audit')
    args = parser.parse_args()
    if args.command == 'worker':
        return worker(args)
    verify_sources(args.revision, SOURCES)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/'manifest.json').write_text(json.dumps(dict(revision=args.revision, audit_cases=CASES,
        timed_cases=TIMED_CASES, arms=ARMS, rounds=5, worker_seconds=120, memory_gib=3,
        primary_cases=('two_stage_join', 'asymmetric_join')), indent=2)+'\n')
    def launch(name, arm, mode, tag):
        return subprocess.run([sys.executable, '-m', 'research.dag_mapping.bench_reuse', 'worker',
            '--out', str(args.out/f'{name}_{arm}_{tag}.json'), '--revision', args.revision,
            '--case', name, '--arm', arm, '--mode', mode],
            env=dict(os.environ, PYTHONHASHSEED='0')).returncode
    # Correctness is a gate; a failed audit prevents all performance claims.
    for name in CASES:
        if launch(name, 'sym_shared', 'audit', 'audit'):
            return 1
    failed = False
    for turn in range(5):
        arms = ARMS[turn % len(ARMS):] + ARMS[:turn % len(ARMS)]
        for name in TIMED_CASES:
            for arm in arms:
                failed |= bool(launch(name, arm, 'time', str(turn)))
    for name in TIMED_CASES:
        for arm in ARMS:
            failed |= bool(launch(name, arm, 'work', 'work'))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
