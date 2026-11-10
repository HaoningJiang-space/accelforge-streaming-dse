"""Joint-state census of existing small forks; no solver source files are edited.

The in-memory AST adds a recording decorator INSIDE each existing LRU cache.
Every completed cache miss emits its full projected key and numeric frontier.
This is diagnostic instrumentation, not a state-merging optimization.
"""
import argparse
import ast
from datetime import datetime, timezone
from functools import wraps
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import time

from research.index_coupling.graph.model import fork
from research.index_coupling.simulate_nest import simulate

HERE = Path(__file__).resolve().parent
CASES = {'kkk': (2, 2, 2, 2, 'kkk'),
         'same6': (2, 2, 2, 2, 'kkkkkk'),
         'mixed6': (2, 2, 2, 2, 'kkkiii')}


def instrumented_curve(on_complete):
    """Keep transitions/cache keys intact; observe completed misses only."""
    path = HERE / 'graph/curve.py'
    tree = ast.parse(path.read_text(), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ('_solve', '_group_curve'):
            if len(node.decorator_list) != 1 or not isinstance(node.decorator_list[0], ast.Call):
                raise ValueError('unexpected solver decorator layout')
            decorator = node.decorator_list[0]
            if not isinstance(decorator.func, ast.Name) or decorator.func.id != 'lru_cache':
                raise ValueError('observer must be inside the LRU cache')
            stage = 'solve' if node.name == '_solve' else 'group'
            node.decorator_list.append(ast.Call(func=ast.Name(id='_audit_observe', ctx=ast.Load()),
                                               args=[ast.Constant(stage)], keywords=[]))
            found.append(stage)
    if sorted(found) != ['group', 'solve']:
        raise ValueError('expected exactly one solve and one group cache')

    def observe(stage):
        def decorate(fn):
            @wraps(fn)
            def recorded(ops, ext, external, owned, *extra):
                points = fn(ops, ext, external, owned, *extra)
                on_complete(dict(stage=stage, ops=ops, ext=ext,
                                 external=tuple(sorted(external)), owned=tuple(sorted(owned)),
                                 constrained=bool(extra and extra[0]),
                                 points=tuple(p[:2] for p in points)))
                return points
            return recorded
        return decorate

    namespace = dict(__name__='research.index_coupling.graph._residency_audit',
                     __package__='research.index_coupling.graph', _audit_observe=observe)
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), namespace)
    return namespace['curve']


def source_hashes():
    names = ('audit_residency_states.py', 'summarize_residency_states.py', 'test_residency_states.py',
             'graph/curve.py', 'graph/model.py', 'graph/span_names.py', 'simulate_nest.py')
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in names}


def save(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def timeout(*_):
    raise TimeoutError('joint-state audit wall-time limit')


def run(case, directory, seconds=20, mem_gib=1):
    directory.mkdir(parents=True, exist_ok=False)
    graph = fork(*CASES[case])
    record = dict(case=case, graph_args=CASES[case], rank_order=sorted(graph.sizes),
                  revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
                  source_sha256=source_hashes(), python=platform.python_version(),
                  hash_seed=os.environ.get('PYTHONHASHSEED'),
                  started_utc=datetime.now(timezone.utc).isoformat(),
                  state_point_semantics='internal extra traffic; caller reservations and whole-graph compulsory traffic excluded',
                  options=dict(partitions='dp', ownership_projection=True, canonical_spans=False,
                               independent_ops=False, tile_domain='halving', witness=True),
                  budgets=dict(seconds=seconds, mem_gib=mem_gib),
                  memory_enforcement='RLIMIT_AS' if platform.system() == 'Linux' else 'sampled_peak_RSS',
                  status='running', stage='search', completed_states=0)
    cap = int(mem_gib * 2**30)
    if platform.system() == 'Linux':
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    signal.signal(signal.SIGALRM, timeout)
    stats, count = {}, 0
    start = time.monotonic()
    save(directory / 'run.json', record)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        with gzip.open(directory / 'states.jsonl.gz', 'wt') as stream:
            def append(state):
                nonlocal count
                stream.write(json.dumps(state, separators=(',', ':')) + '\n')
                count += 1
                if count % 512 == 0:
                    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    if (rss if platform.system() == 'Darwin' else rss * 1024) > cap:
                        raise MemoryError('joint-state audit RSS limit')
            compute = instrumented_curve(append)
            points = compute(graph, stats=stats, **record['options'])
        record.update(stage='replay', search_seconds=time.monotonic() - start,
                      points=[list(p[:2]) for p in points], witnesses=points, replays=[])
        save(directory / 'run.json', record)
        for c, q, witness in points:
            actual = simulate(graph, witness)
            record['replays'].append(dict(capacity=c, traffic=q,
                exact=actual['valid'] and (actual['peak'], actual['traffic']) == (c, q), actual=actual))
        expected = stats['solve_cache']['currsize'] + stats['group_cache']['currsize']
        record.update(status='complete' if count == expected and all(r['exact'] for r in record['replays']) else 'invalid',
                      stage='done', cache_entries=expected, cache_count_matches=count == expected)
    except Exception as exc:
        record.update(status='timeout' if isinstance(exc, TimeoutError) else
                      'memory' if isinstance(exc, MemoryError) else 'error',
                      error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    record.update(completed_states=count, stats=stats, seconds=time.monotonic() - start,
                  peak_rss_bytes=rss if platform.system() == 'Darwin' else rss * 1024)
    save(directory / 'run.json', record)
    print(json.dumps({k: record[k] for k in ('case', 'status', 'completed_states', 'seconds', 'peak_rss_bytes')}))
    return int(record['status'] != 'complete')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=CASES, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=20)
    p.add_argument('--mem-gib', type=float, default=1)
    args = p.parse_args()
    if args.seconds <= 0 or args.mem_gib <= 0:
        p.error('budgets must be positive')
    return run(args.case, args.out, args.seconds, args.mem_gib)


if __name__ == '__main__':
    raise SystemExit(main())
