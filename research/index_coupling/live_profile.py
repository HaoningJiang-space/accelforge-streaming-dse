"""How many tensors are locally live and nonscalar in each nontrivial state?

For every recorded state with a multi-point or positive-traffic frontier
(stratum `rest` of attribute_work.py), counts k = live tensors of size > 1 at
the current extents, and the number of distinct ranks some live nonscalar
tensor lacks among the span's common ranks (`conflict axes`). The two-live
normal form (ONE_OBLIGATION_RESULTS.md section 3) covers k <= 2 only.

Usage: python -m research.index_coupling.live_profile STATES.jsonl.gz CASE
"""
from collections import Counter
import gzip
import json
from math import prod
import sys

from research.index_coupling.analyze_redundancy import graph_of


def main(path, case):
    graph = graph_of(case)
    names = sorted(graph.sizes)
    by_k, by_axes = Counter(), Counter()
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            s = json.loads(line)
            p = s['points']
            if not p or (len(p) == 1 and p[0][1] == 0):
                continue
            ext = dict(zip(names, s['ext']))
            dims = {t: d for op in s['ops'] for t, d in graph.access[op].items()}
            live = [t for t in dims if t not in s['external'] and prod(ext[v] for v in dims[t]) > 1]
            common = set.intersection(*(graph.rank_vars((op,)) for op in s['ops']))
            axes = {v for v in common if ext[v] > 1 and any(v not in dims[t] for t in live)}
            by_k[min(len(live), 6)] += 1
            by_axes[len(axes)] += 1
    print(json.dumps(dict(case=case, rest=sum(by_k.values()),
                          live_nonscalar={str(k): by_k[k] for k in sorted(by_k)},
                          conflict_axes={str(k): by_axes[k] for k in sorted(by_axes)})))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
