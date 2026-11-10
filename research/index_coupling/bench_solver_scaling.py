"""Fresh-process comparisons; identical witnesses, budgets and profiling per arm.

python -m research.index_coupling.bench_solver_scaling --out DIR --revision REV
All jobs checkpoint separately. Re-running the exact same invocation skips
completed jobs; mismatched source/configuration refuses to reuse the directory.
No global theorem or exhaustive audit is inferred from frontier equality.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import fork, residual
from research.index_coupling.simulate_nest import simulate


CASES = {
    'fork_small': ('fork', (2, 2, 2, 2, 'kki')),
    'residual_small': ('residual', (2, 2, 2, 3, True)),
    'residual_medium': ('residual', (8, 2, 4, 6, True)),
    'fork_medium_same': ('fork', (4, 2, 4, 2, 'kkkkkk')),
    'fork_medium_mixed': ('fork', (4, 2, 4, 2, 'kkkiii')),
    'p19_same': ('fork', (8, 4, 8, 2, 'kkkkkk')),
    'p19_mixed': ('fork', (8, 4, 8, 2, 'kkkiii')),
    'residual_deep': ('residual', (8, 2, 4, 12, True)),
}
VARIANTS = {f'{mode}_{projection}': (mode, projection == 'projected')
            for mode in ('enumerate', 'dp') for projection in ('baseline', 'projected')}


def atomic_json(path, obj):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, indent=2) + '\n')
    tmp.replace(path)


def source_hash():
    root = Path(__file__).parent
    names = ('graph/curve.py', 'graph/model.py', 'graph/span_names.py', 'simulate_nest.py', 'bench_solver_scaling.py')
    h = hashlib.sha256()
    for name in names:
        h.update(name.encode())
        h.update((root / name).read_bytes())
    return h.hexdigest()


class Timeout(Exception):
    pass


def timeout(_signum, _frame):
    raise Timeout()


def worker(args):
    kind, shape = CASES[args.case]
    graph = (fork if kind == 'fork' else residual)(*shape)
    mode, projected = VARIANTS[args.variant]
    stats = None if args.no_profile else {}
    out = dict(case=args.case, kind=kind, args=shape, n_ops=len(graph.ops),
               variant=args.variant, witness=not args.no_witness, profiling=not args.no_profile,
               canonical_spans=args.canonical_spans,
               source_sha256=source_hash(), revision=args.revision, python=platform.python_version(),
               started_utc=datetime.now(timezone.utc).isoformat(),
               budgets=dict(seconds=args.seconds, mem_gib=args.mem_gib), stats=stats,
               phase='search', status='running')
    cap = int(args.mem_gib * 2**30)
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    signal.signal(signal.SIGALRM, timeout)
    begin = time.perf_counter()
    atomic_json(args.out, out)
    signal.setitimer(signal.ITIMER_REAL, args.seconds)
    try:
        points = curve(graph, witness=not args.no_witness, partitions=mode,
                       ownership_projection=projected, stats=stats, canonical_spans=args.canonical_spans)
        out.update(search_seconds=time.perf_counter() - begin, points=[list(p[:2]) for p in points],
                   phase='replay', replay_checked=0, replay_failures=[])
        atomic_json(args.out, out)
        replay_start = time.perf_counter()
        if not args.no_witness:
            for c, q, w in points:
                a = simulate(graph, w)
                out['replay_checked'] += 1
                if not a['valid'] or (a['peak'], a['traffic']) != (c, q):
                    out['replay_failures'].append(dict(model=[c, q], actual=[a['peak'], a['traffic']], valid=a['valid']))
        out.update(replay_seconds=time.perf_counter() - replay_start, phase='finished',
                   status='invalid' if out['replay_failures'] else 'complete')
    except Timeout:
        out['status'] = 'timeout'
    except MemoryError:
        out['status'] = 'memory'
    except Exception as exc:
        out.update(status='error', error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out.update(seconds=time.perf_counter() - begin,
               peak_rss_bytes=rss if sys.platform == 'darwin' else rss * 1024)
    atomic_json(args.out, out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--seconds', type=float, default=180)
    parser.add_argument('--mem-gib', type=float, default=6)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--cases', nargs='+', choices=CASES, default=list(CASES))
    parser.add_argument('--variants', nargs='+', choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument('--no-witness', action='store_true')
    parser.add_argument('--no-profile', action='store_true')
    parser.add_argument('--canonical-spans', action='store_true')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--case', choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument('--variant', choices=VARIANTS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if min(args.seconds, args.mem_gib, args.workers) <= 0:
        parser.error('budgets must be positive')
    if args.worker:
        worker(args)
        return
    args.out.mkdir(parents=True, exist_ok=True)
    config = dict(source_sha256=source_hash(), revision=args.revision, seconds=args.seconds,
                  mem_gib=args.mem_gib, workers=args.workers, cases=args.cases, variants=args.variants,
                  witness=not args.no_witness, profiling=not args.no_profile,
                  canonical_spans=args.canonical_spans)
    manifest = args.out / 'manifest.json'
    if manifest.exists() and json.loads(manifest.read_text()) != config:
        parser.error('existing output directory has a different source or configuration')
    atomic_json(manifest, config)

    def run(case, variant):
        path = args.out / f'{case}__{variant}.json'
        if path.exists():
            old = json.loads(path.read_text())
            if old.get('status') == 'complete':
                return old
        command = [sys.executable, '-m', __spec__.name, '--worker', '--case', case, '--variant', variant,
                   '--out', str(path), '--revision', args.revision,
                   '--seconds', str(args.seconds), '--mem-gib', str(args.mem_gib)]
        if args.no_witness:
            command.append('--no-witness')
        if args.no_profile:
            command.append('--no-profile')
        if args.canonical_spans:
            command.append('--canonical-spans')
        try:
            p = subprocess.run(command, capture_output=True, text=True, timeout=args.seconds + 15)
            failure = dict(status='crashed', exitcode=p.returncode, stderr=p.stderr[-2000:])
        except subprocess.TimeoutExpired:
            failure = dict(status='hard_timeout')
        out = json.loads(path.read_text()) if path.exists() else dict(case=case, variant=variant)
        if out.get('status') in (None, 'running'):
            out.update(failure)
            atomic_json(path, out)
        return out

    outputs = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run, case, variant) for case in args.cases for variant in args.variants]
        for future in as_completed(futures):
            out = future.result()
            outputs.append(out)
            print(json.dumps({k: out.get(k) for k in ('case', 'variant', 'status', 'search_seconds', 'peak_rss_bytes')}), flush=True)
    comparisons = {}
    for case in args.cases:
        rows = [o for o in outputs if o['case'] == case and o['status'] == 'complete']
        comparisons[case] = dict(complete=len(rows), requested=len(args.variants),
                                 equal_completed=(all(r['points'] == rows[0]['points'] for r in rows)
                                                  if len(rows) >= 2 else None))
    atomic_json(args.out / 'summary.json', dict(config=config, comparisons=comparisons,
                                               statuses={f"{o['case']}__{o['variant']}": o['status'] for o in outputs}))
    sys.exit(1 if any(o['status'] in ('invalid', 'error') for o in outputs)
             or any(c['equal_completed'] is False for c in comparisons.values())
             else 2 if any(o['status'] != 'complete' for o in outputs) else 0)


if __name__ == '__main__':
    main()
