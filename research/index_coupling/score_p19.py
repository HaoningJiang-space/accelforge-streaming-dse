"""Score P19 (PROTOCOL.md) from run_p19 output.

Usage: python -m research.index_coupling.score_p19 results/p19.jsonl
"""
import json
import sys
from math import ceil

from research.index_coupling.analyze_p18_profile import capacity
from research.index_coupling.run_p19 import ROLES, shapes

PURE = 'kkkkkk'


def gaps(pure, mixed, q_hi):
    # Exact step-interval walk on [0, q_hi]: (max gap, min-gap check data, positive width).
    qs = sorted({t - p[-1][1] for p in (pure, mixed) for _, t in p} | {0, q_hi})
    rows = [(lo, hi, capacity(mixed, lo) - capacity(pure, lo)) for lo, hi in zip(qs, qs[1:])]
    return rows, max(g for *_, g in rows), sum(hi - lo for lo, hi, g in rows if g > 0)


if __name__ == '__main__':
    curves = {}
    for line in open(sys.argv[1]):
        r = json.loads(line)
        key = (tuple(r['shape']), r['roles'])
        assert key not in curves, key
        curves[key] = r['points']
    expected = {(tuple(s), r) for s in shapes() for r in ROLES}
    print('records', len(curves), 'missing', sorted(expected - set(curves)))
    a_exact = a_strict = a_strict_n = 0
    b_ok = {'kkkkki': 0, 'kkkkii': 0}
    c_ok = d_ok = d_n = 0
    for shape in shapes():
        n, _, _, l = shape
        cv = {r: curves.get((tuple(shape), r)) for r in ROLES}
        if None in cv.values():
            continue
        q_hi = max(t - p[-1][1] for p in cv.values() for _, t in p)
        res = {r: gaps(cv[PURE], cv[r], q_hi) for r in ROLES[1:]}
        mx = {r: res[r][1] for r in res}
        width = {r: res[r][2] for r in res}
        pred = {r: n * min(ceil(b / 2) * l, n // 2) for r, b in (('kkkkki', 1), ('kkkkii', 2), ('kkkiii', 3))}
        a_exact += mx['kkkiii'] == pred['kkkiii']
        if l <= n // 4:
            a_strict_n += 1
            a_strict += mx['kkkiii'] > mx['kkkkii']
        for r in b_ok:
            b_ok[r] += mx[r] == pred[r]
        c_ok += width['kkkkki'] < width['kkkkii'] < width['kkkiii']
        for r, b in (('kkkkki', 1), ('kkkkii', 2), ('kkkiii', 3)):
            d_n += 1
            d_ok += all(-b * n * l <= g <= b * n * l for *_, g in res[r][0])
        print(shape, 'max', mx, 'pred', pred, 'positive width', width, 'q_hi', q_hi)
    print(f'P19a exact {a_exact}/8 (need 7), strictly above kkkkii {a_strict}/{a_strict_n} (need all 6)')
    print(f'P19b {b_ok} (need 7 each)')
    print(f'P19c ordered widths {c_ok}/8 (need 7)')
    print(f'P19d bound {d_ok}/{d_n}')
