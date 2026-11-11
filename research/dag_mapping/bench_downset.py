"""Frozen Gate 3 benchmark (DOWNSET_PROTOCOL.md): downset recursion vs native and sym_prefix.

  check CASE...                 exactness: union-of-orders frontier, normalized witness replay
  once ARM CASE                 one fresh-process timing (ARM: native, sym_prefix, downset)
  run OUT_DIR                   five rounds, alternating arm order, all timed cases
"""
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
from time import perf_counter

from research.index_coupling.census_tools import graph_of
from research.index_coupling.graph.branch_symmetry import topological_orders
from research.index_coupling.graph.curve import curve, pareto
from research.index_coupling.simulate_nest import simulate
from .bench_reuse import run_arm
from .workloads import dag_graph as graph_for
from .boundary import resized
from .downset import make_downset_kernel, normalize

DAG_CASES = ('chain_tiny', 'residual_tiny', 'residual_rectangle', 'fork_join_tiny', 'fork_join_rectangle',
             'gated_fork_join_tiny', 'two_stage_join', 'asymmetric_join', 'mixed_join')
PRIMARY = ('asymmetric_join', 'mixed_join')
CHAINS = ('ffn_forward_l1_m8', 'ffn_forward_l2_m8')
OPTIONS = dict(scalar_leaf='v2', partitions='dp')


def graph(case):
    return graph_of(case) if case in CHAINS else graph_for(case)


def downset_generation(g, stats=None):
    kernel = make_downset_kernel()
    started = perf_counter()
    points = kernel(g, witness=True, stats=stats, **OPTIONS)
    witnesses = [normalize(g, w) for _, _, w in points]
    return points, witnesses, perf_counter() - started


def check(cases):
    for case in cases:
        g = graph(case)
        orders = (g.ops,) if case in CHAINS else tuple(topological_orders(g))
        native = pareto([p[:2] + (o,) for o in orders for p in curve(resized(g, g.sizes, o), **OPTIONS)])
        points, witnesses, _ = downset_generation(g)
        same = [p[:2] for p in native] == [p[:2] for p in points]
        replay = sum(1 for (c, q, _), (order, notes) in zip(points, witnesses)
                     if (lambda r: r['valid'] and (r['peak'], r['traffic']) == (c, q))(
                         simulate(resized(g, g.sizes, order), notes, scalar_leaf='v2')))
        print(json.dumps(dict(case=case, orders=len(orders), points=len(points), same_frontier=same,
                              replay_exact=replay)), flush=True)


def once(arm, case):
    g = graph(case)
    if arm == 'downset':
        points, _, seconds = downset_generation(g)
        frontier = [list(p[:2]) for p in points]
    elif case in CHAINS:
        started = perf_counter()
        points = curve(g, witness=True, **OPTIONS)
        seconds, frontier = perf_counter() - started, [list(p[:2]) for p in points]
    else:
        record = run_arm(case, 'native' if arm == 'native' else 'sym_prefix')
        seconds, frontier = record['generation_seconds'], record['frontier']
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    stats = {}
    if arm == 'downset':
        downset_generation(g, stats)
        work = {k: stats.get(k) for k in ('dp_transitions', 'loop_choices', 'pareto_candidates')}
        work.update(solve_misses=stats['solve_cache']['misses'], group_misses=stats['group_cache']['misses'])
    else:
        work = None
    print(json.dumps(dict(case=case, arm=arm, generation_seconds=seconds, frontier=frontier,
                          peak_rss_mib=rss / 2**20 if platform.system() == 'Darwin' else rss / 2**10,
                          work=work)))


def run(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONHASHSEED='0')
    plan = [(case, ('native', 'sym_prefix', 'downset')) for case in PRIMARY + ('two_stage_join',)] + \
           [(case, ('native', 'downset')) for case in CHAINS]
    with (out / 'timing.jsonl').open('x') as stream:
        for r in range(5):
            for case, arms in plan:
                for arm in (arms if r % 2 == 0 else tuple(reversed(arms))):
                    line = subprocess.run([sys.executable, '-m', 'research.dag_mapping.bench_downset', 'once', arm, case],
                                          env=env, capture_output=True, text=True, timeout=600)
                    record = json.loads(line.stdout.strip().splitlines()[-1]) if line.returncode == 0 else \
                        dict(case=case, arm=arm, error=line.stderr[-2000:])
                    record['round'] = r
                    stream.write(json.dumps(record) + '\n')
                    stream.flush()
                    print(json.dumps({k: record.get(k) for k in ('case', 'arm', 'round', 'generation_seconds')}),
                          flush=True)


if __name__ == '__main__':
    command, args = sys.argv[1], sys.argv[2:]
    {'check': lambda: check(args or DAG_CASES + CHAINS), 'once': lambda: once(*args),
     'run': lambda: run(args[0])}[command]()
