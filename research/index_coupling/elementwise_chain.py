"""Closed-form grammar response of unit-M chains with elementwise operators (CONTRACTION_ORACLE.md §10).

A chain is vectors V_0..V_m and ops c (dense contraction, resident weight) or
e (elementwise, same rank on both sides). A run of ops can form a looped
grammar group only if its ops share a rank. `predict` is a DP over group
boundaries, as in chain2_closed_form.chain_predict, with the paper-derived
forms for the group patterns c, e, cc, ce, ec and cec.
Weights are resident; streamed weights are not covered.

Usage: python -m research.index_coupling.elementwise_chain freeze OUT.json
       python -m research.index_coupling.elementwise_chain check PRED.json OUT.jsonl
       python -m research.index_coupling.elementwise_chain archive CASE [CASE ...]
       python -m research.index_coupling.elementwise_chain wfreeze OUT.json
       python -m research.index_coupling.elementwise_chain wcheck PRED.json OUT.jsonl
"""
from functools import lru_cache
import json
import sys

from research.index_coupling.chain2_closed_form import pair, single
from research.index_coupling.contraction_oracle import reachable_tiles
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.stacks import attention_stack, ffn_stack

INF = float('inf')


def ranks(kinds):
    rank = [0]
    for k in kinds:
        rank.append(rank[-1] if k == 'e' else rank[-1] + 1)
    return rank


def loopable(kinds, rank, j, k):
    common = None
    for i in range(j, k):
        own = {rank[i], rank[i + 1]}
        common = own if common is None else common & own
    return bool(common)


