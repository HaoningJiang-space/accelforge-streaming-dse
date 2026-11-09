"""Reanalyze archived P18 curves with interval-weighted, common-domain metrics.

No mapping search is run. This is exploratory analysis after P18, not a new
prediction test. All role strings of one shape use the same finite q domain;
the signed area also has an equivalent capacity-axis integral.
"""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess

from .run_p18 import ROLES, shapes


def read_curves(path):
    data = path.read_bytes()
    records = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
    curves = {}
    for row in records:
        key = (tuple(row['shape']), row['roles'])
        assert key not in curves, ('duplicate', key)
        points = row['points']
        assert points and all(len(p) == 2 and all(type(x) is int and x > 0 for x in p)
                              for p in points), ('bad points', key)
        assert all(a[0] < b[0] and a[1] > b[1] for a, b in zip(points, points[1:])), key
        i, j, k, l = key[0]
        assert points[-1][1] == i*j+j*k+len(key[1])*l*(i+k), ('compulsory', key)
        curves[key] = points
    expected = {(tuple(s), r) for s in shapes() for r in ROLES}
    assert set(curves) == expected, ('manifest', expected-set(curves), set(curves)-expected)
    return curves, hashlib.sha256(data).hexdigest()


def capacity(points, q):
    base = points[-1][1]
    return min(c for c, traffic in points if traffic-base <= q)


def extra(points, c):
    return min(traffic-points[-1][1] for cap, traffic in points if cap <= c)


def profile(base, mixed, q_hi, refined=False):
    assert base[-1][1] == mixed[-1][1]
    assert base[0][0] == mixed[0][0], 'unequal minimum capacities need a finite-tail contract'
    pair_qs = sorted({t-points[-1][1] for points in (base, mixed) for _, t in points})
    qs = sorted(set(pair_qs) | {0, q_hi})
    assert q_hi >= max(pair_qs) and q_hi > 0
    if refined:
        qs = sorted(set(qs) | {(a+b)//2 for a,b in zip(qs,qs[1:]) if b-a > 1})
    rows = []
    area = positive_area = positive_width = negative_width = 0
    relative_area = Fraction(0)
    for lo, hi in zip(qs, qs[1:]):
        s0, s1 = capacity(base, lo), capacity(mixed, lo)
        gap, width = s1-s0, hi-lo
        area += width*gap
        positive_area += width*max(gap, 0)
        positive_width += width*(gap > 0)
        negative_width += width*(gap < 0)
        relative_area += Fraction(width*gap, s0)
        rows.append([lo, hi, s0, s1, gap])
    pair_gaps = [(q, capacity(mixed,q)-capacity(base,q), capacity(base,q)) for q in pair_qs]
    max_gap = max(g for _,g,_ in pair_gaps)
    # Layer-cake identity: the signed area between inverse curves equals the
    # signed area between traffic curves, since both have the same endpoints.
    cs = sorted({c for points in (base,mixed) for c,_ in points})
    primal_area = sum((hi-lo)*(extra(mixed,lo)-extra(base,lo))
                      for lo,hi in zip(cs,cs[1:]))
    assert primal_area == area, (primal_area, area)
    return dict(q_hi=q_hi, compulsory=base[-1][1], signed_area=area,
                positive_area=positive_area, positive_width=positive_width,
                negative_width=negative_width,
                positive_fraction=positive_width/q_hi,
                mean_absolute_gap=area/q_hi,
                mean_relative_gap=float(relative_area/q_hi),
                mean_positive_gap=positive_area/positive_width if positive_width else 0,
                max_gap=max_gap, min_gap=min(g for _,g,_ in pair_gaps),
                peak_intervals=[r[:2] for r in rows if r[-1] == max_gap and max_gap > 0],
                pair_knot_count=len(pair_qs),
                positive_pair_knots=sum(g>0 for _,g,_ in pair_gaps),
                unweighted_pair_knot_relative_mean=float(
                    sum((Fraction(g,s) for _,g,s in pair_gaps), Fraction(0))/len(pair_gaps)),
                integral_verified=True, intervals=rows)


def main():
    path = Path(__file__).parent/'results/p18.jsonl'
    curves, digest = read_curves(path)
    print(json.dumps(dict(kind='metadata', input_sha256=digest, input_records=len(curves),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        tracked_dirty=bool(subprocess.check_output(['git','diff','--name-only','HEAD'],text=True)),
        method='exact step-interval integration over a common per-shape q domain',
        exploratory=True, new_mapping_evaluations=0)), flush=True)
    results = []
    for shape in shapes():
        cv = {r:curves[(tuple(shape),r)] for r in ROLES}
        q_hi = max(t-p[-1][1] for p in cv.values() for _,t in p)
        profiles = {}
        for r,pure in [('kki','kkk'),('kkki','kkkk'),('kkii','kkkk')]:
            a = profile(cv[pure],cv[r],q_hi)
            b = profile(cv[pure],cv[r],q_hi,refined=True)
            for field in ('signed_area','positive_area','positive_width','negative_width',
                          'mean_relative_gap','max_gap','min_gap'):
                assert a[field] == b[field], ('sampling dependence',shape,r,field)
            profiles[r] = a
        record = dict(kind='shape', shape=shape, profiles=profiles,
                      order_sensitive=cv['kki']!=cv['ikk'])
        results.append(record)
        print(json.dumps(record), flush=True)
    def count(test):
        return sum(test(r['profiles']) for r in results)
    print(json.dumps(dict(kind='summary', shapes=len(results),
        two_minority_higher_weighted_relative=count(lambda p:p['kkii']['mean_relative_gap']>p['kkki']['mean_relative_gap']),
        two_minority_higher_absolute_area=count(lambda p:p['kkii']['signed_area']>p['kkki']['signed_area']),
        two_minority_wider_positive_domain=count(lambda p:p['kkii']['positive_width']>p['kkki']['positive_width']),
        same_maximum=count(lambda p:p['kkii']['max_gap']==p['kkki']['max_gap']),
        apparent_dilution_relative=count(lambda p:p['kkki']['mean_relative_gap']<p['kki']['mean_relative_gap']),
        dilution_absolute_area=count(lambda p:p['kkki']['signed_area']<p['kki']['signed_area'])
        )), flush=True)


if __name__ == '__main__':
    main()
