"""Exact EDP minimization over an upward E/T supporting-line relaxation."""
from fractions import Fraction as F
from itertools import combinations


def minimum_product(energy,latency,weighted_bounds):
    """Lines E+lambda*T>=value, lambda>=0; retain E/T correlation.

    The lower frontier is piecewise linear. On a descending segment E*T is
    concave, so its minimum is at a vertex. The two unbounded frontier rays
    increase in the free coordinate. Zero axis bounds are supported as well.
    """
    lines = [(F(1),F(),F(energy)),(F(),F(1),F(latency))]
    lines += [(F(1),F(weight),F(value)) for weight,value in weighted_bounds if weight>=0]
    candidates = []
    for left,right in combinations(lines,2):
        a,b,c = left
        d,e,f = right
        determinant = a*e-b*d
        if not determinant:
            continue
        x,y = (c*e-b*f)/determinant,(a*f-c*d)/determinant
        if x<0 or y<0 or any(p*x+q*y<r for p,q,r in lines):
            continue
        candidates.append((x*y,x,y))
    if not candidates:
        raise ValueError('nonempty finite upward relaxation must have a vertex')
    return min(candidates)
