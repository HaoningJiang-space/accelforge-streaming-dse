"""Row-projection lower bound for unit-M chains repeated over M > 1 rows (CONTRACTION_ORACLE.md §13).

Restricting any grammar plan of an M-row span to one row gives a unit-M
grammar plan of no larger peak, so R_m(C) >= m * R_1(C). R_1 takes every
weight resident (proved) or streamed weights as one cell each (conjectured).

Usage: python -m research.index_coupling.row_projection check CASE [CASE ...]
       python -m research.index_coupling.row_projection c2 CASE [CASE ...]
"""
import gzip
import json
from pathlib import Path
import sys

from research.index_coupling.c2_bound_audit import dominates, frontier
from research.index_coupling.census_tools import graph_of
from research.index_coupling.elementwise_chain import KIND, archived_chain, predict
from research.index_coupling.graph.analysis import traffic_at

R = Path(__file__).resolve().parent / 'results/c2_bound'


def rows_chain(graph, state):
    """Like archived_chain but for M > 1: unit-row sizes and the row count."""
    if state['stage'] != 'solve' or state['constrained']:
        return None
    names, ops = sorted(graph.sizes), state['ops']
    ext = dict(zip(names, state['ext']))
    external, owned = set(state['external']), set(state['owned'])
    if ext['M'] == 1 or tuple(ops) != graph.ops[graph.ops.index(ops[0]):][:len(ops)]:
        return None
    vectors = [list(graph.access[ops[0]])[0]] + [graph.output(op) for op in ops]
    weights = {t for op in ops for t in graph.access[op] if 'M' not in graph.access[op][t]}
    if set(vectors[1:-1]) & (external | owned):
        return None
    kinds = [KIND[op.rstrip('0123456789').rstrip('_')] for op in ops]
    sizes = [1] * len(vectors)
    for i, t in enumerate(vectors):
        for v in graph.dims(t):
            if v != 'M':
                sizes[i] *= ext[v]
    streamed = [int(any(t in weights - external for t in graph.access[op])) for op in ops]
    return kinds, sizes, vectors[0] in external, vectors[-1] in external, streamed, ext['M']


def check(cases):
    for case in cases:
        g = graph_of(case)
        nodes = json.load(gzip.open(R / case / 'baseline.json.gz', 'rt'))['nodes']
        c = dict(qualifying=0, violations=0, exact_resident=0, exact_streamed=0, violations_streamed=0)
        for n in nodes:
            ch = rows_chain(g, n['state'])
            if ch is None:
                continue
            kinds, sizes, first, last, streamed, m = ch
            c['qualifying'] += 1
            pts = n['points']
            caps = range(0, max(cc for cc, _ in pts) + 3)
            lb = [m * predict(kinds, sizes, C, 'halving', first, last) for C in caps]
            lbs = [m * predict(kinds, sizes, C, 'halving', first, last, streamed) for C in caps]
            act = [traffic_at(C, pts) for C in caps]
            c['violations'] += any(l > a for l, a in zip(lb, act))
            c['violations_streamed'] += any(l > a for l, a in zip(lbs, act))
            c['exact_resident'] += lb == act
            c['exact_streamed'] += lbs == act
        print(json.dumps(dict(case=case, **c)))


def combined(slots, child, alloc, extra, trips):
    lift = frontier((alloc + c, extra + trips * q) for c, q in child if q != float('inf'))
    caps = sorted({c for c, _ in slots} | {c for c, _ in lift})
    return frontier((c, max(traffic_at(c, slots), traffic_at(c, lift))) for c in caps)


def c2(cases):
    for case in cases:
        g = graph_of(case)
        nodes = {n['id']: n for n in json.load(gzip.open(R / case / 'baseline.json.gz', 'rt'))['nodes']}
        c = dict(proper=0, unit=0, rows=0, rows_slots=0, rows_proved=0, rows_conj=0, rows_strict_slots=0, rows_strict_proved=0)
        for line in gzip.open(R / case / 'choices.jsonl.gz', 'rt'):
            r = json.loads(line); c['proper'] += 1
            par = frontier(nodes[r['parent']]['points'])
            slots = [tuple(p) for p in r['slots_bound']]
            s = dominates(par, slots)
            st = nodes[r['child']]['state']
            if archived_chain(g, st) is not None:
                c['unit'] += 1; continue
            ch = rows_chain(g, st)
            if ch is None:
                continue
            c['rows'] += 1; c['rows_slots'] += s
            # strict: the bound lies strictly above the parent frontier somewhere it is finite
            strict = lambda b: any(traffic_at(cc, b) > traffic_at(cc, par) for cc, _ in b)
            c['rows_strict_slots'] += strict(slots)
            kinds, sizes, first, last, streamed, m = ch
            parent = nodes[r['parent']]['state']
            trips = parent['ext'][sorted(g.sizes).index(r['axis'])] // r['tile']
            top = m * sum(sizes) + sum(sizes) ** 2 + 4
            for key, fl in (('proved', None), ('conj', streamed)):
                child = [(C, m * predict(kinds, sizes, C, 'halving', first, last, fl)) for C in range(top)]
                b = combined(slots, child, r['allocation'], r['extra'], trips)
                assert dominates(b, [tuple(p) for p in r['actual']]), (case, key)
                c['rows_' + key] += dominates(par, b)
                if key == 'proved':
                    c['rows_strict_proved'] += strict(b)
        print(json.dumps(dict(case=case, **c)))


if __name__ == '__main__':
    {'check': check, 'c2': c2}[sys.argv[1]](sys.argv[2:])
