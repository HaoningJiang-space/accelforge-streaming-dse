"""Bounded, separately versioned order-complete Fork quotient measurements."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time

from .fork_order_oracle import envelope, orders, replay_private_boundary
from .graph.curve import curve
from .graph.fork_quotient import ForkQuotient, Plan, reordered


def specs():
    cases = {}
    for m in (2, 4, 6, 8):
        cases[f'same{m}'] = dict(roles='k' * m, external=[])
        cases[f'mixed{m}'] = dict(roles='k' * (m // 2) + 'i' * (m // 2), external=[])
    cases['same6_pin3'] = dict(roles='kkkkkk', external=['C0', 'C2', 'C4'])
    out = [dict(name=f'quotient_{name}', case=name, mode='quotient', **case) for name, case in cases.items()]
    for name in ('same4', 'mixed4', 'same6', 'mixed6', 'same6_pin3'):
        case = cases[name]
        graph = ForkQuotient((2, 2, 2, 2), case['roles']).graph
        for i, order in enumerate(orders(graph, case['external'])):
            out.append(dict(name=f'oracle_{name}_{i:03}', case=name, mode='oracle', order=order, **case))
    out.extend(dict(name=f'census_{r}', case=r, mode='census', roles=r, external=[]) for r in ('kkk', 'kki'))
    return out


def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2) + '\n'); temp.replace(path)


def hashes():
    root = Path(__file__).parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in (
        'run_fork_quotient.py', 'fork_order_oracle.py', 'graph/fork_quotient.py',
        'graph/curve.py', 'graph/model.py', 'graph/span_names.py', 'simulate_nest.py')}


def worker(spec, args):
    if sys.platform != 'linux':
        raise ValueError('bounded experiments require Linux')
    cap = 6 * 2**30
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    solver = ForkQuotient((2, 2, 2, 2), spec['roles'])
    graph, stats = solver.graph, {}
    record = dict(spec=spec, revision=args.revision, source_sha256=hashes(),
                  python=platform.python_version(), hash_seed=os.environ.get('PYTHONHASHSEED'),
                  budgets=dict(seconds=60, mem_gib=6), status='running', stage='search', stats=stats)
    save(args.out, record)
    def timeout(*_):
        raise TimeoutError('search plus replay limit')
    signal.signal(signal.SIGALRM, timeout); signal.alarm(60)
    start = time.monotonic()
    try:
        if spec['mode'] == 'census':
            queries, keys, mismatches = [], set(), []
            record.update(queries=queries, mismatches=mismatches)
            for profiles in product(range(4), repeat=3):
                external = set()
                for op, profile in zip(graph.ops[1:], profiles):
                    _, inp, out = solver.info[op]
                    if profile & 1: external.add(inp)
                    if profile & 2: external.add(out)
                ext = tuple(graph.sizes[v] for v in solver.ranks)
                keys.add(solver.canonical(graph.ops, ext, external, False)[0])
                points = solver.curve(external=external)
                ledger = {}
                expected = envelope(graph, external=external, quotient=False, ledger=ledger)
                equal = tuple(p[:2] for p in points) == tuple(p[:2] for p in expected)
                checks = [replay_private_boundary(graph, external, c, q, p) for c, q, p in points]
                queries.append(dict(external=sorted(external), points=[list(p[:2]) for p in points],
                    equal=equal, oracle=ledger, replays=checks,
                    witnesses=[asdict(p) for _, _, p in points]))
                if not equal or not all(c['exact'] for c in checks):
                    mismatches.append(len(queries) - 1)
            record.update(root_orbits=len(keys), predicted_orbits=20 if spec['roles']=='kkk' else 40,
                          status='invalid' if mismatches or len(keys) != (20 if spec['roles']=='kkk' else 40) else 'complete')
        else:
            if spec['mode'] == 'quotient':
                points = solver.curve(external=spec['external'])
            else:
                raw = curve(reordered(graph, spec['order']), partitions='dp', witness=True,
                            stats=stats, external=spec['external'])
                points = tuple((c, q, Plan(tuple(spec['order']), w)) for c, q, w in raw)
            record.update(search_seconds=time.monotonic()-start, stage='replay',
                          points=[list(p[:2]) for p in points], witnesses=[asdict(p) for _, _, p in points])
            record['replays'] = [replay_private_boundary(graph, spec['external'], c, q, p) for c, q, p in points]
            record['status'] = 'complete' if all(c['exact'] for c in record['replays']) else 'invalid'
        record['stage'] = 'done'
    except Exception as exc:
        record.update(status='timeout' if isinstance(exc, TimeoutError) else
                      'memory' if isinstance(exc, MemoryError) else 'error', error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.alarm(0)
    if spec['mode'] != 'oracle':
        solver.stats.update(**{f'{k}_cache':getattr(solver,k).cache_info()._asdict() for k in ('solve','group','sequence')})
        record['stats'] = solver.stats
    record.update(seconds=time.monotonic()-start, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    save(args.out, record)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--worker', type=int)
    args = p.parse_args(); cases = specs()
    if args.worker is not None:
        worker(cases[args.worker], args); return
    args.out.mkdir(parents=True, exist_ok=False)
    save(args.out/'manifest.json', dict(specs=cases, revision=args.revision, source_sha256=hashes(),
                                      workers=4, seconds=60, mem_gib=6, hash_seed='0'))
    def run(i):
        path = args.out/f"{cases[i]['name']}.json"
        cmd = [sys.executable, '-m', __spec__.name, '--out', str(path), '--revision', args.revision, '--worker', str(i)]
        try:
            proc = subprocess.run(cmd, env=dict(os.environ,PYTHONHASHSEED='0'),capture_output=True,text=True,timeout=90)
            failure = dict(status='crash', exitcode=proc.returncode)
        except subprocess.TimeoutExpired:
            failure = dict(status='hard_timeout')
        record = json.loads(path.read_text()) if path.exists() else dict(spec=cases[i])
        if record.get('status') in (None,'running'):
            record.update(failure);save(path,record)
        return record
    records=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(run,i) for i in range(len(cases))]):
            r=f.result();records.append(r)
            print(json.dumps(dict(case=r['spec']['name'],status=r['status'],seconds=r.get('seconds'))),flush=True)
    save(args.out/'summary.json',dict(statuses={r['spec']['name']:r['status'] for r in records}))
    return int(any(r['status']!='complete' for r in records))


if __name__ == '__main__':
    raise SystemExit(main())
