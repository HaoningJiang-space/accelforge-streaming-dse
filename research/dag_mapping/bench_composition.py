"""Frozen factorial audit of existing reductions with prefix composition."""
import argparse
import gc
import hashlib
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
from research.index_coupling.graph.stacks import ffn_stack, attention_stack
from research.index_coupling.response.prefix import make_kernel
from research.index_coupling.run_ancestor_width import control
from research.index_coupling.simulate_nest import simulate
from .bench_reuse import graph_for as dag_graph, select_orders, SOURCES as REUSE_SOURCES
from .boundary import resized
from .hierarchy import analyze, decode
from .reuse import RegionSession

CASES = ('two_stage_join', 'asymmetric_join', 'mixed_join', 'ffn4', 'attention4', 'ancestor8')
ARMS = ('native', 'native_p', 'analytic', 'prefix', 'prefix_p', 'prefix_i', 'prefix_r',
        'prefix_pi', 'prefix_pr', 'prefix_ir', 'prefix_pir')
FLAGS = dict(p='prune_infeasible_groups', i='independent_ops', r='canonical_remainders')
SOURCES = tuple(sorted(set(REUSE_SOURCES) | {
    'research/dag_mapping/bench_composition.py',
    'research/index_coupling/test_prefix_reductions.py',
    'research/index_coupling/graph/remainder.py', 'research/index_coupling/graph/span_names.py',
    'research/index_coupling/graph/stacks.py', 'research/index_coupling/run_ancestor_width.py'}))


def graph_for(name):
    if name == 'ffn4':
        return ffn_stack(4)
    if name == 'attention4':
        return attention_stack(4)
    if name == 'ancestor8':
        return control(8)
    return dag_graph(name)


def run_arm(name, arm, profile=False, analytic_flags=None):
    start = perf_counter()
    graph = graph_for(name)
    orders, all_orders, automorphisms = select_orders(graph, arm != 'reference')
    options = dict(partitions='dp', scalar_leaf='v2', witness=True)
    session = None
    if arm in ('reference', 'native', 'native_p'):
        kernel = curve
        if arm == 'native_p':
            options['prune_infeasible_groups'] = True
    elif arm == 'analytic':
        session = RegionSession(graph, unit=True, certificate=True, reductions=analytic_flags is not None)
    else:
        suffix = arm.partition('_')[2]
        kernel, _ = make_kernel(frames=True, composition='numeric', reductions=bool(suffix))
        options.update({FLAGS[k]: True for k in suffix})
    setup = perf_counter() - start
    start = perf_counter()
    aggregate, per_order, work = [], [], []
    for order in orders:
        ledger = {} if profile else None
        points = (session.query(order, stats=ledger, **(analytic_flags or {})) if session else
                  kernel(resized(graph, graph.sizes, order), stats=ledger, **options))
        aggregate.extend((c, q, (order, notes)) for c, q, notes in points)
        per_order.append(dict(order=order, frontier=[list(p[:2]) for p in points]))
        if ledger is not None:
            work.append(ledger)
    selected = pareto(aggregate)
    recovery_start = perf_counter()
    witnesses = [dict(order=order, notes=session.recover(notes) if session else notes)
                 for _, _, (order, notes) in selected]
    recovery = perf_counter() - recovery_start
    generation = perf_counter() - start
    memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    start = perf_counter()
    replays = []
    for (c, q, _), witness in zip(selected, witnesses):
        ordered = resized(graph, graph.sizes, witness['order'])
        check = analyze(ordered, decode(ordered, witness['notes']))
        actual = simulate(ordered, witness['notes'], scalar_leaf='v2')
        if (not actual['valid'] or (actual['peak'], actual['traffic']) != (c, q)
                or (check['peak'], check['traffic']) != (c, q)):
            raise AssertionError('complete root witness mismatch')
        replays.append(dict(point=[c, q], actual=actual))
    fields = ('dp_transitions', 'loop_choices', 'pareto_candidates', 'independent_splits',
              'renamed_calls', 'rename_nodes', 'group_prechecks', 'empty_group_skips',
              'prefix_infeasible_skips', 'retention_batches_skipped', 'exact_checks',
              'exact_hits', 'separator_checks', 'separator_hits')
    summary = {key: sum(row.get(key, 0) for row in work) for key in fields} if profile else None
    if profile:
        summary.update(response_bodies=sum(row['solve_cache']['misses']+row['group_cache']['misses']
                                           for row in work),
                       prefix_entries=sum(row.get('prefix_cache', {}).get('currsize', 0) for row in work),
                       remainder_seconds=sum(row.get('remainder', {}).get('seconds', 0) for row in work))
    return dict(all_orders=all_orders, searched_orders=len(orders), automorphisms=automorphisms,
                setup_seconds=setup, generation_seconds=generation, inclusive_seconds=setup+generation,
                recovery_seconds=recovery, replay_seconds=perf_counter()-start,
                pre_replay_peak_rss_kib=memory, frontier=[list(p[:2]) for p in selected],
                order_frontiers=per_order, witnesses=witnesses, replays=replays,
                selected_exact_placeholders=sum(n[0] == 'exact' for _, _, (_, ns) in selected for n in ns),
                selected_transported_placeholders=sum(n[0] == 'exact' and len(n) == 5
                                                      for _, _, (_, ns) in selected for n in ns),
                recovery_contexts=len(session.recovery_cache) if session else 0,
                work=summary, ledgers=work if profile else None)


