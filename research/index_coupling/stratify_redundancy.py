"""Split cache keys into trivial and remaining strata before measuring redundancy.

- empty: the response is infeasible (no frontier point);
- zero_at_d: the single point (d, 0), with d the per-operator operand bound;
- zero_above_d: a single point (c, 0) with c > d: zero extra traffic only
  (archived *.strat.json files predate this split and merge both as
  `lower_bound`);
- rest: everything else, where local redundancy (decorations at a fixed
  stage/span/extents vs distinct frontiers) is reported separately.

Usage: python -m research.index_coupling.stratify_redundancy STATES.jsonl.gz CASE
"""
from collections import defaultdict
import json
import sys

from research.index_coupling.census_tools import graph_of, load_states, points_of, stratum


def main(path, case):
    graph = graph_of(case)
    counts = dict(keys=0, empty=0, zero_at_d=0, zero_above_d=0, rest=0)
    local = defaultdict(set)
    for s in load_states(path):
        counts['keys'] += 1
        points = points_of(s)
        kind = stratum(graph, s, points)
        counts[kind] += 1
        if kind == 'rest':
            local[(s['stage'], tuple(s['ops']), tuple(s['ext']), s['constrained'])].add(points)
    counts.update(rest_contexts=len(local), rest_local_distinct=sum(len(v) for v in local.values()),
                  rest_distinct=len({f for v in local.values() for f in v}))
    print(json.dumps(dict(case=case, **counts)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
