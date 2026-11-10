"""Attribute the exact solver's work to response strata. No solver source is edited.

Like audit_residency_states.instrumented_curve, the in-memory AST adds
observers; here they also read the live stats counters, so every completed
solve/group cache miss gets its EXCLUSIVE work (its own counters and time,
minus those of child misses completed during it). A third observer wraps the
uncached group_curve entry, so every group query, hit or miss, is counted by
whether it returned an empty frontier (the queries Lemma 2 of
REMAINDER_LEMMAS.md lets a caller skip).

Strata of a cache miss (exactly one each):
- empty: no frontier point;
- zero_at_d: the single point (d, 0), where d = max over ops of nonexternal
  cells: both the operand-slot capacity bound and zero extra traffic hold;
- zero_above_d: a single point (c, 0) with c > d: zero extra traffic only;
- rest: everything else.
A miss is also flagged `repeat` when a previous miss had the same
remainder-graph label (sufficient_stat.statistic, variant residual_domain).
That counts work an isomorphism-keyed cache could reuse; WL labels are only
a proxy for isomorphism here, not an implementable key.

Usage: python -m research.index_coupling.attribute_work --case NAME --out DIR
"""
import argparse
import ast
from collections import defaultdict
import json
from math import prod
from pathlib import Path
import platform
import resource
import signal
import subprocess
import time

from research.index_coupling.analyze_redundancy import graph_of
from research.index_coupling.audit_residency_states import CASES as FORKS
from research.index_coupling.redundancy_census import CASES
from research.index_coupling.sufficient_stat import statistic

HERE = Path(__file__).resolve().parent
COUNTERS = ('dp_transitions', 'loop_choices', 'partition_choices', 'pareto_candidates', 'merge_inputs')


def instrumented(observe_miss, observe_group_call):
    path = HERE / 'graph/curve.py'
    tree = ast.parse(path.read_text(), filename=str(path))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ('_solve', '_group_curve'):
            if not (len(node.decorator_list) == 1 and isinstance(node.decorator_list[0], ast.Call)
                    and getattr(node.decorator_list[0].func, 'id', None) == 'lru_cache'):
                raise ValueError('observer must sit inside the LRU cache')
            stage = 'solve' if node.name == '_solve' else 'group'
            node.decorator_list.append(ast.Call(func=ast.Name(id='_observe_miss', ctx=ast.Load()),
                                               args=[ast.Constant(stage)], keywords=[]))
            found.add(node.name)
        elif isinstance(node, ast.FunctionDef) and node.name == 'group_curve':
            node.decorator_list.append(ast.Name(id='_observe_group_call', ctx=ast.Load()))
            found.add(node.name)
    if found != {'_solve', '_group_curve', 'group_curve'}:
        raise ValueError(f'unexpected solver layout: {sorted(found)}')
    namespace = dict(__name__='research.index_coupling.graph._work_audit',
                     __package__='research.index_coupling.graph',
                     _observe_miss=observe_miss, _observe_group_call=observe_group_call)
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), namespace)
    return namespace['curve']


def stratum(graph, state, points):
    if not points:
        return 'empty'
    if len(points) > 1 or points[0][1] != 0:
        return 'rest'
    ext = dict(zip(sorted(graph.sizes), state['ext']))
    resident = set(state['external'])
    d = max(sum(prod(ext[v] for v in dims) for t, dims in graph.access[op].items() if t not in resident)
            for op in state['ops'])
    return 'zero_at_d' if points[0][0] == d else 'zero_above_d'


def timeout(*_):
    raise TimeoutError('work attribution wall-time limit')


def run(case, seconds, mem_gib):
    graph = graph_of(case)
    if platform.system() == 'Linux':
        cap = int(mem_gib * 2**30)
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    stats = {}
    facts = (graph.produced(), graph.consumed(), {t: len(graph.consumers(t)) for t in graph.tensors(graph.ops)})
    totals = defaultdict(lambda: defaultdict(float))
    seen_labels = set()
    stack = []
    group_calls = dict(calls=0, empty=0)

    def snapshot():
        return [stats.get(k, 0) for k in COUNTERS] + [time.perf_counter()]

    def observe_miss(stage):
        def decorate(fn):
            def recorded(ops, ext, external, owned, *extra):
                stack.append([0.] * (len(COUNTERS) + 1))
                before = snapshot()
                points = fn(ops, ext, external, owned, *extra)
                after = snapshot()
                children = stack.pop()
                inclusive = [b - a for a, b in zip(before, after)]
                exclusive = [i - c for i, c in zip(inclusive, children)]
                if stack:
                    stack[-1] = [s + i for s, i in zip(stack[-1], inclusive)]
                state = dict(stage=stage, ops=list(ops), ext=list(ext), external=sorted(external),
                             owned=sorted(owned), constrained=bool(extra and extra[0]))
                kind = stratum(graph, state, [p[:2] for p in points])
                label = statistic(graph, state, 'residual_domain', facts)
                repeat = label in seen_labels
                seen_labels.add(label)
                for key in (kind, 'all') + (('repeat',) if repeat else ()):
                    row = totals[key]
                    row['misses'] += 1
                    for name, value in zip(COUNTERS + ('seconds',), exclusive):
                        row[name] += value
                return points
            return recorded
        return decorate

    def observe_group_call(fn):
        def counted(*args):
            points = fn(*args)
            group_calls['calls'] += 1
            group_calls['empty'] += not points
            return points
        return counted

    record = dict(case=case, revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE,
                                                              text=True).strip(),
                  python=platform.python_version(), budgets=dict(seconds=seconds, mem_gib=mem_gib),
                  options=dict(partitions='dp', canonical_spans=False, independent_ops=False,
                               tile_domain='halving'))
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    start = time.monotonic()
    try:
        compute = instrumented(observe_miss, observe_group_call)
        points = compute(graph, stats=stats, **record['options'])
        record.update(status='complete', points=[list(p[:2]) for p in points])
    except TimeoutError:
        record.update(status='timeout')
    except MemoryError:
        record.update(status='memory')
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    record.update(seconds=time.monotonic() - start, group_calls=group_calls,
                  strata={k: dict(v) for k, v in totals.items()},
                  run_totals={k: stats.get(k) for k in COUNTERS})
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=list(CASES) + list(FORKS), required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=120)
    p.add_argument('--mem-gib', type=float, default=4)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    record = run(a.case, a.seconds, a.mem_gib)
    (a.out / f'{a.case}.work.json').write_text(json.dumps(record, indent=1) + '\n')
    s = record['strata']
    print(json.dumps(dict(case=a.case, status=record['status'], group_calls=record['group_calls'],
                          transitions={k: round(v.get('dp_transitions', 0) + v.get('loop_choices', 0))
                                       for k, v in s.items()})))


if __name__ == '__main__':
    main()
