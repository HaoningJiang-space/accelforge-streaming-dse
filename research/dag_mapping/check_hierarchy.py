"""Gate 1 only: certify D1 witnesses and unchanged complete native frontiers.

No independent optimizer is introduced. Fresh generation is still native DP.
Timing includes certification/execution and must not be used as a speedup.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
from time import perf_counter

from research.index_coupling.graph.curve import curve, pareto
from research.index_coupling.simulate_nest import simulate
from .boundary import resized, workload
from .hierarchy import analyze, decode, encode, tuples
from .score import score
from .study import ARMS
from .workloads import D1_CASES as CASES
from .artifacts import source_set, source_hashes, verify_sources


SOURCES = source_set(
    'research/dag_mapping/hierarchy.py', 'research/dag_mapping/check_hierarchy.py',
    'research/dag_mapping/boundary.py', 'research/dag_mapping/score.py',
    'research/dag_mapping/test_hierarchy.py', 'research/dag_mapping/test_boundary.py',
    'research/dag_mapping/INTERFACE_PLAN.md', 'research/dag_mapping/study.py',
    'research/index_coupling/graph/curve.py', 'research/index_coupling/graph/model.py',
    'research/index_coupling/simulate_nest.py',
    'research/index_coupling/test_prefix_sharing.py',
    'research/index_coupling/response/prefix.py',
)


def certify(graph, expected, notes):
    plan = decode(graph, notes)
    restored = encode(plan)
    if restored != tuples(notes):
        raise AssertionError('witness roundtrip differs')
    checked = analyze(graph, plan)
    if (checked['peak'], checked['traffic']) != tuple(expected):
        raise AssertionError('typed resource certificate differs')
    actual = simulate(graph, restored, scalar_leaf='v2')
    if not actual['valid'] or (actual['peak'], actual['traffic']) != tuple(expected):
        raise AssertionError('independent execution differs')
    return dict(point=list(expected), roundtrip=True, extra=checked['extra_traffic'],
                compulsory=checked['compulsory'], nodes=len(checked['calls']),
                loop_scopes=[c for c in checked['calls'] if c['kind'] == 'loop'],
                execution=actual), plan


def run(archive):
    # Validate the archive against its recorded Git source, even after main evolves.
    old = score(archive)
    records, key = [], None
    for name, (kind, shape) in CASES.items():
        path = archive / 'results' / (name + '.json')
        saved = json.loads(path.read_text())
        graph, _ = workload(kind, shape)
        row = dict(case=name, input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   archived=[], fresh=[])
        for arm in ARMS:
            source = saved['arms'][arm]
            for point, witness in zip(source['frontier'], source['witnesses'], strict=True):
                ordered = resized(graph, graph.sizes, witness['order'])
                checked, plan = certify(ordered, point, witness['notes'])
                row['archived'].append(dict(arm=arm, order=witness['order'], **checked))
                if name == 'fork_join_tiny' and arm == 'native_all_orders' and point == [5, 32]:
                    key = dict(plan=asdict(plan), **checked)
        # Keep exactly the archived global-order family; never choose local orders.
        aggregate = []
        for order in saved['orders']:
            ordered = resized(graph, graph.sizes, order)
            points = curve(ordered, witness=True, partitions='dp', scalar_leaf='v2')
            for p, q, notes in points:
                checked, _ = certify(ordered, (p, q), notes)
                row['fresh'].append(dict(order=order, notes=notes, **checked))
                aggregate.append((p, q, ()))
        frontier = [list(p[:2]) for p in pareto(aggregate)]
        if frontier != saved['arms']['native_all_orders']['frontier']:
            raise AssertionError(f'complete frontier differs: {name}')
        row.update(frontier=frontier, complete_equal=True)
        records.append(row)
        print(json.dumps(dict(case=name, archived=len(row['archived']), fresh=len(row['fresh']),
                              complete_equal=True)), flush=True)
    if key is None:
        raise AssertionError('missing key witness')
    return dict(cases=records, key_witness=key,
                original_D1=dict(cases=old['completed'], boundary_checks=old['native_boundary_checks'],
                                 root_replays=old['witness_replays']),
                archived_replays=sum(len(r['archived']) for r in records),
                fresh_replays=sum(len(r['fresh']) for r in records),
                interpretation='typed representation/certification only; no new search or speedup')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=Path('research/dag_mapping/results/d1'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('preserve prior result')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    verify_sources(revision, SOURCES)
    result = dict(revision=revision, python=platform.python_version(),
                  hash_seed=os.environ.get('PYTHONHASHSEED'),
                  source_sha256=source_hashes(SOURCES),
                  status='running')
    resource.setrlimit(resource.RLIMIT_AS, (2 * 2**30, 2 * 2**30))
    def timeout(*_):
        raise TimeoutError('120-second certificate limit')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(120)
    start = perf_counter()
    try:
        result.update(run(args.archive), status='complete')
    except Exception as exc:
        result.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.alarm(0)
        result.update(seconds=perf_counter()-start,
                      peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'seconds')}))
    return int(result['status'] != 'complete')


if __name__ == '__main__':
    raise SystemExit(main())
