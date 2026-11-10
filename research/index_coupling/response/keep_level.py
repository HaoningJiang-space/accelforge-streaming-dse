"""Keep-level model of one contraction's grammar response at any M (CONTRACTION_ORACLE.md §12).

Y[M,F] += X[M,D] W[D,F]. Each tensor lacks one rank (X: F, W: M, Y: D).
Along a loop nest the current tiles c = (c_M, c_D, c_F) only shrink. A live
tensor T is either
- kept at a loop over its lacking rank r, at tiles c with c_r > 1: it then
  holds the product of its own tiles in cells, and was re-fetched
  E_r / c_r - 1 times;
- or never kept: it ends scalar at the leaf (1 cell), re-fetched E_r / c_r - 1
  times with c the leaf tiles.
Peak cells add over tensors. Keeps happen in some order; after T is kept the
next state has a smaller r tile (the keeping loop). Y's re-fetches are spills
(weight 2). `predict` minimises over orders and states; `curve_of` caches its
frontier per (ext, live, domain).
"""
from functools import lru_cache
from itertools import permutations, product

from research.index_coupling.graph.curve import pareto
from research.index_coupling.response.forms import reachable_tiles

OWN = dict(X=(0, 1), W=(1, 2), Y=(0, 2))
LACK = dict(X=2, W=0, Y=1)
WEIGHT = dict(X=1, W=1, Y=2)
INF = float('inf')


def predict(ext, live, capacity, dom):
    """Least extra traffic of one contraction with extents (M, D, F) and the given live tensors."""
    live = tuple(sorted(live))
    size = {t: ext[OWN[t][0]] * ext[OWN[t][1]] for t in live}
    tiles = [sorted(reachable_tiles(e, dom)) for e in ext]

    def below(c, need):
        """States reachable from c; the `need` rank must shrink."""
        for s in product(*tiles):
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


@lru_cache(maxsize=None)
def curve_of(ext, live, dom):
    """Frontier of `predict`, scanned upward to the first zero-traffic point."""
    live = tuple(sorted(live))
    top = sum(ext[OWN[t][0]] * ext[OWN[t][1]] for t in live) + 3
    points = []
    for c in range(top + 1):
        q = predict(ext, live, c, dom)
        if q != INF:
            points.append((c, q))
            if q == 0:
                break
    return pareto(points)
