"""Closed-form grammar response of contraction chains (CONTRACTION_ORACLE.md §8-9).

x[D=a] -E0(W0[D,F])-> h[F=b] -E1(W1[F,G])-> z[G=c], weights resident.
`predict` is the paper derivation; `grammar` is curve() under grammar v2.
Both return extra traffic above the compulsory a + c.

`chain_predict` extends it to unit-M chains V_0 -> ... -> V_m by a DP over
boundaries, with one- and two-contraction segments (§9).

Usage: python -m research.index_coupling.chain2_closed_form freeze OUT.json
       python -m research.index_coupling.chain2_closed_form check PRED.json OUT.jsonl
       python -m research.index_coupling.chain2_closed_form chain-freeze OUT.json
       python -m research.index_coupling.chain2_closed_form chain-check PRED.json OUT.jsonl
"""
import json
import sys

from research.index_coupling.contraction_oracle import loop_nest, reachable_tiles
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph

SIZES = [(2, 4, 3), (4, 4, 4), (3, 6, 2), (6, 4, 6), (4, 8, 4), (8, 6, 3), (2, 6, 8), (5, 4, 5),
         (6, 12, 4), (9, 6, 9)]


def predict(a, b, c, capacity, tile_domain):
    options = [2 * b + loop_nest(a, b, capacity, tile_domain) + loop_nest(b, c, capacity, tile_domain)]
    for u in reachable_tiles(b, tile_domain):  # fused F loop; u = b is h held whole
        trips = b // u
        for cells, extra in ((u + 1, (trips - 1) * (a + 2 * c)),  # refetch x, spill z
                             (c + u + 1, (trips - 1) * a),         # keep z
                             (a + u + 1, 2 * (trips - 1) * c),     # keep x
                             (a + c + u, 0)):                      # keep both
            if capacity >= cells:
                options.append(extra)
    return min(options)


def grammar_curve(a, b, c, tile_domain):
    g = Graph(dict(D=a, F=b, G=c), [('E0', {'x': ('D',), 'W0': ('D', 'F'), 'h': ('F',)}),
                                    ('E1', {'h': ('F',), 'W1': ('F', 'G'), 'z': ('G',)})])
    return curve(g, partitions='dp', external=frozenset({'W0', 'W1'}), scalar_leaf='v2',
                 tile_domain=tile_domain)


def single(p, q, cells, resident_in, resident_out, tile_domain):
    """One contraction p -> q; a resident boundary is held by the caller."""
    if resident_in or resident_out:
        return 0 if cells >= 1 - (resident_in and resident_out) else float('inf')
    return loop_nest(p, q, cells, tile_domain)


def pair(a, b, c, cells, resident_in, resident_out, tile_domain):
    """Two contractions a -> b -> c fused under their only common rank F."""
    best = float('inf')
    for u in reachable_tiles(b, tile_domain):
        trips = b // u
        if resident_in and resident_out:
            options = ((u, 0),)
        elif resident_in:
            options = ((u + 1, 2 * (trips - 1) * c), (c + u, 0))
        elif resident_out:
            options = ((u + 1, (trips - 1) * a), (a + u, 0))
        else:
            options = ((u + 1, (trips - 1) * (a + 2 * c)), (c + u + 1, (trips - 1) * a),
                       (a + u + 1, 2 * (trips - 1) * c), (a + c + u, 0))
        best = min([best] + [extra for need, extra in options if cells >= need])
    return best


