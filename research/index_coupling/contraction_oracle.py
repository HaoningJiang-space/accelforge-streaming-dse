"""Exact schedule-level optimum for one dense contraction, vs the loop grammar.

One contraction y_j += x_i * W[i, j] for all i < a, j < b, with W resident. A
serial schedule with C cells for x and y elements may:
- load x_i: free the first time, 1 extra transfer afterwards;
- evict x_i: free;
- bring y_j on chip: free when fresh, part of a spill otherwise;
- evict y_j: free once all a contributions are done (its compulsory write);
  otherwise a spill of 2 extra transfers (write plus read back);
- multiply-add (i, j): requires x_i and y_j on chip, at most once per pair,
  no recomputation.

`oracle(a, b, C)` is the least extra traffic over ALL such schedules
(Dijkstra on (done pairs, on-chip set)). `grammar(a, b, C)` is the
curve() optimum of the same contraction under both tile domains.
`serpentine(a, b, C)` is the first conjecture (refuted at a = b = C = 4);
`blocked(a, b, C)` is its post-hoc repair.

Usage: python -m research.index_coupling.contraction_oracle MAX_A MAX_B
       python -m research.index_coupling.contraction_oracle --cases A,B[,A,B...]
"""
from heapq import heappop, heappush
from itertools import product
import json
import sys

from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve, tile_sizes
from research.index_coupling.graph.model import Graph


def oracle(a, b, capacity):
    full = (1 << (a * b)) - 1
    x_bits = [sum(1 << (i * b + j) for j in range(b)) for i in range(a)]
    y_bits = [sum(1 << (i * b + j) for i in range(a)) for j in range(b)]
    start = (0, frozenset())
    best = {start: 0}
    heap = [(0, 0, frozenset())]
    while heap:
        cost, done, chip = heappop(heap)
        if best.get((done, chip), cost) < cost:
            continue
        if done == full:
            return cost
        moves = []
        for e in chip:  # evictions
            kind, k = e
            extra = 2 if kind == 'y' and done & y_bits[k] and (done & y_bits[k]) != y_bits[k] else 0
            moves.append((extra, done, chip - {e}))
        if len(chip) < capacity:  # loads
            for i in range(a):
                if ('x', i) not in chip and (done & x_bits[i]) != x_bits[i]:
                    moves.append((1 if done & x_bits[i] else 0, done, chip | {('x', i)}))
            for j in range(b):
                if ('y', j) not in chip and (done & y_bits[j]) != y_bits[j]:
                    moves.append((0, done, chip | {('y', j)}))  # a spill was charged at eviction
        for i, j in product(range(a), range(b)):  # multiply-adds
            bit = 1 << (i * b + j)
            if not done & bit and ('x', i) in chip and ('y', j) in chip:
                moves.append((0, done | bit, chip))
        for extra, d, c in moves:
            key, total = (d, c), cost + extra
            if total < best.get(key, float('inf')):
                best[key] = total
                heappush(heap, (total, d, c))
    return float('inf')


def grammar(a, b, capacity, tile_domain):
    g = Graph(dict(D=a, F=b), [('E', {'x': ('D',), 'W': ('D', 'F'), 'y': ('F',)})])
    points = curve(g, partitions='dp', external=frozenset({'W'}), scalar_leaf='v2', tile_domain=tile_domain)
    return traffic_at(capacity, points) - (a + b)  # remove compulsory x reads and y writes


def reachable_tiles(extent, tile_domain):
    """Every tile a chain of recursive tilings can reach, the extent included."""
    out = {extent}
    for t in tile_sizes(extent, tile_domain):
        out |= reachable_tiles(t, tile_domain)
    return out


def loop_nest(a, b, capacity, tile_domain):
    """Predicted grammar optimum (CONTRACTION_ORACLE.md §6): one held tile, one-level.

    Hold a y tile u (u | b by a tiling chain, u <= C-1) and re-read all of x
    per F tile: a (b/u - 1). Or hold an x tile t and spill y per D tile:
    2 b (a/t - 1). Deeper nests and mixed orders are claimed never to help.
    """
    if capacity < 2:
        return float('inf')
    options = [a * (b // u - 1) for u in reachable_tiles(b, tile_domain) if u <= capacity - 1]
    options += [2 * b * (a // t - 1) for t in reachable_tiles(a, tile_domain) if t <= capacity - 1]
    return min(options)


def ceil_div(p, q):
    return -(-p // q)


def serpentine(a, b, capacity):
    """Hold u = C-1 elements of one side, sweep the other side back and forth."""
    if capacity < 2:
        return float('inf')
    if capacity > min(a, b):
        return 0
    u = capacity - 1
    keep_y = (a - 1) * (ceil_div(b, u) - 1)          # reuse the last x at each turn
    keep_x = 2 * (b - 1) * (ceil_div(a, u) - 1)      # reuse the last y partial at each turn
    return min(keep_y, keep_x)


def blocked(a, b, capacity):
    """Blocked serpentine with carry-over, fitted after the 4x4 counterexample.

    Hold one side in consecutive blocks u_1, u_2, ... (each at most C-1) and
    sweep the other side back and forth. At the turn between blocks u_k and
    u_{k+1}, at most C - max(u_k, u_{k+1}) streamed elements stay on chip, so
    the turn costs w * max(0, n - C + max(u_k, u_{k+1})), where n is the
    streamed side's size and w = 1 for streamed inputs, 2 for spilled
    partial sums. Minimise over block sequences (DP) and over which side is held.
    """
    if capacity < 2:
        return float('inf')
    if capacity > min(a, b):
        return 0

    def side(n, m, w):
        best = {0: {None: 0}}
        for rem in range(1, m + 1):
            best[rem] = {}
            for u in range(1, min(rem, capacity - 1) + 1):
                options = [cost + (0 if prev is None else w * max(0, n - capacity + max(prev, u)))
                           for prev, cost in best[rem - u].items()]
                best[rem][u] = min(options)
        return min(best[m].values())
    return min(side(a, b, 1), side(b, a, 2))


def main(max_a, max_b):
    rows = []
    for a in range(1, max_a + 1):
        for b in range(1, max_b + 1):
            for c in range(2, min(a, b) + 2):
                row = dict(a=a, b=b, C=c, oracle=oracle(a, b, c), serpentine=serpentine(a, b, c), blocked=blocked(a, b, c),
                           grammar_halving=grammar(a, b, c, 'halving'),
                           grammar_divisors=grammar(a, b, c, 'divisors'))
                rows.append(row)
                print(json.dumps(row))
    print(json.dumps(dict(cases=len(rows), serpentine_equals_oracle=sum(r['oracle'] == r['serpentine'] for r in rows),
                          blocked_equals_oracle=sum(r['oracle'] == r['blocked'] for r in rows),
                          grammar_divisors_above_oracle=sum(r['grammar_divisors'] > r['oracle'] for r in rows))))


def cases(pairs):
    for a, b in pairs:
        for c in range(2, min(a, b) + 2):
            row = dict(a=a, b=b, C=c, oracle=oracle(a, b, c), blocked=blocked(a, b, c),
                       grammar_divisors=grammar(a, b, c, 'divisors'))
            print(json.dumps(row), flush=True)


if __name__ == '__main__':
    if sys.argv[1] == '--cases':
        values = [int(v) for v in sys.argv[2].split(',')]
        cases(zip(values[::2], values[1::2]))
    else:
        main(int(sys.argv[1]), int(sys.argv[2]))
