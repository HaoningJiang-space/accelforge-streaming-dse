"""Closed-form grammar responses of unit-M chains (CONTRACTION_ORACLE.md §6-11).

A chain is vectors V_0..V_m joined by ops: 'c' (dense contraction with a
weight) or 'e' (elementwise, same rank on both sides). All functions return
extra traffic above the compulsory reads and writes, at `cells` cells, for
grammar v2 with the given tile domain ('halving' or 'divisors').

- `loop_nest`: one contraction, both ends streamed, weight resident (§6).
- `single`, `pair`, `ce`, `ec`, `cec`: one loopable group with resident or
  streamed ends; w flags a streamed weight (one extra operand cell, §11).
- `predict`: DP over group boundaries; a boundary vector is kept (its size
  charged as cells in both neighbouring groups) or sent via DRAM (2 x size).
- `two_chain`, `contraction_chain`: the §8 and §9 special cases, kept because
  their frozen predictions are checked against them.
"""
from functools import lru_cache

from research.index_coupling.graph.curve import tile_sizes

INF = float('inf')


@lru_cache(maxsize=None)
def reachable_tiles(extent, tile_domain):
    """Every tile a chain of recursive tilings can reach, the extent included."""
    out = {extent}
    for t in tile_sizes(extent, tile_domain):
        out |= reachable_tiles(t, tile_domain)
    return frozenset(out)


