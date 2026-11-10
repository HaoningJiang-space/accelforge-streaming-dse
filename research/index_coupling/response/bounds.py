"""Bounds on a chain state's grammar response (CONTRACTION_ORACLE.md §14, SANDWICH_PROTOCOL.md).

- `lower`: operator projection. Projecting any plan onto one contraction
  gives a plan of that operator alone with no larger peak, and the extra
  traffic events of distinct operators are disjoint, so the chain needs at
  least the sum of its contractions' isolated optima (keep-level model).
- `upper`: the singleton partition. Every op is its own group; every interior
  vector is kept (cells in both neighbours, resident inside them) or sent via
  DRAM (2 x size). It is a plan the cut DP contains.
Where they agree at every capacity, the response is certified exactly.
"""
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.response.keep_level import curve_of

INF = float('inf')


def lower(chain, capacity, dom='halving'):
    return sum(traffic_at(capacity, curve_of(ext, live, dom)) for ext, live in chain.contractions)


def _op(chain, j, k, cells, res_in, res_out, dom):
    """Single-op group j (the k-th contraction if kind 'c') at the given end residencies."""
    if cells < 0:
        return INF
    if chain.kinds[j] == 'e':
        return 0 if cells >= (not res_in) + (not res_out) else INF
    ext, _ = chain.contractions[k]
    live = [t for t, on in (('W', chain.streamed[j]), ('X', not res_in), ('Y', not res_out)) if on]
    return traffic_at(cells, curve_of(ext, tuple(sorted(live)), dom))


def upper(chain, capacity, dom='halving'):
    n, m = len(chain.kinds), chain.rows
    sizes = [m * s for s in chain.sizes]
    best, k = {chain.first: 0}, 0  # kept/resident flag of V_j -> least traffic so far
    for j in range(n):
        nxt = {}
        for kept_in, cost in best.items():
            for kept_out in ((chain.last,) if j == n - 1 else (False, True)):
                cells = capacity - sizes[j] * (kept_in and j > 0) - sizes[j + 1] * (kept_out and j < n - 1)
                total = cost + _op(chain, j, k, cells, kept_in, kept_out, dom)
                total += 0 if kept_out or j == n - 1 else 2 * sizes[j + 1]
                if total < nxt.get(kept_out, INF):
                    nxt[kept_out] = total
        best = nxt
        k += chain.kinds[j] == 'c'
    return best.get(chain.last, INF)
