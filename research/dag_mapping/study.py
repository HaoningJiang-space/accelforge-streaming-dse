"""Frozen small-DAG boundary diagnostic; no performance speedup claim."""
import argparse
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
from time import perf_counter

from research.index_coupling.graph.branch_symmetry import topological_orders
from research.index_coupling.graph.curve import curve, pareto
from research.index_coupling.simulate_nest import Specification, parse_witness, simulate
from .boundary import RegionComposer, boundary_description, compulsory, resized, workload
from .workloads import D1_CASES as CASES
from .artifacts import source_set, source_hashes


ARMS = ('native_all_orders', 'closed_materialized', 'closed_retained', 'shared_row_loop')
SOURCES = source_set(
    'research/dag_mapping/study.py', 'research/dag_mapping/PROTOCOL.md',
)


def numeric(points):
    return [list(p[:2]) for p in points]


def value(points, capacity):
    feasible = [p[1] for p in points if p[0] <= capacity]
    return min(feasible) if feasible else None


def compare(reference, restricted):
    rows = []
    for capacity in sorted({p[0] for p in reference} | {p[0] for p in restricted}):
        a, b = value(reference, capacity), value(restricted, capacity)
        if b is not None and (a is None or b < a):
            raise AssertionError('restricted arm improves complete reference: accounting or grammar error')
        if a != b:
            rows.append(dict(capacity=capacity, reference=a, restricted=b))
    return dict(equal=not rows, differing_breakpoints=rows)


def spanning_loops(graph, notes, regions):
    labels = {o: i for i, region in enumerate(regions) for o in region}
    root = parse_witness(Specification(graph), notes, scalar_leaf='v2')
    records = []

    def visit(node, sizes):
        touched = sorted({labels[o] for o in node.ops})
        if node.kind == 'loop':
            if len(touched) > 1:
                records.append(dict(operators=list(node.ops), regions=touched,
                                    rank=node.variable, tile=node.tile, extents=dict(sizes),
                                    kept=list(node.kept), refetched=list(node.dropped),
                                    partial_sums=[t for t in node.dropped
                                                  if t in {graph.output(o) for o in node.ops}]))
            sizes = dict(sizes, **{node.variable: node.tile})
        for child in node.children:
            visit(child, sizes)

    visit(root, graph.sizes)
    return records


def execute_case(name):
    kind, shape = CASES[name]
    graph, regions = workload(kind, shape)
    orders = tuple(topological_orders(graph))
    rows = {}
    for arm in ARMS:
        start = perf_counter()
        composer = None if arm == 'native_all_orders' else RegionComposer(graph, verify=True)
        generated, ledgers = [], []
        for order in orders:
            ordered = resized(graph, graph.sizes, order)
            blocks = tuple(tuple(o for o in order if o in r) for r in regions)
            if tuple(o for r in blocks for o in r) != order:
                raise ValueError('declared regions are not blocks in this legal order')
            if composer is None:
                ledger = {}
                points = curve(ordered, witness=True, partitions='dp', scalar_leaf='v2', stats=ledger)
                ledgers.append(ledger)
            else:
                extra = composer.compose(blocks, materialize=arm == 'closed_materialized')
                if arm == 'shared_row_loop':
                    extra = pareto(list(extra) + list(composer.shared_loop(blocks)))
                points = [(p, q + compulsory(graph, graph.sizes), w) for p, q, w in extra]
            generated.extend((p, q, dict(order=order, notes=w)) for p, q, w in points)
        points = pareto(generated)
        generation_seconds = perf_counter() - start
        replay_start = perf_counter()
        replays, loops = [], []
        for capacity, traffic, plan in points:
            ordered = resized(graph, graph.sizes, plan['order'])
            actual = simulate(ordered, plan['notes'], scalar_leaf='v2')
            exact = actual['valid'] and (actual['peak'], actual['traffic']) == (capacity, traffic)
            replays.append(dict(exact=exact, expected=[capacity, traffic], actual=actual))
            if not exact:
                raise AssertionError(dict(arm=arm, expected=[capacity, traffic], actual=actual))
            crossing = spanning_loops(ordered, plan['notes'], regions)
            if crossing:
                loops.append(dict(point=[capacity, traffic], loops=crossing))
        rows[arm] = dict(frontier=numeric(points), witnesses=[p[2] for p in points],
                         generation_seconds_including_checks=generation_seconds,
                         replay_seconds=perf_counter() - replay_start,
                         replays=replays, cross_region_loops=loops)
        if composer is not None:
            rows[arm]['work'] = composer.stats
            rows[arm]['comparison_to_complete'] = compare(rows['native_all_orders']['frontier'], points)
        else:
            rows[arm]['work'] = {field: sum(s[field] for s in ledgers)
                                for field in ('dp_transitions', 'loop_choices', 'pareto_candidates')}
            rows[arm]['work']['response_entries'] = sum(s[k]['currsize'] for s in ledgers
                                                        for k in ('solve_cache', 'group_cache'))
    return dict(case=name, kind=kind, shape=shape, operators=list(graph.ops),
                sizes=graph.sizes, access=graph.access, orders=orders,
                regions=regions, boundary=boundary_description(graph, regions), arms=rows)


def worker(args):
    if args.out.exists():
        raise ValueError('preserve existing experiment output')
    resource.setrlimit(resource.RLIMIT_AS, (6 * 2**30, 6 * 2**30))
    def timeout(*_):
        raise TimeoutError('180-second case limit')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(180)
    started = perf_counter()
    record = dict(case=args.case, revision=args.revision, status='running',
                  python=platform.python_version(), hash_seed=os.environ.get('PYTHONHASHSEED'),
                  source_sha256=source_hashes(SOURCES))
    try:
        record.update(execute_case(args.case), status='complete')
    except Exception as exc:
        record.update(status='timeout' if isinstance(exc, TimeoutError) else 'error',
                      error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.alarm(0)
        record.update(seconds=perf_counter() - started,
                      peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        args.out.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({k: record[k] for k in ('case', 'status', 'seconds')}), flush=True)
    return int(record['status'] != 'complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--case', choices=CASES)
    args = parser.parse_args()
    if args.case:
        return worker(args)
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = dict(revision=args.revision, cases=CASES, arms=ARMS,
                    seconds_per_case=180, memory_gib=6, processes='sequential', hash_seed=0)
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    exits = []
    for name in CASES:
        result = subprocess.run([sys.executable, '-m', 'research.dag_mapping.study',
                                 '--case', name, '--out', str(args.out / (name + '.json')),
                                 '--revision', args.revision],
                                env=dict(os.environ, PYTHONHASHSEED='0'))
        exits.append(dict(case=name, returncode=result.returncode))
    (args.out / 'exits.json').write_text(json.dumps(exits, indent=2) + '\n')
    return int(any(r['returncode'] for r in exits))


if __name__ == '__main__':
    raise SystemExit(main())
