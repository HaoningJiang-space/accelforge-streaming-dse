"""Exploratory P21 attribution: how much of the fixed-boundary gap is the I chain?

For each P21 graph, compares on integer capacities:
- fixed:     root partition EX | H | EAdd at full extents, allowing H_last
             retention (unlike frozen P21, which materializes H_last);
- lifted:    any chain of loops over I (the only span-legal rank) above that
             fixed partition, composed by graph/context.py;
- regraded:  the same chain composition above the unrestricted curve, which
             must reproduce the unrestricted curve (accounting check);
- unrestricted.
Not a frozen prediction. Run on the designated server: --case 0..15.
"""
import argparse
import json
import time

from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.context import lifted_curve, span_ranks
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import residual
from research.index_coupling.run_p21 import CASES


def fixed_bottom(g, kept):
    groups = (g.ops[:1], g.ops[1:-1], g.ops[-1:])
    return [p[:2] for p in curve(g, external=kept, root_groups=groups)]


def free_bottom(g, kept):
    return [p[:2] for p in curve(g, external=kept)]


def gap(a, b):
    # Integer capacities through the last breakpoint where a is above b.
    hi = max(p[0] for p in a + b)
    return [c for c in range(hi + 1) if traffic_at(c, a) > traffic_at(c, b)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', type=int, required=True)
    args = ap.parse_args()
    (ni, nk, nl), depth, reads_x = CASES[args.case]
    graph = residual(ni, nk, nl, depth, reads_x)
    start = time.time()
    unrestricted = [list(p[:2]) for p in curve(graph)]
    fixed = fixed_bottom(graph, frozenset())
    lifted = [list(p) for p in lifted_curve(graph, 'I', fixed_bottom)]
    regraded = [list(p) for p in lifted_curve(graph, 'I', free_bottom)]
    print(json.dumps(dict(
        case=args.case, shape=[ni, nk, nl], depth=depth, reads_x=reads_x,
        span_ranks=sorted(span_ranks(graph, graph.ops)),
        unrestricted=unrestricted, fixed=[list(p) for p in fixed], lifted=lifted,
        regraded_equal=regraded == unrestricted,
        fixed_above=gap(fixed, unrestricted), lifted_above=gap(lifted, unrestricted),
        lifted_below_fixed=gap(fixed, lifted), seconds=time.time() - start)))


if __name__ == '__main__':
    main()
