"""Closed-form grammar response of unit-M chains with elementwise operators (CONTRACTION_ORACLE.md §10).

A chain is vectors V_0..V_m and ops c (dense contraction, resident weight) or
e (elementwise, same rank on both sides). A run of ops can form a looped
grammar group only if its ops share a rank. `predict` is a DP over group
boundaries, as in chain2_closed_form.chain_predict, with the paper-derived
forms for the group patterns c, e, cc, ce, ec and cec.
Weights are resident; streamed weights are not covered.

Usage: python -m research.index_coupling.elementwise_chain freeze OUT.json
       python -m research.index_coupling.elementwise_chain check PRED.json OUT.jsonl
"""
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


def ce(a, f, cells, res_in, res_out, dom):
    """X[a] -c-> H[f] -e-> Z[f], fused under F."""
    s_out = int(not res_out)
    best = INF
    for u in reachable_tiles(f, dom):
        options = [(u + s_out, 0)] if res_in else [(a + u + s_out, 0), (u + 1, a * (f // u - 1))]
        best = min([best] + [x for need, x in options if cells >= need])
    return best


def ec(f, c, cells, res_in, res_out, dom):
    """H[f] -e-> Z[f] -c-> X'[c], fused under F."""
    s_in = int(not res_in)
    best = INF
    for u in reachable_tiles(f, dom):
        options = [(u + s_in, 0)] if res_out else [(c + u + s_in, 0), (u + 1, 2 * c * (f // u - 1))]
        best = min([best] + [x for need, x in options if cells >= need])
    return best


def cec(a, f, c, cells, res_in, res_out, dom):
    """X[a] -c-> H[f] -e-> Z[f] -c-> X'[c], fused under F, at most two loop levels.

    Level 1 tile u keeps or re-fetches x and z (resident ends are neither).
    Level 2 either splits all three ops (H, Z tiles u) or splits off one
    contraction with its intermediate kept at u and loops the other pair
    {c, e} with tile u' < u, where that side's end may be kept at level 2.
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
                options = [(base + max(2 * u, u + sx, u + sz), fx + fz)]  # split all
                for v in reachable_tiles(u, dom) - {u}:
                    tt = f // v
                    # Left: {c, e} loops v, Z kept at u; x may be kept at level 2.
                    options.append((base + max(u + v + sx, u + sz), a * (tt - 1) * sx + fz))
                    if sx:
                        options.append((base + max(u + v + a, u + sz), fx + fz))
                    # Right: {e, c} loops v, H kept at u; z may be kept at level 2.
                    options.append((base + max(u + sx, u + v + sz), fx + 2 * c * (tt - 1) * sz))
                    if sz:
                        options.append((base + max(u + sx, u + v + c), fx + fz))
                best = min([best] + [x for need, x in options if cells >= need])
    return best


def group(pattern, sizes, cells, res_in, res_out, dom):
    if pattern == 'c':
        return single(sizes[0], sizes[1], cells, res_in, res_out, dom)
    if pattern == 'e':
        return 0 if cells >= (not res_in) + (not res_out) else INF
    if pattern == 'cc':
        return pair(*sizes, cells, res_in, res_out, dom)
    if pattern == 'ce':
        return ce(sizes[0], sizes[1], cells, res_in, res_out, dom)
    if pattern == 'ec':
        return ec(sizes[0], sizes[2], cells, res_in, res_out, dom)
    if pattern == 'cec':
        return cec(sizes[0], sizes[1], sizes[3], cells, res_in, res_out, dom)
    raise ValueError(f'no form for group pattern {pattern}')


def predict(kinds, sizes, capacity, dom):
    m, rank = len(kinds), ranks(kinds)
    best = {(0, False): 0}
    for j in range(m):
        for kept_j in (False, True):
            if (j, kept_j) not in best:
                continue
            for k in range(j + 1, m + 1):
                if not loopable(kinds, rank, j, k):
                    break
                for kept_k in ((False,) if k == m else (False, True)):
                    cells = capacity - sizes[j] * kept_j - sizes[k] * kept_k
                    cost = group(''.join(kinds[j:k]), sizes[j:k + 1], cells, kept_j, kept_k, dom)
                    cost += 0 if kept_k or k == m else 2 * sizes[k]
                    if best[j, kept_j] + cost < best.get((k, kept_k), INF):
                        best[k, kept_k] = best[j, kept_j] + cost
    return best.get((m, False), INF)


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


def main(argv):
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
