"""Keep-level model of one matmul's grammar response at M > 1 (CONTRACTION_ORACLE.md §12).

Y[M,F] += X[M,D] W[D,F]. Each tensor lacks one rank (X: F, W: M, Y: D).
Along a loop nest the current tiles c = (c_M, c_D, c_F) only shrink. A live
tensor T is either
- kept at a loop over its lacking rank r, at tiles c with c_r > 1: it then
  holds prod of its own tiles cells, and was re-fetched E_r / c_r - 1 times;
- or never kept: it ends scalar at the leaf (1 cell), re-fetched E_r / c_r - 1
  times with c the leaf tiles.
Peak cells add over tensors. Keeps happen in some order; after T is kept the
next state has a smaller r tile (the keeping loop). Extra traffic weights Y
by 2 (spill) and inputs by 1. `predict` minimises over orders and states.

Usage: python -m research.index_coupling.matmul_keep freeze OUT.json
       python -m research.index_coupling.matmul_keep check PRED.json OUT.jsonl
"""
from functools import lru_cache
from itertools import permutations, product
import json
import sys

from research.index_coupling.contraction_oracle import reachable_tiles
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph

RANKS = ('M', 'D', 'F')
OWN = dict(X=(0, 1), W=(1, 2), Y=(0, 2))
LACK = dict(X=2, W=0, Y=1)
WEIGHT = dict(X=1, W=1, Y=2)
INF = float('inf')


def predict(ext, live, capacity, dom):
    live = tuple(sorted(live))
    size = {t: ext[OWN[t][0]] * ext[OWN[t][1]] for t in live}
    tiles = [sorted(reachable_tiles(e, dom)) for e in ext]

    def below(c, need):
        """States reachable from c; the `need` rank must shrink."""
        for s in product(*(tiles[i] for i in range(3))):
            if all(s[i] <= c[i] and c[i] % s[i] == 0 and s[i] in reachable_tiles(c[i], dom) for i in range(3)):
                if need is None or s[need] < c[need]:
                    yield s

    def cost(t, c):
        r = LACK[t]
        return WEIGHT[t] * size[t] * (ext[r] // c[r] - 1)

    @lru_cache(maxsize=None)
    def rest(order, leaf, c, need, budget):
        if not order:
            if not leaf:
                return 0
            if budget < len(leaf):
                return INF
            best = INF
            for s in below(c, need):
                if all(s[i] == 1 for t in leaf for i in OWN[t]):
                    best = min(best, sum(cost(t, s) for t in leaf))
            return best
        t, best = order[0], INF
        for s in below(c, need):
            r = LACK[t]
            cells = s[OWN[t][0]] * s[OWN[t][1]]
            if s[r] == 1 or cells > budget:
                continue
            best = min(best, cost(t, s) + rest(order[1:], leaf, s, r, budget - cells))
        return best

    best = INF
    for k in range(len(live) + 1):
        for order in permutations(live, k):
            leaf = tuple(t for t in live if t not in order)
            # The first state may equal ext: nothing before the first keep.
            best = min(best, rest(order, leaf, tuple(ext), None, capacity))
    return best


def grammar_curve(ext, live, dom):
    m, a, b = ext
    g = Graph(dict(M=m, D=a, F=b), [('E', {'X': ('M', 'D'), 'W': ('D', 'F'), 'Y': ('M', 'F')})])
    external = frozenset({'X', 'W', 'Y'} - set(live))
    points = curve(g, partitions='dp', external=external, scalar_leaf='v2', tile_domain=dom)
    compulsory = sum(m * a if t == 'X' else a * b if t == 'W' else m * b for t in live)
    return points, compulsory


SHAPES = [(2, 2, 2), (4, 2, 4), (4, 4, 2), (2, 8, 4), (8, 4, 8), (6, 3, 4), (8, 2, 2)]
LIVE = [('W', 'X', 'Y'), ('X', 'Y'), ('W', 'Y'), ('W', 'X')]


def main(argv):
    if argv[0] == 'freeze':
        rows = []
        for ext in SHAPES:
            m, a, b = ext
            top = m * a + a * b + m * b + 2
            for live in LIVE:
                for dom in ('halving', 'divisors'):
                    for cap in range(1, top + 1):
                        rows.append(dict(ext=ext, live=live, tile_domain=dom, C=cap,
                                         predict=predict(ext, live, cap, dom)))
        json.dump(rows, open(argv[1], 'w'), indent=0)
        print(len(rows))
        return
    rows, curves = json.load(open(argv[1])), {}
    with open(argv[2], 'w') as out:
        for r in rows:
            key = (tuple(r['ext']), tuple(r['live']), r['tile_domain'])
            if key not in curves:
                curves[key] = grammar_curve(*key)
            points, compulsory = curves[key]
            r['grammar'] = traffic_at(r['C'], points) - compulsory
            out.write(json.dumps(r) + '\n')
            if r['grammar'] != r['predict']:
                print('MISMATCH', json.dumps(r), flush=True)
    print(json.dumps(dict(cases=len(rows), mismatches=sum(r['grammar'] != r['predict'] for r in rows))))


if __name__ == '__main__':
    main(sys.argv[1:])
