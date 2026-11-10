"""Closed conditional responses for two dense contractions, grammar v2 only.

Pure predictor: no solver/executor imports. Caller-resident weights and endpoint
vectors are excluded from capacity and compulsory traffic. This is a declared
formula for the restricted interface, not a drop-in general-graph optimization.
"""
from functools import lru_cache
from math import inf, isqrt


@lru_cache(None)
def proper_tiles(n, domain):
    if type(n) is not int or n < 1:
        raise ValueError('positive integer extent required')
    if domain == 'divisors':
        values = set()
        for d in range(1, isqrt(n)+1):
            if n % d == 0:
                values.update((d,n//d))
        return tuple(sorted(values-{n},reverse=True))
    if domain != 'halving':
        raise ValueError('unknown tile domain')
    values, b = [], n//2
    while b:
        if n % b == 0:
            values.append(b)
        b //= 2
    return tuple(values)


@lru_cache(None)
def reachable_tiles(n, domain):
    values = {n}
    for t in proper_tiles(n,domain):
        values.update(reachable_tiles(t,domain))
    return tuple(sorted(values))


def single(a, b, capacity, resident_in=False, resident_out=False, domain='halving'):
    if resident_in or resident_out:
        return 0 if capacity >= int(not (resident_in and resident_out)) else inf
    candidates = [a*(b//u-1) for u in reachable_tiles(b,domain) if u+1 <= capacity]
    candidates += [2*b*(a//t-1) for t in reachable_tiles(a,domain) if t+1 <= capacity]
    return min(candidates,default=inf)


def alternatives(a, b, c, capacity, resident_in=False, resident_out=False, domain='halving'):
    """Solve-entry normal forms; fields describe sufficient capacity, not time."""
    p, q = bool(resident_in), bool(resident_out)
    yield dict(kind='materialize_h', traffic=2*b+single(a,b,capacity,p,False,domain)
               +single(b,c,capacity,False,q,domain))
    for u in reachable_tiles(b,domain):
        for keep_x in ((True,) if p else (False,True)):
            for keep_z in ((True,) if q else (False,True)):
                reserve = a*(keep_x and not p)+c*(keep_z and not q)
                need = reserve+u+int(not (keep_x and keep_z))
                if capacity >= need:
                    yield dict(kind='retain_h_tile', tile=u, keep_x=keep_x, keep_z=keep_z,
                        capacity=need, traffic=(a*(not keep_x)+2*c*(not keep_z))*(b//u-1))


def solve_response(a, b, c, capacity, resident_in=False, resident_out=False, domain='halving'):
    return min(row['traffic'] for row in alternatives(a,b,c,capacity,resident_in,resident_out,domain))


def group_response(a, b, c, capacity, resident_in=False, resident_out=False, domain='halving'):
    p, q = bool(resident_in), bool(resident_out)
    if b == 1 and (p or a == 1) and (q or c == 1):
        # v2 scalar group -> solve, including scalar partition choices.
        return solve_response(a,b,c,capacity,p,q,domain)
    best = inf
    for u in proper_tiles(b,domain):
        r = b//u
        for keep_x in ((True,) if p else (False,True)):
            for keep_z in ((True,) if q else (False,True)):
                reserve = a*(keep_x and not p)+c*(keep_z and not q)
                if reserve > capacity:
                    continue
                extra = (a*(not keep_x)+2*c*(not keep_z))*(r-1)
                child = solve_response(a,u,c,capacity-reserve,keep_x,keep_z,domain)
                best = min(best,extra+r*child)
    return best
