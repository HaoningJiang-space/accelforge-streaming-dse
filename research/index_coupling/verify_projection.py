"""Check that projected cache keys (curve_model.py) reproduce archived curves.

Usage: python -m research.index_coupling.verify_projection [workers]
Recomputes every small archived curve: graph, no write-through and chain views
(classify_v2_small), FFM-like (p14_small), the coupling sweeps, and P18. A few
witness runs check that the witness path returns the same points.
"""
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

R = Path(__file__).parent / 'results'


def pts(points):
    return [list(p[:2]) for p in points]


def load(name):
    return [json.loads(line) for line in (R / name).read_text().splitlines() if line.strip()]


def job(task):
    kind, key, expected = task
    if kind == 'small':
        graph = dict((n, g) for n, g, _ in cases())[key[0]]
        got = {'graph': curve, 'no_write_through': lambda g: curve(g, write_through=False),
               'chain': chain_curve, 'ffm_like': ffm_like_curve}[key[1]](graph)
    elif kind == 'sweep':
        got = sweep_run(tuple(key))
        return kind, key, all(got[k] == expected[k] for k in expected if k != 'shape')
    elif kind == 'p18':
        got = curve(fork(*key[0], key[1]))
    else:
        got = curve(fork(*key[0], key[1]), witness=True)
    return kind, key, pts(got) == pts(expected)


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
    bad = total = 0
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as pool:
        for kind, key, ok in pool.imap_unordered(job, list(tasks())):
            total += 1
            bad += not ok
            if not ok:
                print('MISMATCH', kind, key, flush=True)
    print(f'checked {total}, mismatches {bad}', flush=True)
