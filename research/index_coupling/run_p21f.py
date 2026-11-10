"""P21f freeze/runner: --prepare never solves; --case/--arm runs one Linux job.

Freeze --prepare output as p21f_manifest.json before any new curve is searched.
See PROTOCOL.md for scoring and the separate, unscored tile diagnostic.
"""
import argparse
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import time

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import residual
from research.index_coupling.simulate_nest import simulate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MANIFEST = HERE / 'p21f_manifest.json'
DEPTH = 6
BETWEEN = ((2,4,6), (6,4,6), (2,6,8), (4,6,10),
           (2,8,12), (6,8,12), (2,10,16), (2,12,16))
ABOVE = ((2,4,12), (6,4,10), (2,6,16), (4,6,16),
         (2,8,20), (4,8,24), (2,10,24), (2,12,32))
BELOW = ((2,6,4), (6,6,4), (2,10,4), (6,10,4),
         (2,12,4), (6,12,4), (2,16,4), (6,16,4))
KNOWN = (((4,12,8), False), ((6,12,8), False), ((6,12,8), True))
SOURCES = ('PROTOCOL.md', 'run_p21f.py', 'score_p21f.py', 'test_p21f.py', 'graph/curve.py',
           'graph/model.py', 'graph/analysis.py', 'graph/span_names.py', 'simulate_nest.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cases():
    out = []
    for cohort, shapes in (('between', BETWEEN), ('above', ABOVE), ('below', BELOW)):
        for shape, reads_x in product(shapes, (False, True)):
            out.append(dict(case=len(out), shape=list(shape), depth=DEPTH,
                            reads_x=reads_x, cohort=cohort, held_out=True,
                            domains=['halving', 'divisors'] if cohort == 'below' else ['halving']))
    for shape, reads_x in KNOWN:
        out.append(dict(case=len(out), shape=list(shape), depth=DEPTH, reads_x=reads_x,
                        cohort='known_p21e_failure', held_out=False, domains=['halving', 'divisors']))
    return out


def known_reference(spec, arm):
    from research.index_coupling.run_p21e import CASES
    case = CASES.index((tuple(spec['shape']), spec['reads_x']))
    return HERE / 'results/p21e' / f'{case:02d}_{arm}.json'


def prepare():
    # Inspect input metadata only. Never search any of the proposed shapes.
    from research.index_coupling.run_p21 import CASES as p21
    from research.index_coupling.run_p21d import CASES as p21d
    from research.index_coupling.run_p21e import CASES as p21e
    sweep = HERE / 'results/p21e_explore/sweep.jsonl'
    seen = {tuple(r['shape']) for r in map(json.loads, sweep.read_text().splitlines())}
    seen |= {tuple(x[0]) for x in p21} | {tuple(x[0]) for x in p21d} | {tuple(x[0]) for x in p21e}
    overlap = seen & set(BETWEEN + ABOVE + BELOW)
    if overlap:
        raise ValueError(f'new shapes overlap declared prior residual evidence: {sorted(overlap)}')
    return dict(experiment='P21f', prior_evidence_revision='70c576b3', depth=DEPTH,
                cases=cases(), jobs=sum(2 * len(c['domains']) for c in cases()),
                source_sha256={name: sha(HERE / name) for name in SOURCES},
                prior_inputs_sha256={name: sha(HERE / name) for name in
                    ('run_p21.py', 'run_p21d.py', 'run_p21e.py', 'results/p21e_explore/sweep.jsonl')},
                known_reference_sha256={str(known_reference(s, a).relative_to(HERE)): sha(known_reference(s, a))
                    for s in cases() if not s['held_out'] for a in ('free', 'tied')},
                novelty_audit=dict(scope='P21, P21d, P21e and P21e exploratory residual inputs; shape only, any depth/mode',
                                   prior_shapes=[list(s) for s in sorted(seen)], overlap=[]),
                primary_strata=dict(read_x_between=8, read_x_above=8,
                                    independent_between=8, independent_above=8),
                pass_rule='all 8 in each primary stratum; diagnostics cannot rescue failures',
                wall_limit_seconds=1800, address_space_limit_gib=8, max_processes=4,
                options=dict(partitions='dp', grid=None, spill_cost=2, write_through=True,
                             split_shared=True, legacy_nested_writes=False))


def frozen():
    saved = json.loads(MANIFEST.read_text())
    if saved != prepare():
        raise ValueError('P21f source/input/protocol differs from frozen manifest')
    return saved


def path_for(directory, case, arm, domain):
    return Path(directory) / f'{case:02d}_{domain}_{arm}.json'


def save(path, record):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(record, allow_nan=False) + '\n')
    tmp.replace(path)


