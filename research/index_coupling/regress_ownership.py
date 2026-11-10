"""Regression of archived curves after the final-write ownership fix.

graph/curve.py now passes each partition's owned final writes to its children
(legacy_nested_writes=True restores the old double charge). This recomputes the
archived curves with the fixed default and reports, per task, whether the curve
changed. For every task on a plain graph whose curve changed, all new frontier
witnesses are executed by simulate_nest.py; a valid fix must only lower or keep
traffic, and every new point must replay exactly.

Usage (designated server, capped): python -m research.index_coupling.regress_ownership
    [workers] [--p19-n16] [--mem-gib G] [--seconds S]
Prints one JSON line per task and a final summary line.
"""
import argparse
import json
import resource
import signal
import sys
import time
from multiprocessing import Pool
from pathlib import Path

from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.experiments import run_sweep
from research.index_coupling.graph.model import fork, residual
from research.index_coupling.graph.references import cases
from research.index_coupling.graph.views import chain_curve, ffm_like_curve
from research.index_coupling.simulate_nest import simulate

R = Path(__file__).parent / 'results'
SECONDS = 3600


def pts(points):
    return [list(p[:2]) for p in points]


def load(name):
    return [json.loads(line) for line in (R / name).read_text().splitlines() if line.strip()]


def graph_of(kind, key):
    if kind in ('p18', 'p19'):
        return fork(*key[0], key[1])
    if kind in ('p21', 'p21d'):
        return residual(*key[1], key[2], key[3])
    return dict((n, g) for n, g, _ in cases())[key[0]]


def compare(old, new):
    # Integer capacities through the last breakpoint where traffic differs.
    hi = max(p[0] for p in old + new)
    rows = [(c, traffic_at(c, old), traffic_at(c, new)) for c in range(hi + 1)]
    diff = [(c, o, n) for c, o, n in rows if o != n]
    return dict(changed=len(diff), lower=sum(n < o for _, o, n in diff),
                higher=sum(n > o for _, o, n in diff),
                max_drop=max((o - n for _, o, n in diff if n < o and o != float('inf')), default=0),
                first=[[c, o, n] for c, o, n in diff[:5]])


def job(task):
    kind, key, old, options = task
    start = time.time()

    def alarm(*_):
        raise TimeoutError
    signal.signal(signal.SIGALRM, alarm)
    signal.alarm(SECONDS)
    try:
        if kind == 'sweep':
            new = run_sweep(tuple(key))
            same = all(new[k] == old[k] for k in old if k != 'shape')
            return dict(kind=kind, key=key, match=same, seconds=time.time() - start,
                        **({} if same else dict(old={k: old[k] for k in old if k != 'shape' and new[k] != old[k]},
                                                new={k: new[k] for k in old if k != 'shape' and new[k] != old[k]})))
        if kind == 'small' and key[1] in ('chain', 'ffm_like'):
            new = pts({'chain': chain_curve, 'ffm_like': ffm_like_curve}[key[1]](graph_of(kind, key)))
            out = dict(kind=kind, key=key, match=new == old, seconds=time.time() - start)
            return out if new == old else dict(out, old=old, new=new, diff=compare(old, new))
        graph = graph_of(kind, key)
        points = curve(graph, witness=True, **options)
        new = pts(points)
        out = dict(kind=kind, key=key, match=new == old, seconds=time.time() - start)
        if new == old:
            return out
        replays = []
        for c, q, w in points:
            a = simulate(graph, w)
            replays.append(a['valid'] and (a['peak'], a['traffic']) == (c, q))
        return dict(out, old=old, new=new, diff=compare(old, new),
                    replayed=len(replays), replay_exact=sum(replays), seconds=time.time() - start)
    except TimeoutError:
        return dict(kind=kind, key=key, match=None, status='timeout', seconds=time.time() - start)
    except MemoryError:
        return dict(kind=kind, key=key, match=None, status='memory', seconds=time.time() - start)
    finally:
        signal.alarm(0)


def tasks(p19_n16):
    for r in load('classify_v2_small.jsonl'):
        yield 'small', (r['case'], 'graph'), r['graph'], {}
        yield 'small', (r['case'], 'no_write_through'), r['no_write_through'], dict(write_through=False)
        yield 'small', (r['case'], 'chain'), r['chain'], {}
    for r in load('p14_small.jsonl'):
        yield 'small', (r['case'], 'ffm_like'), r['ffm_like'], {}
    for name in ('coupling_sweep.jsonl', 'coupling_sweep_heldout.jsonl'):
        for r in load(name):
            yield 'sweep', r['shape'], r, {}
    for r in load('p18.jsonl'):
        yield 'p18', (r['shape'], r['roles']), r['points'], {}
    for r in load('p19.jsonl'):
        if r['shape'][0] == 8 or p19_n16:
            yield 'p19', (r['shape'], r['roles']), r['points'], {}
    for path in sorted((R / 'p21').glob('case_*.json')):
        r = json.loads(path.read_text())['result']
        yield 'p21', (r['case'], r['shape'], r['depth'], r['reads_x']), \
            r['interfaces'][0]['curves']['unrestricted'], {}
    for path in sorted((R / 'p21d').glob('*_*.json')):
        r = json.loads(path.read_text())
        if 'arm' not in r or r.get('status') not in ('complete', 'invalid'):
            continue
        options = dict(whole_span_cuts=r['cut_rule']['positions']) if r['arm'] == 'structural' else {}
        yield 'p21d', (f"{r['case']}:{r['arm']}", r['shape'], r['depth'], r['reads_x']), pts(r['points']), options


def init(mem_gib):
    limit = int(mem_gib * 2**30)
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workers', type=int, nargs='?', default=4)
    parser.add_argument('--p19-n16', action='store_true')
    parser.add_argument('--mem-gib', type=float, default=6)
    parser.add_argument('--seconds', type=int, default=3600)
    args = parser.parse_args()
    SECONDS = args.seconds
    pending = list(tasks(args.p19_n16))
    counts = dict(total=0, match=0, changed=0, incomplete=0, replay_failures=0)
    with Pool(args.workers, initializer=init, initargs=(args.mem_gib,)) as pool:
        for out in pool.imap_unordered(job, pending):
            counts['total'] += 1
            counts['match' if out['match'] else 'incomplete' if out['match'] is None else 'changed'] += 1
            counts['replay_failures'] += out.get('replayed', 0) - out.get('replay_exact', 0)
            print(json.dumps(out), flush=True)
    print(json.dumps(dict(summary=counts, expected=len(pending))), flush=True)
    sys.exit(0 if counts['total'] == len(pending) and not counts['replay_failures'] else 1)
