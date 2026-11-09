"""Check that projected cache keys (curve_model.py) reproduce archived curves.

Usage: python -m research.index_coupling.verify_projection [workers] [--witness-only]
Recomputes every small archived curve: graph, no write-through and chain views
(classify_v2_small), FFM-like (p14_small), the coupling sweeps, and P18. A few
witness runs check both the returned points and independent cell execution.
"""
import argparse
import json
import sys
from multiprocessing import Pool
from pathlib import Path

from research.index_coupling.chain_view import chain_curve
from research.index_coupling.compare_curves import cases
from research.index_coupling.coupling_sweep import run as sweep_run
from research.index_coupling.curve_model import curve
from research.index_coupling.ffm_like import ffm_like_curve
from research.index_coupling.nest_model import fork
from research.index_coupling.simulate_nest import simulate

R = Path(__file__).parent / 'results'


def pts(points):
    return [list(p[:2]) for p in points]


def load(name):
    return [json.loads(line) for line in (R / name).read_text().splitlines() if line.strip()]


def job(task):
    kind, key, expected = task
    executed = 0
    if kind == 'small':
        graph = dict((n, g) for n, g, _ in cases())[key[0]]
        got = {'graph': curve, 'no_write_through': lambda g: curve(g, write_through=False),
               'chain': chain_curve, 'ffm_like': ffm_like_curve}[key[1]](graph)
    elif kind == 'sweep':
        got = sweep_run(tuple(key))
        return kind, key, all(got[k] == expected[k] for k in expected if k != 'shape'), executed
    elif kind == 'p18':
        got = curve(fork(*key[0], key[1]))
    else:
        graph = fork(*key[0], key[1])
        got = curve(graph, witness=True)
        for capacity, traffic, witness in got:
            actual = simulate(graph, witness)
            if not actual['valid'] or (actual['peak'], actual['traffic']) != (capacity, traffic):
                raise AssertionError((key, capacity, traffic, actual))
            executed += 1
    return kind, key, pts(got) == pts(expected), executed


def tasks():
    for r in load('classify_v2_small.jsonl'):
        for col in ('graph', 'no_write_through', 'chain'):
            yield 'small', (r['case'], col), r[col]
    for r in load('p14_small.jsonl'):
        yield 'small', (r['case'], 'ffm_like'), r['ffm_like']
    for name in ('coupling_sweep.jsonl', 'coupling_sweep_heldout.jsonl'):
        for r in load(name):
            yield 'sweep', r['shape'], r
    for r in load('p18.jsonl'):
        yield 'p18', (r['shape'], r['roles']), r['points']
        if r['shape'][0] == 4:
            yield 'witness', (r['shape'], r['roles']), r['points']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workers', type=int, nargs='?', default=4)
    parser.add_argument('--witness-only', action='store_true')
    args = parser.parse_args()
    pending = [t for t in tasks() if not args.witness_only or t[0] == 'witness']
    bad = total = executed = 0
    with Pool(args.workers) as pool:
        for kind, key, ok, count in pool.imap_unordered(job, pending):
            total += 1
            bad += not ok
            executed += count
            if args.witness_only:
                print(json.dumps(dict(kind=kind, key=key, match=ok, witnesses_executed=count)), flush=True)
            if not ok:
                print('MISMATCH', kind, key, flush=True)
    print(f'checked {total}, mismatches {bad}, executed witnesses {executed}', flush=True)
    sys.exit(1 if bad or total != len(pending) else 0)
