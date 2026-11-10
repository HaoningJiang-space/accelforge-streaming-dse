"""Supplementary P21d depth-12 cases computed with the exact cut DP.

The four depth-12 cases timed out under enumeration in the frozen run, so the
frozen verdict counts them as incomplete. This computes both arms with
partitions='dp' (same grammar and pricing, corrected final-write ownership),
executes every frontier witness, and compares the arms. It does not rescore
P21d; it reports what the incomplete cases would have shown.

Usage (designated server): python -m research.index_coupling.supplement_p21d_dp CASE
"""
import json
import sys
import time

from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve
from research.index_coupling.run_p21d import audit
from research.index_coupling.graph.model import residual
from research.index_coupling.simulate_nest import simulate


def arm(graph, options):
    start = time.time()
    points = curve(graph, witness=True, partitions='dp', **options)
    seconds = time.time() - start
    exact = 0
    for c, q, w in points:
        a = simulate(graph, w)
        exact += a['valid'] and (a['peak'], a['traffic']) == (c, q)
    return dict(points=[list(p[:2]) for p in points], replay_exact=exact, seconds=seconds)


if __name__ == '__main__':
    spec = audit(int(sys.argv[1]))
    graph = residual(*spec['shape'], spec['depth'], spec['reads_x'])
    structural = arm(graph, dict(whole_span_cuts=spec['cut_rule']['positions']))
    unrestricted = arm(graph, {})
    s, u = structural['points'], unrestricted['points']
    hi = max(p[0] for p in s + u)
    wrong = [[c, traffic_at(c, s), traffic_at(c, u)] for c in range(hi + 1)
             if traffic_at(c, s) != traffic_at(c, u)]
    print(json.dumps(dict(case=spec['case'], shape=spec['shape'], depth=spec['depth'],
                          reads_x=spec['reads_x'], cuts=spec['cut_rule']['positions'],
                          structural=structural, unrestricted=unrestricted,
                          equal=not wrong, wrong_capacities=len(wrong), first_errors=wrong[:5])))