def worker(args, runner=None, sources=None):
    if args.out.exists():
        raise ValueError('preserve prior record')
    resource.setrlimit(resource.RLIMIT_AS, (4*2**30, 4*2**30))
    def timeout(*_):
        raise TimeoutError('180-second worker budget')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(180)
    runner = run_arm if runner is None else runner
    sources = SOURCES if sources is None else sources
    result = dict(case=args.case, arm=args.arm, mode=args.mode, revision=args.revision,
                  python=platform.python_version(), hash_seed=os.environ.get('PYTHONHASHSEED'),
                  source_sha256={p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sources})
    try:
        result.update(runner(args.case, args.arm, profile=args.mode == 'work'))
        if args.reference:
            reference = json.loads(args.reference.read_text())
            expected = {tuple(row['order']): row['frontier'] for row in reference['order_frontiers']}
            if result['frontier'] != reference['frontier']:
                raise AssertionError('complete union frontier mismatch')
            for row in result['order_frontiers']:
                if row['frontier'] != expected[tuple(row['order'])]:
                    raise AssertionError('per-order frontier mismatch')
            result['reference_sha256'] = hashlib.sha256(args.reference.read_bytes()).hexdigest()
            result['equal'] = True
        result['status'] = 'complete'
    except Exception as exc:
        result.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.alarm(0)
        args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({key: result[key] for key in ('case', 'arm', 'mode', 'status')}), flush=True)
    return int(result['status'] != 'complete')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('run', 'worker'))
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--case', choices=CASES)
    p.add_argument('--arm', choices=ARMS+('reference',), default='prefix')
    p.add_argument('--mode', choices=('audit', 'time', 'work'), default='audit')
    p.add_argument('--reference', type=Path)
    args = p.parse_args()
    if args.command == 'worker':
        return worker(args)
    if platform.system() != 'Linux':
        raise ValueError('fresh Linux processes required')
    for source in SOURCES:
        if subprocess.check_output(['git', 'show', f'{args.revision}:{source}']) != Path(source).read_bytes():
            raise ValueError(f'unfrozen source: {source}')
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = dict(revision=args.revision, cases=CASES, arms=ARMS, rounds=3,
                    worker_seconds=180, memory_gib=4, hash_seed='0',
                    policy='exact unlimited v2; halving; fixed certified order representatives',
                    primary_comparison='prefix versus each existing-reduction combination; no universal speedup gate')
    (args.out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    def launch(name, arm, mode, tag):
        cmd = [sys.executable, '-m', 'research.dag_mapping.bench_composition', 'worker',
               '--out', str(args.out/f'{name}_{arm}_{tag}.json'), '--revision', args.revision,
               '--case', name, '--arm', arm, '--mode', mode]
        if arm != 'reference':
            cmd += ['--reference', str(args.out/f'{name}_reference_audit.json')]
        return subprocess.run(cmd, env=dict(os.environ, PYTHONHASHSEED='0')).returncode
    # Every fixed-order full frontier and union must agree before timing.
    for name in CASES:
        if launch(name, 'reference', 'audit', 'audit'):
            return 1
        for arm in ARMS:
            if launch(name, arm, 'audit', 'audit'):
                return 1
    failed = False
    for turn in range(3):
        arms = ARMS[turn:] + ARMS[:turn]
        for name in CASES:
            for arm in arms:
                failed |= bool(launch(name, arm, 'time', str(turn)))
    for name in CASES:
        for arm in ARMS:
            failed |= bool(launch(name, arm, 'work', 'work'))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
