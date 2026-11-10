"""Operator-projection lower bound for chain spans at any M (CONTRACTION_ORACLE.md §14).

Projecting a grammar plan of a chain span onto one contraction gives a
grammar plan of that operator alone with no larger peak, and the extra
traffic events of distinct operators are disjoint. Hence

    R_chain(C) >= sum_j R_j(C),

where R_j is the keep-level optimum of operator j alone (matmul_keep) with
its weight's residency as in the span and its activations live unless they
are resident span ends. Elementwise operators contribute 0.

Usage: python -m research.index_coupling.op_projection check CASE [CASE ...]
       python -m research.index_coupling.op_projection c2 CASE [CASE ...]
"""
from functools import lru_cache
import gzip
import json
from pathlib import Path
import sys

from research.index_coupling.c2_bound_audit import dominates, frontier
from research.index_coupling.census_tools import graph_of
from research.index_coupling.elementwise_chain import KIND
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.matmul_keep import predict as op_response

R = Path(__file__).resolve().parent / 'results/c2_bound'
DOMAIN = 'halving'  # run_c2_bound_audit.py


def chain_ops(graph, state):
    """Per-contraction (ext, live) of a qualifying solve node, else None."""
    if state['stage'] != 'solve' or state['constrained']:
        return None
    names, ops = sorted(graph.sizes), state['ops']
    ext = dict(zip(names, state['ext']))
    external, owned = set(state['external']), set(state['owned'])
    if tuple(ops) != graph.ops[graph.ops.index(ops[0]):][:len(ops)]:
        return None
    vectors = [list(graph.access[ops[0]])[0]] + [graph.output(op) for op in ops]
    if set(vectors[1:-1]) & (external | owned):
        return None
    out = []
    for j, op in enumerate(ops):
        if KIND[op.rstrip('0123456789').rstrip('_')] == 'e':
            continue
        x, y = vectors[j], vectors[j + 1]
        (w,) = [t for t in graph.access[op] if 'M' not in graph.access[op][t]]
        d_in = [v for v in graph.dims(x) if v != 'M'][0]
        d_out = [v for v in graph.dims(y) if v != 'M'][0]
        live = tuple(name for name, t in (('X', x), ('W', w), ('Y', y)) if t not in external)
        out.append(((ext['M'], ext[d_in], ext[d_out]), live))
    return tuple(out)


@lru_cache(maxsize=None)
def bound(ops, capacity):
    return sum(op_response(e, live, capacity, DOMAIN) for e, live in ops)


def check(cases):
    for case in cases:
        g = graph_of(case)
        nodes = json.load(gzip.open(R / case / 'baseline.json.gz', 'rt'))['nodes']
        c = dict(qualifying=0, multi_row=0, violations=0, exact=0, positive=0)
        example = None
        for n in nodes:
            ops = chain_ops(g, n['state'])
            if ops is None:
                continue
            c['qualifying'] += 1
            c['multi_row'] += n['state']['ext'][sorted(g.sizes).index('M')] > 1
            pts = n['points']
            caps = range(0, max(cc for cc, _ in pts) + 3)
            lb = [bound(ops, C) for C in caps]
            act = [traffic_at(C, pts) for C in caps]
            bad = any(l > a for l, a in zip(lb, act))
            c['violations'] += bad
            c['exact'] += lb == act
            c['positive'] += any(0 < a < float('inf') for a in act)
            if bad and example is None:
                example = dict(state=n['state'], points=pts, bound=list(zip(caps, lb)))
        print(json.dumps(dict(case=case, **c, violation_example=example)), flush=True)


def lifted(slots, child, alloc, extra, trips):
    lift = frontier((alloc + c, extra + trips * q) for c, q in child if q != float('inf'))
    caps = sorted({c for c, _ in slots} | {c for c, _ in lift})
    return frontier((c, max(traffic_at(c, slots), traffic_at(c, lift))) for c in caps)


def c2(cases):
    """Ideal exclusions of proper retention choices: slot bound vs slot bound max op bound."""
    for case in cases:
        g = graph_of(case)
        nodes = {n['id']: n for n in json.load(gzip.open(R / case / 'baseline.json.gz', 'rt'))['nodes']}
        c = dict(proper=0, applicable=0, slots=0, op_bound=0, applicable_slots=0, applicable_op=0)
        for line in gzip.open(R / case / 'choices.jsonl.gz', 'rt'):
            r = json.loads(line)
            c['proper'] += 1
            par = frontier(nodes[r['parent']]['points'])
            slots = [tuple(p) for p in r['slots_bound']]
            s = dominates(par, slots)
            c['slots'] += s
            ops = chain_ops(g, nodes[r['child']]['state'])
            if ops is None:
                c['op_bound'] += s
                continue
            trips = nodes[r['parent']]['state']['ext'][sorted(g.sizes).index(r['axis'])] // r['tile']
            top = max(cc for cc, _ in r['actual']) - r['allocation'] + 3
            child = [(C, bound(ops, C)) for C in range(top)]
            b = lifted(slots, child, r['allocation'], r['extra'], trips)
            assert dominates(b, [tuple(p) for p in r['actual']]), (case, r['child'])
            e = dominates(par, b)
            c['applicable'] += 1
            c['applicable_slots'] += s
            c['applicable_op'] += e
            c['op_bound'] += e
        print(json.dumps(dict(case=case, **c)), flush=True)


if __name__ == '__main__':
    {'check': check, 'c2': c2}[sys.argv[1]](sys.argv[2:])