def chain_predict(sizes, capacity, tile_domain):
    """DP over boundaries V_1..V_{m-1}: each kept (cells in both neighbours) or via DRAM (2 n)."""
    m = len(sizes) - 1
    best = {(0, False): 0}  # (boundary index, kept) -> least traffic of the prefix
    for j in range(m):
        for kept_j in (False, True):
            if (j, kept_j) not in best:
                continue
            for length in (1, 2):
                k = j + length
                if k > m:
                    continue
                for kept_k in ((False,) if k == m else (False, True)):
                    cells = capacity - sizes[j] * kept_j - sizes[k] * kept_k
                    if length == 1:
                        cost = single(sizes[j], sizes[k], cells, kept_j, kept_k, tile_domain)
                    else:
                        cost = pair(sizes[j], sizes[j + 1], sizes[k], cells, kept_j, kept_k, tile_domain)
                    cost += 0 if kept_k or k == m else 2 * sizes[k]
                    total = best[j, kept_j] + cost
                    if total < best.get((k, kept_k), float('inf')):
                        best[k, kept_k] = total
    return best.get((m, False), float('inf'))


def chain_graph(sizes):
    ranks = [f'R{j}' for j in range(len(sizes))]
    ops = [(f'E{j}', {f'V{j}': (ranks[j],), f'W{j}': (ranks[j], ranks[j + 1]), f'V{j + 1}': (ranks[j + 1],)})
           for j in range(len(sizes) - 1)]
    return Graph(dict(zip(ranks, sizes)), ops), frozenset(f'W{j}' for j in range(len(sizes) - 1))


CHAINS = [(2, 3, 2, 4), (4, 2, 4, 2), (3, 6, 2, 4), (4, 4, 4, 4), (2, 4, 8, 4, 2), (6, 3, 6, 3, 6),
          (4, 8, 2, 8, 4), (3, 3, 3, 3, 3), (8, 4, 2, 4, 8), (2, 6, 4, 6, 2, 6)]


def chain_cases():
    for sizes in CHAINS:
        for cap in range(1, 2 * max(sizes) + 3):
            for dom in ('halving', 'divisors'):
                yield sizes, cap, dom


def chain_main(argv):
    if argv[0] == 'chain-freeze':
        rows = [dict(sizes=s, C=cap, tile_domain=dom, predict=chain_predict(s, cap, dom))
                for s, cap, dom in chain_cases()]
        json.dump(rows, open(argv[1], 'w'), indent=0)
        print(len(rows))
        return
    rows, curves = json.load(open(argv[1])), {}
    with open(argv[2], 'w') as out:
        for r in rows:
            key = (tuple(r['sizes']), r['tile_domain'])
            if key not in curves:
                g, external = chain_graph(key[0])
                curves[key] = curve(g, partitions='dp', external=external, scalar_leaf='v2', tile_domain=key[1])
            r['grammar'] = traffic_at(r['C'], curves[key]) - (key[0][0] + key[0][-1])
            out.write(json.dumps(r) + '\n')
            if r['grammar'] != r['predict']:
                print('MISMATCH', json.dumps(r), flush=True)
    print(json.dumps(dict(cases=len(rows), mismatches=sum(r['grammar'] != r['predict'] for r in rows))))


def cases():
    for a, b, c in SIZES:
        for cap in range(2, b + 3):
            for dom in ('halving', 'divisors'):
                yield a, b, c, cap, dom


def main(argv):
    if argv[0].startswith('chain-'):
        return chain_main(argv)
    if argv[0] == 'freeze':
        rows = [dict(a=a, b=b, c=c, C=cap, tile_domain=dom, predict=predict(a, b, c, cap, dom))
                for a, b, c, cap, dom in cases()]
        json.dump(rows, open(argv[1], 'w'), indent=0)
        print(len(rows))
        return
    rows, curves = json.load(open(argv[1])), {}
    with open(argv[2], 'w') as out:
        for r in rows:
            key = (r['a'], r['b'], r['c'], r['tile_domain'])
            if key not in curves:
                curves[key] = grammar_curve(*key)
            r['grammar'] = traffic_at(r['C'], curves[key]) - (r['a'] + r['c'])
            out.write(json.dumps(r) + '\n')
            if r['grammar'] != r['predict']:
                print('MISMATCH', json.dumps(r), flush=True)
    print(json.dumps(dict(cases=len(rows), mismatches=sum(r['grammar'] != r['predict'] for r in rows))))


if __name__ == '__main__':
    main(sys.argv[1:])
