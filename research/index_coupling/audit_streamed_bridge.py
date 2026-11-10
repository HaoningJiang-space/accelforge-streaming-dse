"""Bounded exploratory validation and coverage census, not a timing benchmark."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import time

from research.index_coupling.audit_residency_states import instrumented_curve
from research.index_coupling.graph.model import fork
from research.index_coupling.scalar_bridge import make_scalar_bridge_curve
from research.index_coupling.simulate_nest import simulate
from research.index_coupling.streamed_bridge import make_streamed_bridge_curve, streamed_response
from research.index_coupling.test_streamed_bridge import conditional_cases, framed_streamed_witness

HERE = Path(__file__).parent
CASES = ((4,2,2,2,'kkk'), (4,2,4,2,'kki'),
         (4,2,2,2,'kkkk'), (4,2,4,2,'kkii'))


def hashes():
    names = ('streamed_bridge.py', 'test_streamed_bridge.py', 'audit_streamed_bridge.py',
             'scalar_bridge.py', 'test_scalar_bridge.py', 'audit_residency_states.py',
             'graph/curve.py', 'graph/model.py', 'graph/span_names.py', 'simulate_nest.py')
    return {n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in names}


def observer(graph):
    counts, qualified = Counter(), []

    def check(state):
        counts['all_states'] += 1
        if state['stage'] != 'solve' or state['constrained']:
            return
        predicted = streamed_response(graph, state['ops'], state['ext'], state['external'],
                                      state['owned'], sorted(graph.sizes))
        if predicted is None:
            return
        same = tuple(map(tuple, state['points'])) == tuple(p[:2] for p in predicted)
        counts['eligible'] += 1
        counts['wrong'] += not same
        qualified.append(dict(state=state, predicted=predicted, exact=same))

    return counts, qualified, check


def replay(graph, points):
    rows = []
    for c, q, notes in points:
        actual = simulate(graph, notes)
        rows.append(dict(capacity=c, traffic=q,
                         exact=actual['valid'] and (actual['peak'], actual['traffic']) == (c,q)))
    return rows


def archived(directory):
    record = json.loads((directory / 'run.json').read_text())
    if record['status'] != 'complete' or not record['cache_count_matches']:
        raise ValueError('requires complete existing census')
    graph = fork(*record['graph_args'])
    counts, qualified, check = observer(graph)
    raw = directory / 'states.jsonl.gz'
    with gzip.open(raw, 'rt') as stream:
        for line in stream:
            check(json.loads(line))
    if counts['all_states'] != record['completed_states']:
        raise ValueError('incomplete census stream')
    return dict(case=record['case'], shape=record['graph_args'], counts=dict(counts),
                eligible_states=qualified, raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                source_sha256=record['source_sha256'])


def fresh(shape):
    graph = fork(*shape)
    counts, qualified, check = observer(graph)
    variants = {}
    for name, compute in (('baseline', instrumented_curve(check)),
                          ('scalar', make_scalar_bridge_curve()),
                          ('streamed', make_streamed_bridge_curve())):
        stats = {}
        points = compute(graph, partitions='dp', witness=True, stats=stats)
        variants[name] = dict(points=[list(p[:2]) for p in points], witnesses=points,
                              replays=replay(graph, points), stats=stats)
    expected_count = sum(variants['baseline']['stats'][key]['currsize']
                         for key in ('solve_cache', 'group_cache'))
    count_matches = counts['all_states'] == expected_count
    equal = all(r['points'] == variants['baseline']['points'] for r in variants.values())
    exact = all(row['exact'] for r in variants.values() for row in r['replays'])
    return dict(shape=shape, counts=dict(counts), eligible_states=qualified, variants=variants,
                count_matches=count_matches, equal=equal, replays_exact=exact,
                valid=count_matches and equal and exact and counts['wrong'] == 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=20, help='per fresh case, including all three variants')
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error('positive budget required')
    args.out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    initial_hashes = hashes()
    manifest = dict(revision=subprocess.check_output(['git','rev-parse','HEAD'], cwd=HERE, text=True).strip(),
                    source_sha256=initial_hashes, started_utc=datetime.now(timezone.utc).isoformat(),
                    hash_seed=os.environ.get('PYTHONHASHSEED'), python=platform.python_version(),
                    status='running', seconds_per_fresh_case=args.seconds, memory_cap_bytes=2**30,
                    memory_enforcement='RLIMIT_AS + sampled peak RSS' if platform.system() == 'Linux' else 'sampled peak RSS',
                    scope='Exploratory deterministic work census; profiled/observed timings are not a speed benchmark.')
    manifest_path = args.out / 'summary.json'

    def save():
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')

    cap = 2**30
    if platform.system() == 'Linux':
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    deadline = float('inf')

    def watch(*_):
        if time.monotonic() >= deadline:
            raise TimeoutError('streamed bridge case budget')
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if (rss if platform.system() == 'Darwin' else rss * 1024) > cap:
            raise MemoryError('streamed bridge audit peak RSS cap')

    signal.signal(signal.SIGALRM, watch)
    signal.setitimer(signal.ITIMER_REAL, .25, .25)
    save()
    try:
        manifest['archived'] = [archived(HERE/'results/residency_states'/name)
                               for name in ('same6_serial40', 'mixed6_serial40')]
        manifest['fresh'] = []
        for shape in CASES:
            deadline = time.monotonic() + args.seconds
            row = fresh(shape)
            filename = f"I{shape[0]}K{shape[2]}_{shape[4]}.json"
            (args.out / filename).write_text(json.dumps(row, indent=2) + '\n')
            brief = {k: row[k] for k in ('shape','counts','valid')}
            brief['file'] = filename
            manifest['fresh'].append(brief)
            print(json.dumps(brief), flush=True)
            save()
        deadline = time.monotonic() + args.seconds
        framed = []
        for shape, graph, resident in conditional_cases():
            child = streamed_response(graph, graph.ops, tuple(graph.sizes.values()),
                                      resident, set(), tuple(graph.sizes), witness=True)
            parent, notes, c, q = framed_streamed_witness(graph, resident, child)
            actual = simulate(parent, notes)
            framed.append(dict(shape=shape, resident=sorted(resident), internal=child,
                               witness=notes, expected=[c,q], actual=[actual['peak'],actual['traffic']],
                               exact=actual['valid'] and (actual['peak'],actual['traffic']) == (c,q)))
        with gzip.open(args.out/'framed.json.gz', 'wt') as stream:
            json.dump(framed, stream)
        manifest.update(framed_cases=len(framed), framed_exact=all(r['exact'] for r in framed),
                        source_unchanged=hashes() == initial_hashes)
        valid = (manifest['source_unchanged'] and manifest['framed_exact']
                 and all(r['valid'] for r in manifest['fresh'])
                 and all(not r['counts'].get('wrong',0) for r in manifest['archived']))
        manifest['status'] = 'complete' if valid else 'invalid'
    except Exception as exc:
        manifest.update(status='error', error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        manifest['seconds'] = time.monotonic() - start
        save()
    return int(manifest['status'] != 'complete')


if __name__ == '__main__':
    raise SystemExit(main())
