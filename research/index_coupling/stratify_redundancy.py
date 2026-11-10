"""Split cache keys into trivial and remaining strata before measuring redundancy.

- empty: the response is infeasible (no frontier point);
- lower_bound: the response is the single point (c, 0), i.e. zero extra
  traffic, which is the shape the scalar-X bridge proves for its states;
- rest: everything else, where local redundancy (decorations at a fixed
  stage/span/extents vs distinct frontiers) is reported separately.

Usage: python -m research.index_coupling.stratify_redundancy STATES.jsonl.gz CASE
"""
from collections import defaultdict
import gzip
import json
import sys


def main(path, case):
    counts = dict(keys=0, empty=0, lower_bound=0, rest=0)
    local = defaultdict(set)
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            s = json.loads(line)
            counts['keys'] += 1
            points = tuple(map(tuple, s['points']))
            if not points:
                counts['empty'] += 1
            elif len(points) == 1 and points[0][1] == 0:
                counts['lower_bound'] += 1
            else:
                counts['rest'] += 1
                local[(s['stage'], tuple(s['ops']), tuple(s['ext']), s['constrained'])].add(points)
    counts.update(rest_contexts=len(local), rest_local_distinct=sum(len(v) for v in local.values()),
                  rest_distinct=len({f for v in local.values() for f in v}))
    print(json.dumps(dict(case=case, **counts)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
