"""Sandwich certificate for chain solve states (SANDWICH_PROTOCOL.md).

LB = operator-projection bound (sum of single-op keep-level optima).
UB = singleton partition with every interior vector kept or via DRAM, each
group priced by its single-op response at that residency. Where UB = LB at
every capacity, the state's response is certified without search.

Usage: python -m research.index_coupling.sandwich CASE [CASE ...]
"""
from functools import lru_cache
import gzip
import json
from pathlib import Path
import sys

from research.index_coupling.c2_bound_audit import COUNTERS, reachable
from research.index_coupling.census_tools import graph_of
from research.index_coupling.elementwise_chain import KIND, archived_chain
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import pareto
from research.index_coupling.matmul_keep import predict as keep_level

R = Path(__file__).resolve().parent / 'results/c2_bound'
DOMAIN = 'halving'  # run_c2_bound_audit.py
INF = float('inf')


@lru_cache(maxsize=None)
def op_curve(ext, live):
    """Frontier of one contraction (M, D_in, D_out) with the given live tensors."""
    m, a, b = ext
    sizes = dict(X=m * a, W=a * b, Y=m * b)
    top = sum(sizes[t] for t in live) + 3
    points = []
    for c in range(top + 1):
        q = keep_level(ext, live, c, DOMAIN)
        if q != INF:
            points.append((c, q))
            if q == 0:
                break
    return pareto(points)


def chain(graph, state):
    """Per-op records of a qualifying chain solve state, else None."""
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
    size = lambda t: eval_size(graph, t, ext)
    records = []
    for j, op in enumerate(ops):
        x, y = vectors[j], vectors[j + 1]
        if KIND[op.rstrip('0123456789').rstrip('_')] == 'e':
            records.append(('e', None, None))
            continue
        (w,) = [t for t in graph.access[op] if 'M' not in graph.access[op][t]]
        d_in = [v for v in graph.dims(x) if v != 'M'][0]
        d_out = [v for v in graph.dims(y) if v != 'M'][0]
        records.append(('c', (ext['M'], ext[d_in], ext[d_out]), w not in external))
    return dict(records=records, sizes=[size(v) for v in vectors],
                first=vectors[0] in external, last=vectors[-1] in external)


def eval_size(graph, t, ext):
    out = 1
    for v in graph.dims(t):
        out *= ext[v]
    return out


def group_cost(record, cells, res_in, res_out):
    kind, ext, w_live = record
    if kind == 'e':
        return 0 if cells >= (not res_in) + (not res_out) else INF
    live = tuple(t for t, on in (('W', w_live), ('X', not res_in), ('Y', not res_out)) if on)
    return traffic_at(cells, op_curve(ext, tuple(sorted(live)))) if cells >= 0 else INF


def lower(c, info):
    total = 0
    for k, (kind, ext, w_live) in enumerate(info['records']):
        if kind == 'c':
            res_in = k == 0 and info['first']
            res_out = k == len(info['records']) - 1 and info['last']
            total += group_cost((kind, ext, w_live), c, res_in, res_out)
    return total


def upper(c, info):
    recs, sizes, n = info['records'], info['sizes'], len(info['records'])
    best = {info['first']: 0}  # kept/resident flag of V_j -> least traffic so far
    for j in range(n):
        nxt = {}
        for kept_in, cost in best.items():
            for kept_out in ((info['last'],) if j == n - 1 else (False, True)):
                cells = c - sizes[j] * (kept_in and j > 0) - sizes[j + 1] * (kept_out and j < n - 1)
                total = cost + group_cost(recs[j], cells, kept_in, kept_out)
                total += 0 if kept_out or j == n - 1 else 2 * sizes[j + 1]
                if total < nxt.get(kept_out, INF):
                    nxt[kept_out] = total
        best = nxt
    return best.get(info['last'], INF)


def main(cases):
    for case in cases:
        g = graph_of(case)
        names = sorted(g.sizes)
        data = json.load(gzip.open(R / case / 'baseline.json.gz', 'rt'))
        nodes = {n['id']: n for n in data['nodes']}
        c = dict(qualifying=0, multi_row=0, lb_violations=0, ub_violations=0, certified=0,
                 certified_multi_row=0, certified_inexact=0,
                 uncertified_multi_row=dict(ub_gap_only=0, lb_gap_only=0, both=0))
        certified, unit = set(), set()
        example = None
        for i, n in nodes.items():
            s = n['state']
            if archived_chain(g, s) is not None:
                unit.add(i)
            info = chain(g, s)
            if info is None:
                continue
            multi = s['ext'][names.index('M')] > 1
            c['qualifying'] += 1
            c['multi_row'] += multi
            pts = n['points']
            caps = range(0, max(cc for cc, _ in pts) + 3)
            act = [traffic_at(cc, pts) for cc in caps]
            lb = [lower(cc, info) for cc in caps]
            ub = [upper(cc, info) for cc in caps]
            lo_bad = any(l > a for l, a in zip(lb, act))
            up_bad = any(u < a for u, a in zip(ub, act))
            c['lb_violations'] += lo_bad
            c['ub_violations'] += up_bad
            if (lo_bad or up_bad) and example is None:
                example = dict(state=s, actual=pts, lb=lb, ub=ub)
            if lb == ub:
                c['certified'] += 1
                c['certified_multi_row'] += multi
                c['certified_inexact'] += lb != act
                certified.add(i)
            elif multi:
                ug, lg = ub != act, lb != act
                key = 'both' if ug and lg else 'ub_gap_only' if ug else 'lb_gap_only'
                c['uncertified_multi_row'][key] += 1
        total = {k: sum(n['work'][k] for n in nodes.values()) for k in COUNTERS}
        out = dict(case=case, **c)
        for label, terminal in (('unit_only', unit), ('certified_only', certified), ('union', unit | certified)):
            keep, stack = set(), [data['root']]
            children = {}
            for e in data['edges']:
                children.setdefault(e['parent'], []).append(e['child'])
            while stack:
                i = stack.pop()
                if i in keep:
                    continue
                keep.add(i)
                if i not in terminal:
                    stack.extend(children.get(i, ()))
            left = keep - terminal
            out[label] = {k: round(1 - sum(nodes[i]['work'][k] for i in left) / total[k], 4) if total[k] else None
                          for k in COUNTERS}
        out['example'] = example
        print(json.dumps(out), flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
