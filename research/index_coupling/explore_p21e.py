"""Exploratory sweep before freezing P21e: when must EH0 own its outer loop?

For residual(I, K, L, depth, reads_x) compares, with the exact cut DP:
- free: the unrestricted curve;
- tied: the same grammar except that EX and EH0 never become separate groups
  at full extents of the whole span (cut 1 excluded from the first whole-span
  partition, as in P21d's structural rule).
Records the integer capacities where tied is above free and the traffic gap.
Exploratory: the shapes swept here are excluded from the P21e held-out set.

Usage: python -m research.index_coupling.explore_p21e I K L DEPTH READS_X
"""
import json
import sys
import time

from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import residual

if __name__ == '__main__':
    i, k, l, depth, reads_x = (int(a) for a in sys.argv[1:6])
    graph = residual(i, k, l, depth, bool(reads_x))
    start = time.time()
    free = [list(p[:2]) for p in curve(graph, partitions='dp')]
    tied = [list(p[:2]) for p in curve(graph, partitions='dp',
                                       whole_span_cuts=range(2, len(graph.ops)))]
    hi = max(p[0] for p in free + tied)
    gaps = [[c, traffic_at(c, tied) - traffic_at(c, free)] for c in range(hi + 1)
            if traffic_at(c, tied) != traffic_at(c, free)]
    print(json.dumps(dict(shape=[i, k, l], depth=depth, reads_x=bool(reads_x), free=free, tied=tied,
                          gap_capacities=len(gaps), max_gap=max((g for _, g in gaps), default=0),
                          gaps=gaps, seconds=time.time() - start)))