def ce(a, f, cells, res_in, res_out, dom, w=0):
    """X[a] -c-> H[f] -e-> Z[f], fused under F; w is the contraction's streamed weight."""
    s_out = int(not res_out)
    best = INF
    for u in reachable_tiles(f, dom):
        options = ([(u + max(w, s_out), 0)] if res_in else
                   [(a + u + max(w, s_out), 0), (u + max(1 + w, s_out), a * (f // u - 1))])
        best = min([best] + [x for need, x in options if cells >= need])
    return best


def ec(f, c, cells, res_in, res_out, dom, w=0):
    """H[f] -e-> Z[f] -c-> X'[c], fused under F; w is the contraction's streamed weight."""
    s_in = int(not res_in)
    best = INF
    for u in reachable_tiles(f, dom):
        options = ([(u + max(s_in, w), 0)] if res_out else
                   [(c + u + max(s_in, w), 0), (u + max(s_in, 1 + w), 2 * c * (f // u - 1))])
        best = min([best] + [x for need, x in options if cells >= need])
    return best


def cec(a, f, c, cells, res_in, res_out, dom, w1=0, w2=0):
    """X[a] -c-> H[f] -e-> Z[f] -c-> X'[c], fused under F, at most two loop levels.

    Level 1 tile u keeps or re-fetches x and z (resident ends are neither).
    Level 2 either splits all three ops (H, Z tiles u) or splits off one
    contraction with its intermediate kept at u and loops the other pair
    {c, e} with tile u' < u, where that side's end may be kept at level 2.
    Each contraction's peak adds its streamed weight cell (w1, w2).
    """
    best = INF
    x_live, z_live = not res_in, not res_out
    for u in reachable_tiles(f, dom):
        t = f // u
        for kx1 in ((False, True) if x_live else (False,)):
            for kz1 in ((False, True) if z_live else (False,)):
                base = a * kx1 + c * kz1
                sx = int(x_live and not kx1)  # x streamed below level 1
                sz = int(z_live and not kz1)
                fx = a * (t - 1) * sx         # x re-fetched per level-1 trip
                fz = 2 * c * (t - 1) * sz
                options = [(base + max(2 * u, u + sx + w1, u + sz + w2), fx + fz)]  # split all
                for v in reachable_tiles(u, dom) - {u}:
                    tt = f // v
                    # Left: {c, e} loops v, Z kept at u; x may be kept at level 2.
                    options.append((base + max(u + v + sx + w1, u + v, u + sz + w2), a * (tt - 1) * sx + fz))
                    if sx:
                        options.append((base + max(u + v + a + w1, u + v, u + sz + w2), fx + fz))
                    # Right: {e, c} loops v, H kept at u; z may be kept at level 2.
                    options.append((base + max(u + sx + w1, u + v, u + v + sz + w2), fx + 2 * c * (tt - 1) * sz))
                    if sz:
                        options.append((base + max(u + sx + w1, u + v, u + v + c + w2), fx + fz))
                best = min([best] + [x for need, x in options if cells >= need])
    return best


@lru_cache(maxsize=None)
def _group(pattern, sizes, cells, res_in, res_out, dom, ws):
    return group(pattern, sizes, cells, res_in, res_out, dom, ws)


def group(pattern, sizes, cells, res_in, res_out, dom, ws=None):
    """ws: per-op streamed-weight flags (0 for elementwise ops)."""
    ws = [w for w, k in zip(ws or [0] * len(pattern), pattern) if k == 'c']
    if pattern == 'c':
        return single(sizes[0], sizes[1], cells, res_in, res_out, dom, *ws)
    if pattern == 'e':
        return 0 if cells >= (not res_in) + (not res_out) else INF
    if pattern == 'cc':
        return pair(*sizes, cells, res_in, res_out, dom, *ws)
    if pattern == 'ce':
        return ce(sizes[0], sizes[1], cells, res_in, res_out, dom, *ws)
    if pattern == 'ec':
        return ec(sizes[0], sizes[2], cells, res_in, res_out, dom, *ws)
    if pattern == 'cec':
        return cec(sizes[0], sizes[1], sizes[3], cells, res_in, res_out, dom, *ws)
    raise ValueError(f'no form for group pattern {pattern}')


def predict(kinds, sizes, capacity, dom, resident_first=False, resident_last=False, streamed=None):
    """Resident ends are held by the caller: groups see them as resident, at no cell cost.

    streamed[i] = 1 if op i's weight is not resident (§11)."""
    streamed = streamed or [0] * len(kinds)
    m, rank = len(kinds), ranks(kinds)
    best = {(0, resident_first): 0}
    for j in range(m):
        for kept_j in (False, True):
            if (j, kept_j) not in best:
                continue
            for k in range(j + 1, m + 1):
                if not loopable(kinds, rank, j, k):
                    break
                for kept_k in (((resident_last,) if k == m else (False, True))):
                    cells = capacity - sizes[j] * (kept_j and j > 0) - sizes[k] * (kept_k and k < m)
                    cost = _group(''.join(kinds[j:k]), tuple(sizes[j:k + 1]), cells, kept_j, kept_k, dom,
                                  tuple(streamed[j:k]))
                    cost += 0 if kept_k or k == m else 2 * sizes[k]
                    if best[j, kept_j] + cost < best.get((k, kept_k), INF):
                        best[k, kept_k] = best[j, kept_j] + cost
    return best.get((m, resident_last), INF)


def stack(family, layers, d, f):
    if family == 'ffn':
        g = ffn_stack(layers, m=1, d=d, f=f)
    else:
        g = attention_stack(layers, m=1, p=f, d=d)
    external = frozenset(t for op in g.ops for t in g.access[op] if 'M' not in g.access[op][t])
    return g, external, ['c', 'e', 'c'] * layers, [d, f, f] * layers + [d]


STACKS = [('ffn', 1, 2, 2), ('ffn', 1, 2, 4), ('ffn', 1, 4, 2), ('ffn', 1, 3, 6), ('ffn', 1, 4, 8),
          ('ffn', 2, 2, 2), ('ffn', 2, 2, 4), ('ffn', 2, 4, 2), ('ffn', 2, 3, 6),
          ('ffn', 3, 2, 2), ('ffn', 3, 2, 4), ('attention', 2, 2, 4), ('attention', 2, 4, 2)]


W_STACKS = [('ffn', 1, 2, 2), ('ffn', 1, 2, 4), ('ffn', 1, 4, 2), ('ffn', 1, 3, 6),
            ('ffn', 2, 2, 4), ('ffn', 2, 4, 2), ('attention', 2, 2, 4)]


def weights_of(graph):
    return [t for op in graph.ops for t in graph.access[op] if 'M' not in graph.access[op][t]]


def wmain(argv):
    """Streamed-weight subsets: every subset of each W_STACKS entry (§11)."""
    if argv[0] == 'wfreeze':
        rows = []
        for family, layers, d, f in W_STACKS:
            g, _, kinds, sizes = stack(family, layers, d, f)
            weights = weights_of(g)
            for mask in range(1 << len(weights)):
                streamed_w = {w for i, w in enumerate(weights) if mask >> i & 1}
                flags = [int(any(t in streamed_w for t in g.access[op])) for op in g.ops]
                for cap in range(1, 2 * (d + f) + 5):
                    for dom in ('halving', 'divisors'):
                        rows.append(dict(family=family, layers=layers, d=d, f=f, streamed=sorted(streamed_w),
                                         C=cap, tile_domain=dom,
                                         predict=predict(kinds, sizes, cap, dom, streamed=flags)))
        json.dump(rows, open(argv[1], 'w'), indent=0)
        print(len(rows))
        return
    rows, curves = json.load(open(argv[1])), {}
    with open(argv[2], 'w') as out:
        for r in rows:
            key = (r['family'], r['layers'], r['d'], r['f'], tuple(r['streamed']), r['tile_domain'])
            if key not in curves:
                g, external, _, _ = stack(*key[:4])
                external = external - set(key[4])
                compulsory = 2 * r['d'] + sum(r['d'] * r['f'] for _ in key[4])
                points = curve(g, partitions='dp', external=external, scalar_leaf='v2', tile_domain=key[5])
                curves[key] = (points, compulsory)
            points, compulsory = curves[key]
            r['grammar'] = traffic_at(r['C'], points) - compulsory
            out.write(json.dumps(r) + '\n')
            if r['grammar'] != r['predict']:
                print('MISMATCH', json.dumps(r), flush=True)
    print(json.dumps(dict(cases=len(rows), mismatches=sum(r['grammar'] != r['predict'] for r in rows))))


KIND = dict(EH='c', EZ='e', EY='c', ES='c', ESoft='e', EO='c')


def archived_chain(graph, state):
    """(kinds, sizes, resident ends, streamed flags) of a qualifying archived solve node, else None."""
    if state['stage'] != 'solve' or state['constrained']:
        return None
    names, ops = sorted(graph.sizes), state['ops']
    ext = dict(zip(names, state['ext']))
    external, owned = set(state['external']), set(state['owned'])
    if ext['M'] != 1 or tuple(ops) != graph.ops[graph.ops.index(ops[0]):][:len(ops)]:
        return None
    vectors = [list(graph.access[ops[0]])[0]] + [graph.output(op) for op in ops]
    weights = {t for op in ops for t in graph.access[op] if 'M' not in graph.access[op][t]}
    if set(vectors[1:-1]) & (external | owned):
        return None
    streamed = [int(any(t in weights - external for t in graph.access[op])) for op in ops]
    kinds = [KIND[op.rstrip('0123456789').rstrip('_')] for op in ops]
    sizes = [1] * len(vectors)
    for i, t in enumerate(vectors):
        for v in graph.dims(t):
            sizes[i] *= ext[v]
    return kinds, sizes, vectors[0] in external, vectors[-1] in external, streamed


def archive(cases):
    import gzip
    from pathlib import Path
    from research.index_coupling.census_tools import graph_of
    here = Path(__file__).resolve().parent
    for case in cases:
        graph = graph_of(case)
        with gzip.open(here / 'results/c2_bound' / case / 'baseline.json.gz', 'rt') as stream:
            data = json.load(stream)
        dom = 'halving'  # run_c2_bound_audit.py
        counts = dict(nodes=len(data['nodes']), qualifying=0, exact=0, positive=0, streamed=0, streamed_exact=0)
        example = None
        for node in data['nodes']:
            chain = archived_chain(graph, node['state'])
            if chain is None:
                continue
            kinds, sizes, first, last, streamed = chain
            counts['qualifying'] += 1
            points = node['points']
            caps = range(0, max(c for c, _ in points) + 3)
            ok = all(predict(kinds, sizes, c, dom, first, last, streamed) == traffic_at(c, points) for c in caps)
            counts['exact'] += ok
            counts['streamed'] += any(streamed)
            counts['streamed_exact'] += ok and any(streamed)
            counts['positive'] += any(q > 0 for _, q in points)
            if not ok and example is None:
                example = dict(state=node['state'], points=points,
                               predict=[(c, predict(kinds, sizes, c, dom, first, last, streamed)) for c in caps])
        print(json.dumps(dict(case=case, **counts, mismatch_example=example)))


def main(argv):
    if argv[0] in ('wfreeze', 'wcheck'):
        return wmain(argv)
    if argv[0] == 'archive':
        return archive(argv[1:])
    if argv[0] == 'freeze':
        rows = []
        for family, layers, d, f in STACKS:
            _, _, kinds, sizes = stack(family, layers, d, f)
            for cap in range(1, 2 * (d + f) + 3):
                for dom in ('halving', 'divisors'):
                    rows.append(dict(family=family, layers=layers, d=d, f=f, C=cap, tile_domain=dom,
                                     predict=predict(kinds, sizes, cap, dom)))
        json.dump(rows, open(argv[1], 'w'), indent=0)
        print(len(rows))
        return
    rows, curves = json.load(open(argv[1])), {}
    with open(argv[2], 'w') as out:
        for r in rows:
            key = (r['family'], r['layers'], r['d'], r['f'], r['tile_domain'])
            if key not in curves:
                g, external, _, _ = stack(*key[:4])
                curves[key] = curve(g, partitions='dp', external=external, scalar_leaf='v2', tile_domain=key[4])
            r['grammar'] = traffic_at(r['C'], curves[key]) - 2 * r['d']
            out.write(json.dumps(r) + '\n')
            if r['grammar'] != r['predict']:
                print('MISMATCH', json.dumps(r), flush=True)
    print(json.dumps(dict(cases=len(rows), mismatches=sum(r['grammar'] != r['predict'] for r in rows))))


if __name__ == '__main__':
    main(sys.argv[1:])
