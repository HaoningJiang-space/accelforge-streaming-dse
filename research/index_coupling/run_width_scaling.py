"""Bounded exact width/stack study; each case runs in a fresh Linux process."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from research.index_coupling.graph.model import fork, residual
from research.index_coupling.graph.stacks import ffn_stack, attention_stack
from research.index_coupling.graph.widths import widths
from research.index_coupling.simulate_nest import simulate


def cases():
    out = []
    for m in range(2, 7):
        for mixed in (False, True):
            roles = 'k' * (m - m // 2) + 'i' * (m // 2) if mixed else 'k' * m
            out.append(dict(name=f'fork_{roles}', family='fork', args=[2, 2, 2, 2, roles]))
    for depth in (4, 6, 8, 12, 16, 24):
        for reads in (False, True):
            out.append(dict(name=f'residual_d{depth}_x{int(reads)}', family='residual',
                            args=[2, 2, 2, depth, reads]))
    for family in ('ffn_forward', 'ffn_training', 'attention_forward'):
        for layers in (1, 2, 4, 8):
            out.append(dict(name=f'{family}_l{layers}', family=family, args=[layers]))
    return out


def build(spec):
    family = spec['family']
    if family in ('fork', 'residual'):
        return {'fork': fork, 'residual': residual}[family](*spec['args'])
    if family == 'attention_forward':
        return attention_stack(*spec['args'])
    return ffn_stack(*spec['args'], training=family == 'ffn_training')


def source_hash():
    root = Path(__file__).parent
    h = hashlib.sha256()
    for name in ('run_width_scaling.py', 'graph/model.py', 'graph/curve.py', 'graph/span_names.py',
                 'graph/stacks.py', 'graph/widths.py', 'simulate_nest.py'):
        h.update(name.encode()); h.update((root / name).read_bytes())
    return h.hexdigest()


def save(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n')
    tmp.replace(path)


def alarm(*_):
    raise TimeoutError('search plus replay budget')


def worker(spec, args):
    if sys.platform != 'linux':
        raise ValueError('bounded experiments require Linux')
    cap = int(args.mem_gib * 2**30)
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    graph = build(spec)
    stats = {}
    record = dict(spec=spec, revision=args.revision, source_sha256=source_hash(),
                  python=platform.python_version(), hash_seed=os.environ.get('PYTHONHASHSEED'),
                  widths=widths(graph), stats=stats, status='running', stage='search',
                  budgets=dict(seconds=args.seconds, mem_gib=args.mem_gib),
                  options=dict(partitions='dp', witness=True, profiling=True,
                               canonical_spans=False, independent_ops=False, tile_domain='halving'))
    save(args.out, record)
    begin = time.monotonic()
    signal.signal(signal.SIGALRM, alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL, args.seconds)
        points = curve(graph, partitions='dp', witness=True, stats=stats)
        record.update(stage='replay', search_seconds=time.monotonic() - begin,
                      points=[list(p[:2]) for p in points], replay_checked=0, replay_failures=[])
        save(args.out, record)
        for c, q, w in points:
            actual = simulate(graph, w)
            record['replay_checked'] += 1
            if not actual['valid'] or (actual['peak'], actual['traffic']) != (c, q):
                record['replay_failures'].append(dict(predicted=[c, q], actual=[actual['peak'], actual['traffic']]))
        record.update(status='invalid' if record['replay_failures'] else 'complete', stage='done')
    except (TimeoutError, MemoryError) as exc:
        record['status'] = 'timeout' if isinstance(exc, TimeoutError) else 'memory'
    except Exception as exc:
        record.update(status='error', error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    record.update(seconds=time.monotonic() - begin,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    save(args.out, record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--mem-gib', type=float, default=6)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--structural-only', action='store_true')
    parser.add_argument('--worker', type=int)
    args = parser.parse_args()
    if min(args.seconds, args.mem_gib, args.workers) <= 0:
        parser.error('positive budgets required')
    specs = cases()
    if args.worker is not None:
        worker(specs[args.worker], args)
        return
    if args.structural_only:
        save(args.out, [dict(spec=s, widths=widths(build(s))) for s in specs])
        return
    args.out.mkdir(parents=True, exist_ok=True)
    config = dict(revision=args.revision, source_sha256=source_hash(), cases=specs,
                  seconds=args.seconds, mem_gib=args.mem_gib, workers=args.workers, hash_seed='0')
    manifest = args.out / 'manifest.json'
    if manifest.exists() and json.loads(manifest.read_text()) != config:
        parser.error('output directory belongs to a different experiment')
    save(manifest, config)

    def run(i):
        path = args.out / f"{specs[i]['name']}.json"
        if path.exists():
            return json.loads(path.read_text())  # preserve every existing attempt
        cmd = [sys.executable, '-m', __spec__.name, '--worker', str(i), '--out', str(path),
               '--revision', args.revision, '--seconds', str(args.seconds), '--mem-gib', str(args.mem_gib)]
        try:
            p = subprocess.run(cmd, env=dict(os.environ, PYTHONHASHSEED='0'), capture_output=True,
                               text=True, timeout=args.seconds + 30)
            failure = dict(status='crashed', exitcode=p.returncode)
        except subprocess.TimeoutExpired:
            failure = dict(status='hard_timeout')
        record = json.loads(path.read_text()) if path.exists() else dict(spec=specs[i])
        if record.get('status') in (None, 'running'):
            record.update(failure); save(path, record)
        return record

    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(run, i) for i in range(len(specs))]):
            record = future.result(); records.append(record)
            print(json.dumps(dict(case=record['spec']['name'], status=record['status'],
                                  seconds=record.get('seconds'))), flush=True)
    save(args.out / 'summary.json', dict(config=config, statuses={r['spec']['name']: r['status'] for r in records}))
    raise SystemExit(1 if any(r['status'] in ('invalid', 'error') for r in records)
                     else 2 if any(r['status'] != 'complete' for r in records) else 0)


if __name__ == '__main__':
    main()
