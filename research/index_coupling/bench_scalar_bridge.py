"""Bounded fresh-process tiny-fork comparisons; no production defaults change."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import fork
from research.index_coupling.scalar_bridge import make_scalar_bridge_curve
from research.index_coupling.simulate_nest import simulate

HERE = Path(__file__).parent
CASES = {'same6': 'kkkkkk', 'mixed6': 'kkkiii'}


def hashes():
    names = ('scalar_bridge.py', 'bench_scalar_bridge.py', 'audit_scalar_bridge.py', 'test_scalar_bridge.py',
             'graph/curve.py', 'graph/model.py', 'graph/span_names.py', 'simulate_nest.py')
    return {n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in names}


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if platform.system() == 'Darwin' else 1024 * value


def worker(args):
    if args.out.exists():
        raise FileExistsError(args.out)
    graph = fork(2, 2, 2, 2, CASES[args.case])
    compute = make_scalar_bridge_curve() if args.variant == 'bridge' else curve
    stats = {} if args.profile else None
    record = dict(case=args.case, variant=args.variant, profiling=args.profile,
                  source_sha256=hashes(), revision=subprocess.check_output(
                      ['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
                  python=platform.python_version(), hash_seed=os.environ.get('PYTHONHASHSEED'),
                  started_utc=datetime.now(timezone.utc).isoformat(), status='running', phase='search',
                  budgets=dict(seconds=args.seconds, mem_gib=args.mem_gib),
                  memory_enforcement='RLIMIT_AS + sampled_peak_RSS' if platform.system() == 'Linux' else 'sampled_peak_RSS',
                  cpu_affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
                  options=dict(partitions='dp', witness=True, canonical_spans=False, independent_ops=False))
    save(args.out, record)
    cap = int(args.mem_gib * 2**30)
    if platform.system() == 'Linux':
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    start = time.monotonic()

    def watch(*_):
        if time.monotonic() - start >= args.seconds:
            raise TimeoutError('bounded scalar-bridge benchmark')
        if rss_bytes() > cap:
            raise MemoryError('benchmark peak-RSS cap')
    signal.signal(signal.SIGALRM, watch)
    signal.setitimer(signal.ITIMER_REAL, .25, .25)
    try:
        points = compute(graph, stats=stats, **record['options'])
        record.update(search_seconds=time.monotonic() - start, phase='replay',
                      points=[list(p[:2]) for p in points], witnesses=points, replays=[])
        save(args.out, record)
        for c, q, witness in points:
            actual = simulate(graph, witness)
            record['replays'].append(dict(capacity=c, traffic=q,
                exact=actual['valid'] and (actual['peak'], actual['traffic']) == (c, q), actual=actual))
        record.update(status='complete' if all(r['exact'] for r in record['replays']) else 'invalid', phase='done')
    except Exception as exc:
        record.update(status='timeout' if isinstance(exc, TimeoutError) else 'memory' if isinstance(exc, MemoryError)
                      else 'error', error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    record.update(seconds=time.monotonic() - start, peak_rss_bytes=rss_bytes(), stats=stats)
    save(args.out, record)
    return int(record['status'] != 'complete')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=40)
    p.add_argument('--mem-gib', type=float, default=1)
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--worker', action='store_true')
    p.add_argument('--case', choices=CASES)
    p.add_argument('--variant', choices=('baseline', 'bridge'))
    p.add_argument('--profile', action='store_true')
    args = p.parse_args()
    if args.seconds <= 0 or args.mem_gib <= 0 or args.repeats < 1:
        p.error('positive budgets and repeats required')
    if args.worker:
        if args.case is None or args.variant is None:
            p.error('worker needs case and variant')
        return worker(args)
    args.out.mkdir(parents=True, exist_ok=False)
    order = []
    for case in CASES:
        for i in range(args.repeats):
            for variant in (('baseline', 'bridge') if i % 2 == 0 else ('bridge', 'baseline')):
                order.append((case, variant, False, i))
        for variant in ('baseline', 'bridge'):
            order.append((case, variant, True, 0))
    initial_hashes = hashes()
    save(args.out / 'manifest.json', dict(source_sha256=initial_hashes, order=order, seconds=args.seconds,
                                        mem_gib=args.mem_gib, repeats=args.repeats, concurrent_jobs=1))
    records = []
    for case, variant, profile, repetition in order:
        output = args.out / f'{case}_{variant}_{"profile" if profile else repetition}.json'
        command = [sys.executable, '-m', 'research.index_coupling.bench_scalar_bridge', '--worker',
                   '--case', case, '--variant', variant, '--out', str(output),
                   '--seconds', str(args.seconds), '--mem-gib', str(args.mem_gib)]
        if profile:
            command.append('--profile')
        try:
            result = subprocess.run(command, env=dict(os.environ, PYTHONHASHSEED='0'),
                                    timeout=args.seconds + 5, capture_output=True, text=True)
            failure = dict(status='crashed', exitcode=result.returncode, stderr=result.stderr[-2000:])
        except subprocess.TimeoutExpired:
            failure = dict(status='hard_timeout')
        r = json.loads(output.read_text()) if output.exists() else dict(case=case, variant=variant)
        if r.get('status') in (None, 'running'):
            r.update(failure)
            save(output, r)
        if r.get('status') == 'complete' and r.get('source_sha256') != initial_hashes:
            r.update(status='source_mismatch')
            save(output, r)
        records.append(r)
        print(json.dumps({k: r.get(k) for k in ('case', 'variant', 'profiling', 'status', 'search_seconds')}), flush=True)
    summary = {}
    for case in CASES:
        rows = [r for r in records if r['case'] == case]
        complete = [r for r in rows if r['status'] == 'complete']
        summary[case] = dict(complete=len(complete), requested=len(rows),
                            equal=bool(complete) and all(r['points'] == complete[0]['points'] for r in complete),
                            root_replays=sum(len(r['replays']) for r in complete))
    save(args.out / 'summary.json', summary)
    return int(any(s['complete'] != s['requested'] or not s['equal'] for s in summary.values()))


if __name__ == '__main__':
    raise SystemExit(main())