def timeout(*_):
    raise TimeoutError('frozen 1800 s search + replay limit')


def run(spec, arm, domain, path, manifest):
    if platform.system() != 'Linux':
        raise ValueError('held-out jobs run only on the designated Linux experiment server')
    if os.environ.get('PYTHONHASHSEED') != '0':
        raise ValueError('set PYTHONHASHSEED=0 for frozen P21f jobs')
    if domain not in spec['domains']:
        raise ValueError('tile domain not frozen for this case')
    if path.exists():
        raise FileExistsError(f'preserve existing record; use a new attempt directory: {path}')
    paths = [str((HERE / n).relative_to(ROOT)) for n in
             (*SOURCES, *manifest['prior_inputs_sha256'], *manifest['known_reference_sha256'])]
    paths.append(str(MANIFEST.relative_to(ROOT)))
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', *paths], cwd=ROOT, text=True)
    if dirty:
        raise ValueError('commit frozen P21f source and manifest before searching')
    resource.setrlimit(resource.RLIMIT_AS, (8 * 2**30, 8 * 2**30))
    signal.signal(signal.SIGALRM, timeout)
    record = dict(**spec, arm=arm, tile_domain=domain, experiment='P21f',
                  manifest_sha256=sha(MANIFEST), source_sha256=manifest['source_sha256'],
                  source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  python=platform.python_version(), hash_seed=os.environ.get('PYTHONHASHSEED'),
                  wall_limit_seconds=1800, address_space_limit_gib=8, status='running', stage='search')
    path.parent.mkdir(parents=True, exist_ok=True)
    save(path, record)
    start = time.monotonic()
    signal.alarm(1800)
    try:
        graph = residual(*spec['shape'], DEPTH, spec['reads_x'])
        options = dict(whole_span_cuts=range(2, len(graph.ops))) if arm == 'tied' else {}
        points = curve(graph, witness=True, tile_domain=domain, **manifest['options'], **options)
        record.update(stage='replay', search_seconds=time.monotonic() - start,
                      points=[list(p[:2]) for p in points], witnesses=points, replays=[])
        save(path, record)
        for c, q, witness in points:
            actual = simulate(graph, witness)
            exact = actual['valid'] and (actual['peak'], actual['traffic']) == (c, q)
            record['replays'].append(dict(capacity=c, traffic=q, exact=exact, actual=actual))
        record.update(status='complete' if points and all(r['exact'] for r in record['replays']) else 'invalid', stage='done')
    except Exception as exc:
        record.update(status='timeout' if isinstance(exc, TimeoutError) else
                      'memory' if isinstance(exc, MemoryError) else 'error', error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.alarm(0)
    record.update(seconds=time.monotonic() - start,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    save(path, record)
    print(json.dumps({k: record[k] for k in ('case', 'arm', 'tile_domain', 'status', 'seconds')}))
    return int(record['status'] != 'complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--case', type=int, choices=range(len(cases())))
    parser.add_argument('--arm', choices=('free', 'tied'))
    parser.add_argument('--domain', choices=('halving', 'divisors'), default='halving')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps(prepare(), indent=2))
        return 0
    manifest = frozen()
    if args.list:
        for spec in manifest['cases']:
            for domain, arm in product(spec['domains'], ('free', 'tied')):
                print(spec['case'], domain, arm)
        return 0
    if args.case is None or args.arm is None or args.output_dir is None:
        parser.error('--case, --arm and --output-dir required')
    return run(manifest['cases'][args.case], args.arm, args.domain,
               path_for(args.output_dir, args.case, args.arm, args.domain), manifest)


if __name__ == '__main__':
    raise SystemExit(main())