def loop_nest(a, b, capacity, tile_domain):
    """One contraction a -> b (§6): hold a y tile and re-read x, or hold an x tile and spill y."""
    if capacity < 2:
        return INF
    options = [a * (b // u - 1) for u in reachable_tiles(b, tile_domain) if u <= capacity - 1]
    options += [2 * b * (a // t - 1) for t in reachable_tiles(a, tile_domain) if t <= capacity - 1]
    return min(options)


def single(p, q, cells, resident_in, resident_out, tile_domain, w=0):
    """One contraction p -> q; a resident end is held by the caller."""
    if resident_in or resident_out:
        return 0 if cells >= w + 1 - (resident_in and resident_out) else INF
    return loop_nest(p, q, cells - w, tile_domain)


def pair(a, b, c, cells, resident_in, resident_out, tile_domain, w0=0, w1=0):
    """Two contractions a -> b -> c fused under their only common rank (§8-9, §11)."""
    best = INF
    sx, sz, w = int(not resident_in), int(not resident_out), max(w0, w1)
    for u in reachable_tiles(b, tile_domain):
        trips = b // u
        options = [(u + max(sx + w0, sz + w1), (trips - 1) * (sx * a + sz * 2 * c))]
        if sz:
            options.append((c + u + max(sx + w0, w1), (trips - 1) * sx * a))  # keep z
        if sx:
            options.append((a + u + max(w0, sz + w1), 2 * (trips - 1) * sz * c))  # keep x
        if sx and sz:
            options.append((a + c + u + w, 0))
        best = min([best] + [extra for need, extra in options if cells >= need])
    return best


def ce(a, f, cells, res_in, res_out, dom, w=0):
    """X[a] -c-> H[f] -e-> Z[f], fused under F (§10)."""
    s_out = int(not res_out)
    best = INF
    for u in reachable_tiles(f, dom):
        options = ([(u + max(w, s_out), 0)] if res_in else
                   [(a + u + max(w, s_out), 0), (u + max(1 + w, s_out), a * (f // u - 1))])
        best = min([best] + [x for need, x in options if cells >= need])
    return best


def ec(f, c, cells, res_in, res_out, dom, w=0):
    """H[f] -e-> Z[f] -c-> X'[c], fused under F (§10)."""
    s_in = int(not res_in)
    best = INF
    for u in reachable_tiles(f, dom):
        options = ([(u + max(s_in, w), 0)] if res_out else
                   [(c + u + max(s_in, w), 0), (u + max(s_in, 1 + w), 2 * c * (f // u - 1))])
        best = min([best] + [x for need, x in options if cells >= need])
    return best


def cec(a, f, c, cells, res_in, res_out, dom, w1=0, w2=0):
    """X[a] -c-> H[f] -e-> Z[f] -c-> X'[c], fused under F, at most two loop levels (§10).

    Level 1 tile u keeps or re-fetches x and z (resident ends are neither).
    Level 2 either splits all three ops (H, Z tiles u) or splits off one
    contraction with its intermediate kept at u and loops the other pair
    {c, e} with tile u' < u, where that side's end may be kept at level 2.
    """
    best = INF
    x_live, z_live = not res_in, not res_out
    for u in reachable_tiles(f, dom):
        t = f // u
        for kx1 in ((False, True) if x_live else (False,)):
            for kz1 in ((False, True) if z_live else (False,)):
                base = a * kx1 + c * kz1
                sx = int(x_live and not kx1)  # x streamed below level 1
                sz = int(z_live and not kz1)
                fx = a * (t - 1) * sx         # x re-fetched per level-1 trip
                fz = 2 * c * (t - 1) * sz
                options = [(base + max(2 * u, u + sx + w1, u + sz + w2), fx + fz)]  # split all
                for v in reachable_tiles(u, dom) - {u}:
                    tt = f // v
                    # Left: {c, e} loops v, Z kept at u; x may be kept at level 2.
                    options.append((base + max(u + v + sx + w1, u + v, u + sz + w2), a * (tt - 1) * sx + fz))
                    if sx:
                        options.append((base + max(u + v + a + w1, u + v, u + sz + w2), fx + fz))
                    # Right: {e, c} loops v, H kept at u; z may be kept at level 2.
                    options.append((base + max(u + sx + w1, u + v, u + v + sz + w2), fx + 2 * c * (tt - 1) * sz))
                    if sz:
                        options.append((base + max(u + sx + w1, u + v, u + v + c + w2), fx + fz))
                best = min([best] + [x for need, x in options if cells >= need])
    return best


def group(pattern, sizes, cells, res_in, res_out, dom, ws=None):
    """One loopable group; ws holds per-op streamed-weight flags (0 for elementwise ops)."""
    ws = [w for w, k in zip(ws or [0] * len(pattern), pattern) if k == 'c']
    if pattern == 'c':
        return single(sizes[0], sizes[1], cells, res_in, res_out, dom, *ws)
    if pattern == 'e':
        return 0 if cells >= (not res_in) + (not res_out) else INF
    if pattern == 'cc':
        return pair(*sizes, cells, res_in, res_out, dom, *ws)
    if pattern == 'ce':
        return ce(sizes[0], sizes[1], cells, res_in, res_out, dom, *ws)
    if pattern == 'ec':
        return ec(sizes[0], sizes[2], cells, res_in, res_out, dom, *ws)
    if pattern == 'cec':
        return cec(sizes[0], sizes[1], sizes[3], cells, res_in, res_out, dom, *ws)
    raise ValueError(f'no form for group pattern {pattern}')


_group = lru_cache(maxsize=None)(group)


def ranks(kinds):
    """Synthetic rank id of each vector: elementwise keeps it, a contraction changes it."""
    rank = [0]
    for k in kinds:
        rank.append(rank[-1] if k == 'e' else rank[-1] + 1)
    return rank


@lru_cache(maxsize=None)
def segments(kinds):
    """Loopable runs (j, k, pattern), whose ops share a rank, in DP order."""
    rank, out = ranks(kinds), []
    for j in range(len(kinds)):
        common = None
        for k in range(j + 1, len(kinds) + 1):
            own = {rank[k - 1], rank[k]}
            common = own if common is None else common & own
            if not common:
                break
            out.append((j, k, ''.join(kinds[j:k])))
    return tuple(out)


def predict(kinds, sizes, capacity, dom, resident_first=False, resident_last=False, streamed=None):
    """Least extra traffic of a unit-M chain at `capacity` cells.

    Resident ends are held by the caller: groups see them as resident at no
    cell cost. streamed[i] = 1 if op i's weight is not resident.
    """
    kinds, sizes, m = tuple(kinds), tuple(sizes), len(kinds)
    streamed = tuple(streamed) if streamed else (0,) * m
    best = {(0, resident_first): 0}
    for j, k, pattern in segments(kinds):
        for kept_j in (False, True):
            if (j, kept_j) not in best:
                continue
            for kept_k in ((resident_last,) if k == m else (False, True)):
                cells = capacity - sizes[j] * (kept_j and j > 0) - sizes[k] * (kept_k and k < m)
                cost = _group(pattern, sizes[j:k + 1], cells, kept_j, kept_k, dom, streamed[j:k])
                cost += 0 if kept_k or k == m else 2 * sizes[k]
                if best[j, kept_j] + cost < best.get((k, kept_k), INF):
                    best[k, kept_k] = best[j, kept_j] + cost
    return best.get((m, resident_last), INF)


def two_chain(a, b, c, capacity, tile_domain):
    """§8: x[a] -> h[b] -> z[c], weights resident, ends streamed."""
    options = [2 * b + loop_nest(a, b, capacity, tile_domain) + loop_nest(b, c, capacity, tile_domain)]
    for u in reachable_tiles(b, tile_domain):
        trips = b // u
        for cells, extra in ((u + 1, (trips - 1) * (a + 2 * c)), (c + u + 1, (trips - 1) * a),
                             (a + u + 1, 2 * (trips - 1) * c), (a + c + u, 0)):
            if capacity >= cells:
                options.append(extra)
    return min(options)


def contraction_chain(sizes, capacity, tile_domain):
    """§9: pure contraction chain, weights resident, ends streamed (equals predict)."""
    return predict(['c'] * (len(sizes) - 1), sizes, capacity, tile_domain)
