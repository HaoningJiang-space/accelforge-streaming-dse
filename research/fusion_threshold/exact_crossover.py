"""Exact check of the fusion threshold law on a two-GEMM chain.

Y[M,P] = (X[M,K] W1[K,N]) W2[N,P]. 'split' forces the intermediate H[M,N] through
DRAM (root groups E1 | E2 with nothing kept); 'full' is the exact v2 frontier,
which may keep H on chip. C* is the least capacity at which full traffic is
strictly below split traffic. Closed-form prediction (asymptotic, see README):
C* ~ 0.134 (K + P)^2, independent of M and N.
"""
import itertools
import json
import resource
import sys

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph

OPTIONS = dict(partitions='dp', scalar_leaf='v2', tile_domain='halving')


def chain(m, k, n, p):
    return Graph(dict(M=m, K=k, N=n, P=p),
                 [('E1', {'X': ('M', 'K'), 'W1': ('K', 'N'), 'H': ('M', 'N')}),
                  ('E2', {'H': ('M', 'N'), 'W2': ('N', 'P'), 'Y': ('M', 'P')})])


def best(points, c):
    return min((q for cc, q in points if cc <= c), default=float('inf'))


def main():
    resource.setrlimit(resource.RLIMIT_AS, (8 * 2**30, 8 * 2**30))
    for m, n, d in itertools.product([16, 64], [4, 16, 64], [2, 4, 8, 16, 32]):
        g = chain(m, d, n, d)
        full = [p[:2] for p in curve(g, **OPTIONS)]
        split = [p[:2] for p in curve(g, root_groups=(('E1',), ('E2',)), root_kept=(), **OPTIONS)]
        caps = sorted({c for c, _ in full} | {c for c, _ in split})
        wins = [c for c in caps if best(full, c) < best(split, c)]
        win5 = [c for c in caps if best(full, c) < 0.95 * best(split, c)]
        top = max(caps)
        print(json.dumps(dict(M=m, N=n, d=d, c_star=wins[0] if wins else None,
                              c_star_5pct=win5[0] if win5 else None,
                              pred=round(0.134 * (2 * d) ** 2, 1),
                              ratio_at_top=round(best(split, top) / best(full, top), 3))), flush=True)


if __name__ == '__main__':
    if sys.platform != 'linux':
        raise SystemExit('run on the Linux server with caps')
    main()
