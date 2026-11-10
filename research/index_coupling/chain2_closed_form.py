"""Closed-form grammar response of a two-contraction chain (CONTRACTION_ORACLE.md §8).

x[D=a] -E0(W0[D,F])-> h[F=b] -E1(W1[F,G])-> z[G=c], weights resident.
`predict` is the paper derivation; `grammar` is curve() under grammar v2.
Both return extra traffic above the compulsory a + c.

Usage: python -m research.index_coupling.chain2_closed_form freeze OUT.json
       python -m research.index_coupling.chain2_closed_form check PRED.json OUT.jsonl
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


def cases():
    for a, b, c in SIZES:
        for cap in range(2, b + 3):
            for dom in ('halving', 'divisors'):
                yield a, b, c, cap, dom


def main(argv):
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
