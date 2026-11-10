"""Is releasing one private input's residency a local lifting of the response?

Pairs every recorded state sigma with sigma' = sigma except that one live
tensor W is resident. W must be nonscalar, accessed by exactly one operator of
the span, and not produced inside it (for example a weight). Same stage, span,
extents, owned set and constraint.

Tests, over all pairs found in a census:
- sandwich: Q'(C) <= Q(C) <= Q'(C - s), with s = |W| at the current extents.
  The left side holds because residency only removes work. The right side
  holds because keeping W for the whole span costs s and no traffic. A
  violation means an accounting or reachability error, not a finding.
- lift_<descriptor>: F(sigma) is a function of (F(sigma'), descriptor(W)).
  If a descriptor has no violations, releasing W acts on the response
  through local data only:
    size: (s, extents of W's ranks);
    op: size + operator position class + sizes of that operator's other live
        tensors;
    op_lacks: op + which of the span's common ranks W lacks.
- tight_keep: F(sigma) equals F(sigma') shifted by s, i.e. W is always best
  kept whole; free_release: F(sigma) equals F(sigma'), i.e. releasing W costs
  nothing. solve_split classifies solve pairs into free / keep / between.

Usage: python -m research.index_coupling.private_lift STATES.jsonl.gz CASE
"""
from collections import defaultdict
import gzip
import json
from math import prod
import sys

from research.index_coupling.analyze_redundancy import graph_of


def traffic(points, c):
    best = None
    for cap, q in points:
        if cap <= c and (best is None or q < best):
            best = q
    return best


def main(path, case):
    graph = graph_of(case)
    names = sorted(graph.sizes)
    index = {}
    states = []
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            s = json.loads(line)
            key = (s['stage'], tuple(s['ops']), tuple(s['ext']), s['constrained'], tuple(s['owned']),
                   frozenset(s['external']))
            index[key] = tuple(map(tuple, s['points']))
            states.append((key, s))
    produced = graph.produced()
    report = dict(case=case, states=len(states), pairs=0, tight_keep=0, free_release=0,
                  solve_split=dict(free=0, keep=0, between=0),
                  sandwich_violations=dict(solve=0, group=0), solve_pairs=0)
    lifts = {f'{name}_{stage}': defaultdict(set) for name in ('size', 'op', 'op_lacks')
             for stage in ('solve', 'group')}
    for key, s in states:
        stage, ops, ext_t, constrained, owned, external = key
        ext = dict(zip(names, ext_t))
        users = defaultdict(list)
        for i, op in enumerate(ops):
            for t in graph.access[op]:
                users[t].append(i)
        common = set.intersection(*(graph.rank_vars((op,)) for op in ops))
        for w, at in users.items():
            if w in external or len(at) != 1 or w in produced:
                continue
            dims = graph.access[ops[at[0]]][w]
            size = prod(ext[v] for v in dims)
            if size == 1:
                continue
            partner = index.get((stage, ops, ext_t, constrained, owned, external | {w}))
            if partner is None:
                continue
            mine = index[key]
            report['pairs'] += 1
            report['solve_pairs'] += stage == 'solve'
            caps = sorted({c for c, _ in mine} | {c for c, _ in partner} | {c + size for c, _ in partner})
            for c in caps:
                lo, mid, hi = traffic(partner, c), traffic(mine, c), traffic(partner, c - size)
                if (mid is not None and lo is None) or (hi is not None and mid is None) or \
                        (mid is not None and lo is not None and lo > mid) or \
                        (hi is not None and mid is not None and mid > hi):
                    report['sandwich_violations'][stage] += 1
                    break
            keep, free = mine == tuple((c + size, q) for c, q in partner), mine == partner
            report['tight_keep'] += keep
            report['free_release'] += free
            if stage == 'solve':
                report['solve_split']['free' if free else 'keep' if keep else 'between'] += 1
            op = ops[at[0]]
            others = tuple(sorted(prod(ext[v] for v in d) for t, d in graph.access[op].items()
                                  if t != w and t not in external))
            position = (at[0] == 0, at[0] == len(ops) - 1, len(ops) == 1)
            lacks = tuple(sorted(ext[v] for v in common if v not in dims))
            base = (stage, size, tuple(sorted(ext[v] for v in dims)))
            descriptors = dict(size=base, op=base + (position, others), op_lacks=base + (position, others, lacks))
            for name, d in descriptors.items():
                lifts[f'{name}_{stage}'][(partner, d)].add(mine)
    for name, groups in lifts.items():
        report[f'lift_{name}'] = dict(classes=len(groups), violations=sum(len(v) > 1 for v in groups.values()))
    print(json.dumps(report))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
