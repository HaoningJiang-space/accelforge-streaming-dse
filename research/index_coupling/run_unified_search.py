"""Bounded eight-arm study of exact decomposition, quotient and certificates."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
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
from time import perf_counter, process_time

from .fork_order_oracle import replay_private_boundary
from .unified_search import UnifiedSearch, mixed_branch_graph, serializable_point

CASES = dict(skinny=(1, 2, 1, 2), core=(2, 2, 2, 2), rectangle=(2, 3, 2, 4))
SOURCES = ('unified_search.py', 'run_unified_search.py', 'UNIFIED_SEARCH_PROTOCOL.md',
           'graph/curve.py', 'graph/model.py', 'graph/branch_symmetry.py',
           'graph/fork_quotient.py', 'graph/span_names.py', 'fork_order_oracle.py', 'simulate_nest.py')


def hashes():
    here = Path(__file__).parent
    return {n: hashlib.sha256((here / n).read_bytes()).hexdigest() for n in SOURCES}


def worker(args):
    if sys.platform != 'linux':
        raise ValueError('bounded workers require Linux')
    if args.out.exists():
        raise ValueError('preserve the existing attempt')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    resource.setrlimit(resource.RLIMIT_AS, (6 * 2**30, 6 * 2**30))
    def timeout(*_):
        raise TimeoutError('180-second search/census/replay budget')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(180)
    record = dict(case=args.case, shape=CASES[args.case], switches=args.bits,
                  mode=args.mode, revision=args.revision, source_sha256=hashes(),
                  python=platform.python_version(), hash_seed=os.environ.get('PYTHONHASHSEED'),
                  budgets=dict(seconds=180, mem_gib=6), status='running', state_records=0)
    census = None
    search = None
    start, cpu = perf_counter(), process_time()
    try:
        if args.mode == 'census':
            census = gzip.open(args.out.with_suffix('.states.jsonl.gz'), 'wt')
        def observe(order, state, points):
            census.write(json.dumps(dict(order=order, state=state, points=points), separators=(',', ':')) + '\n')
            record['state_records'] += 1
        graph = mixed_branch_graph(CASES[args.case])
        search = UnifiedSearch(graph, args.bits, observer=observe if census is not None else None,
                               profile=args.mode == 'census')
        points = search.query()
        record['search_seconds'] = perf_counter() - start
        record['points'] = [serializable_point(p) for p in points]
        selected = {(p[3]['order'], cid) for p in points for cid in p[3]['certificates']}
        record['selected_certificates'] = [dict(order=order, id=cid, **search.proofs[order, cid])
                                           for order, cid in sorted(selected)]
        record['joint_chain'] = args.bits == '111' and any(
            any(s['stage'] == 'cut_dp' for s in p['ancestors']) for p in record['selected_certificates'])
        record['replays'] = [replay_private_boundary(graph, (), c, q, plan) for c, q, plan, _ in points]
        record['status'] = 'complete' if all(p['exact'] for p in record['replays']) else 'invalid'
    except Exception as exc:
        record.update(status='timeout' if isinstance(exc, TimeoutError) else 'error',
                      error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.alarm(0)
        if census is not None:
            census.close()
        record.update(seconds=perf_counter() - start, cpu_seconds=process_time() - cpu,
                      peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if search is not None:
            record['stats'] = search.stats
        args.out.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({k: record.get(k) for k in ('case', 'switches', 'mode', 'status', 'search_seconds', 'state_records', 'joint_chain')}), flush=True)
    return int(record['status'] != 'complete')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--worker', action='store_true')
    p.add_argument('--case', choices=CASES)
    p.add_argument('--bits')
    p.add_argument('--mode', choices=('census', 'timing'), default='census')
    args = p.parse_args()
    if args.worker:
        return worker(args)
    if args.out.exists():
        p.error('preserve the existing study directory')
    args.out.mkdir(parents=True)
    bits = [''.join(v) for v in product('01', repeat=3)]
    if args.mode == 'census':
        jobs = [dict(case=c, bits=b, name=f'{c}_{b}') for c in CASES for b in bits]
    else:
        jobs = [dict(case=c, bits=b, name=f'{c}_{b}_r{r}') for c in ('core', 'rectangle')
                for r in range(3) for b in (('000', '111') if r % 2 == 0 else ('111', '000'))]
    manifest = dict(revision=args.revision, source_sha256=hashes(), jobs=jobs,
                    mode=args.mode, workers=4 if args.mode == 'census' else 1,
                    budgets=dict(seconds=180, mem_gib=6), hash_seed='0')
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    def launch(job):
        cmd = [sys.executable, '-m', 'research.index_coupling.run_unified_search', '--worker',
               '--case', job['case'], '--bits', job['bits'], '--mode', args.mode,
               '--out', str(args.out / (job['name'] + '.json')), '--revision', args.revision]
        result = subprocess.run(cmd, env=dict(os.environ, PYTHONHASHSEED='0'), capture_output=True, text=True)
        print(result.stdout.strip() or json.dumps(dict(case=job['case'], bits=job['bits'], exit_code=result.returncode)), flush=True)
        return result.returncode
    with ThreadPoolExecutor(max_workers=manifest['workers']) as pool:
        exits = list(pool.map(launch, jobs))
    (args.out / 'exits.json').write_text(json.dumps(exits) + '\n')
    return int(any(exits))


if __name__ == '__main__':
    raise SystemExit(main())
