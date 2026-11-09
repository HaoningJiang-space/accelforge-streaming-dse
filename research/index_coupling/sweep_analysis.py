"""Analyze coupling_sweep output: capacity needed for an extra-traffic target.

Same and cross coupling have different compulsory traffic when shapes are not
square (V is I x L versus L x K), so targets are extra traffic q above each
graph's own compulsory traffic (its plateau traffic). S(q) is the least
capacity whose curve point has extra traffic at most q;
dS(q) = S_cross(q) - S_same(q), over q where both are finite.
"""
import json
import sys
from collections import Counter


def s_of(points, q):
    base = points[-1][1]
    return min(c for c, t in points if t - base <= q)


def delta(same, cross):
    qs = sorted({t - same[-1][1] for _, t in same} | {t - cross[-1][1] for _, t in cross})
    q_lo = max(same[0][1] - same[-1][1], cross[0][1] - cross[-1][1])
    return [(q, s_of(cross, q) - s_of(same, q), s_of(same, q)) for q in qs if q >= q_lo]


def sign(ds):
    signs = {(d > 0) - (d < 0) for _, d, _ in ds}
    return {frozenset({1}): 'cross needs more', frozenset({-1}): 'cross needs less',
            frozenset({0}): 'equal'}.get(frozenset(signs), 'mixed' if {1, -1} <= signs else
                                         'cross more or equal' if 1 in signs else 'cross less or equal')


if __name__ == '__main__':
    rows = [json.loads(line) for line in open(sys.argv[1])]
    for mode in ('wt', 'nowt'):
        tally = Counter()
        for r in rows:
            tally[sign(delta(r[f'same_{mode}'], r[f'cross_{mode}']))] += 1
        print(mode, dict(tally))
