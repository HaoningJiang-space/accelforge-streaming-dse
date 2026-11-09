"""Witnesses at the maximum capacity gap between a pure and a mixed-role fork.

Usage: python -m research.index_coupling.fork_witness I J K L pure mixed
Prints, at the smallest extra-traffic target q attaining max dS, the witness of
the least-capacity point reaching q for each graph.
"""
import sys

from research.index_coupling.curve_model import curve
from research.index_coupling.nest_model import fork
from research.index_coupling.sweep_analysis import delta


def at_q(points, q):
    base = points[-1][1]
    return min((p for p in points if p[1] - base <= q), key=lambda p: p[0])


if __name__ == '__main__':
    *shape, pure, mixed = sys.argv[1:]
    shape = tuple(map(int, shape))
    curves = {r: curve(fork(*shape, r), witness=True) for r in (pure, mixed)}
    ds = delta([p[:2] for p in curves[pure]], [p[:2] for p in curves[mixed]])
    q, gap, _ = max(ds, key=lambda r: (r[1], -r[0]))
    print('shape', shape, 'max dS', gap, 'at q', q)
    for r in (pure, mixed):
        c, t, w = at_q(curves[r], q)
        print(f'--- {r}: capacity {c} traffic {t}')
        for note in w:
            print('   ', note)
