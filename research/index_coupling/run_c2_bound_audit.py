"""Run capped unpruned v2 baselines, then analyze C2 entirely offline."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
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

from .c2_bound_audit import BaselineRecorder, CASES, analyze
from .census_tools import graph_of

HERE = Path(__file__).parent
SOURCES = ('c2_bound_audit.py', 'run_c2_bound_audit.py', 'census_tools.py', 'C2_BOUND_PROTOCOL.md',
           'graph/curve.py', 'graph/model.py', 'graph/stacks.py', 'graph/span_names.py',
           'graph/remainder.py', 'run_ancestor_width.py', 'graph/analysis.py')


def hashes():
    return {n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in SOURCES}


def worker(args):
    if sys.platform != 'linux':
        raise ValueError('bounded worker requires Linux')
    args.out.mkdir(parents=True, exist_ok=False)
    resource.setrlimit(resource.RLIMIT_AS, (6 * 2**30, 6 * 2**30))
    def timeout(*_):
        raise TimeoutError('300-second baseline/analysis budget')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(300)
    start = perf_counter()
    record = dict(case=args.case, revision=args.revision, source_sha256=hashes(), status='running',
                  python=platform.python_version(), hash_seed=os.environ.get('PYTHONHASHSEED'),
                  budgets=dict(seconds=300, mem_gib=6),
                  options=dict(partitions='dp', scalar_leaf='v2', tile_domain='halving', witness=False,
                               canonical_spans=False, canonical_remainders=False, independent_ops=False,
                               prune_infeasible_groups=False))
    try:
        graph = graph_of(args.case)
        record['graph'] = dict(sizes=graph.sizes, operators=[(o, graph.access[o]) for o in graph.ops])
        baseline = BaselineRecorder().run(graph)
        record['baseline_seconds'] = perf_counter() - start
        root_archive = HERE / 'results/grammar_v2/check' / f'{args.case}.v2.json'
        expected = json.loads(root_archive.read_text())
        record['root_archive_sha256'] = hashlib.sha256(root_archive.read_bytes()).hexdigest()
        record['root_equal'] = json.loads(json.dumps(baseline['points'])) == expected['v2']
        assert record['root_equal']
        old_census = HERE / 'results/grammar_v2/census' / f'{args.case}_v2.json'
        if old_census.exists():
            old = json.loads(old_census.read_text())
            record['old_census_sha256'] = hashlib.sha256(old_census.read_bytes()).hexdigest()
            record['census_count_equal'] = len(baseline['nodes']) == old['keys']
            assert record['census_count_equal']
        with gzip.open(args.out / 'baseline.json.gz', 'wt') as stream:
            json.dump(baseline, stream, separators=(',', ':'))
        begin = perf_counter()
        report, details = analyze(args.case, baseline)
        record['analysis_seconds'] = perf_counter() - begin
        with gzip.open(args.out / 'choices.jsonl.gz', 'wt') as stream:
            for row in details:
                stream.write(json.dumps(row, separators=(',', ':')) + '\n')
        (args.out / 'analysis.json').write_text(json.dumps(report, indent=2) + '\n')
        record.update(status='complete', states=report['states'], decisions=report['counts']['proper'],
                      summary=report['strata'].get('all', {}),
                      ordered_work_projection=report['ordered_work_projection'])
    except Exception as exc:
        record.update(status='timeout' if isinstance(exc, TimeoutError) else 'error',
                      error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.alarm(0)
        record.update(seconds=perf_counter() - start,
                      peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        record['artifacts_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in args.out.iterdir() if p.is_file()}
        (args.out / 'run.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({k: record.get(k) for k in ('case', 'status', 'states', 'decisions', 'summary', 'seconds')}), flush=True)
    return int(record['status'] != 'complete')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--case', choices=CASES)
    p.add_argument('--worker', action='store_true')
    args = p.parse_args()
    if args.worker:
        return worker(args)
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = dict(cases=CASES, revision=args.revision, source_sha256=hashes(), workers=4,
                    budgets=dict(seconds=300, mem_gib=6), hash_seed='0')
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    def launch(case):
        cmd = [sys.executable, '-m', 'research.index_coupling.run_c2_bound_audit', '--worker',
               '--case', case, '--out', str(args.out / case), '--revision', args.revision]
        r = subprocess.run(cmd, env=dict(os.environ, PYTHONHASHSEED='0'), capture_output=True, text=True)
        print(r.stdout.strip() or json.dumps(dict(case=case, exit=r.returncode)), flush=True)
        return r.returncode
    with ThreadPoolExecutor(max_workers=4) as pool:
        exits = list(pool.map(launch, CASES))
    (args.out / 'exits.json').write_text(json.dumps(exits) + '\n')
    return int(any(exits))


if __name__ == '__main__':
    raise SystemExit(main())
