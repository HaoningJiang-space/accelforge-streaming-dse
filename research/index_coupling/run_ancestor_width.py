"""Single-op control: local obligation width one, accumulated residency k.

Predicted BEFORE running: solve entries = 3**k; group entries = 3**k - 2**k.
Each rank has three reachable states: unsliced, sliced/dropped, sliced/kept.
All 2**k fully sliced states stop at solve's scalar base case.
This counts this implementation's keys, not an intrinsic algorithm lower bound.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import signal
import subprocess
import time

from .graph.curve import curve
from .graph.model import Graph
from .graph.widths import widths
from .simulate_nest import simulate


def control(k):
    ranks = tuple(f'v{i}' for i in range(k))
    access = {f'T{i}': tuple(v for v in ranks if v != ranks[i]) for i in range(k)}
    access['Y'] = ranks
    return Graph(dict.fromkeys(ranks, 2), [('E', access)])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--k', type=int, required=True, choices=range(1, 9))
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if platform.system() != 'Linux':
        p.error('bounded measurements require Linux')
    if args.out.exists():
        p.error('preserve the existing attempt')
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    here = Path(__file__).parent
    source = {n: hashlib.sha256((here / n).read_bytes()).hexdigest() for n in (
        'run_ancestor_width.py', 'graph/curve.py', 'graph/model.py',
        'graph/widths.py', 'graph/span_names.py', 'simulate_nest.py')}
    graph, stats = control(args.k), {}
    record = dict(k=args.k, widths=widths(graph), source_sha256=source,
        revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        python=platform.python_version(), hash_seed=os.environ.get('PYTHONHASHSEED'),
        budgets=dict(seconds=60, mem_gib=1),
        options=dict(partitions='dp', witness=True, canonical_spans=False, independent_ops=False),
        predicted=dict(solve=3**args.k, group=3**args.k - 2**args.k), stats=stats)

    def timeout(*_):
        raise TimeoutError('search plus replay budget')

    start = time.monotonic()
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(60)
    try:
        points = curve(graph, stats=stats, **record['options'])
        record.update(search_seconds=time.monotonic() - start, witnesses=points,
                      points=[list(p[:2]) for p in points], replays=[])
        for c, q, witness in points:
            actual = simulate(graph, witness)
            record['replays'].append(dict(capacity=c, traffic=q, actual=actual,
                exact=actual['valid'] and (actual['peak'], actual['traffic']) == (c, q)))
        observed = {stage: stats[f'{stage}_cache']['currsize'] for stage in ('solve', 'group')}
        record.update(observed=observed, count_prediction_matches=observed == record['predicted'],
            max_external=max(int(re.search(r'external=(\d+)', key)[1])
                             for key in stats['cache_misses_by_residency']),
            status='complete' if all(r['exact'] for r in record['replays']) else 'invalid')
    except Exception as exc:
        record.update(status='timeout' if isinstance(exc, TimeoutError) else 'error',
                      error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.alarm(0)
    record.update(seconds=time.monotonic() - start,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({key: record.get(key) for key in
        ('k', 'status', 'predicted', 'observed', 'count_prediction_matches', 'max_external', 'seconds')}))
    return int(record['status'] != 'complete' or not record.get('count_prediction_matches'))


if __name__ == '__main__':
    raise SystemExit(main())
