"""How many tensors are locally live and nonscalar in each nontrivial state?

For every recorded state with a multi-point or positive-traffic frontier
(stratum `rest` of attribute_work.py), counts k = live tensors of size > 1 at
the current extents, and the number of distinct ranks some live nonscalar
tensor lacks among the span's common ranks (`conflict axes`). The two-live
normal form (ONE_OBLIGATION_RESULTS.md section 3) covers k <= 2 only.

Usage: python -m research.index_coupling.live_profile STATES.jsonl.gz CASE
"""
from collections import Counter
import json
import sys

from research.index_coupling.census_tools import accesses, extents, graph_of, load_states, size_at, stratum


def main(path, case):
    graph = graph_of(case)
    by_k, by_axes = Counter(), Counter()
    for s in load_states(path):
        if stratum(graph, s) != 'rest':
            continue
        ext, dims = extents(graph, s), accesses(graph, s)
        live = [t for t in dims if t not in s['external'] and size_at(dims[t], ext) > 1]
        common = set.intersection(*(graph.rank_vars((op,)) for op in s['ops']))
        axes = {v for v in common if ext[v] > 1 and any(v not in dims[t] for t in live)}
        by_k[min(len(live), 6)] += 1
        by_axes[len(axes)] += 1
    print(json.dumps(dict(case=case, rest=sum(by_k.values()),
                          live_nonscalar={str(k): by_k[k] for k in sorted(by_k)},
                          conflict_axes={str(k): by_axes[k] for k in sorted(by_axes)})))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
