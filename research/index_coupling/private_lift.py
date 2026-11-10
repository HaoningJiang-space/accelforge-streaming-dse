"""Is releasing one private input's residency a local lifting of the response?

Pairs every recorded state sigma with sigma' = sigma except that one live
tensor W is resident. W must be nonscalar, accessed by exactly one operator of
the span, and not produced inside it (for example a weight). Same stage, span,
extents, owned set and constraint. Q and Q' are their least extra traffic at
capacity C; s = |W| at the current extents.

Reported per entry (solve/group):
- monotone: pairs violating Q'(C) <= Q(C). Residency monotonicity; v1 breaks
  it through its mandatory scalar leaf, v2 proves it (GRAMMAR_V2.md).
- keep_bound: pairs violating Q(C) <= Q'(C - s). Not monotonicity: a group must
  loop unless every live tensor is scalar, so it may be unable to hold W whole.
- free / keep / between: F(sigma) = F(sigma'); F(sigma) = F(sigma') shifted
  by s; anything else.
- lift_<descriptor>: classes of equal (F(sigma'), descriptor(W)) whose F(sigma)
  differ. Zero would mean releasing W is a function of local data only:
    size: (s, extents of W's ranks);
    op: size + operator position class + sizes of that operator's other live
        tensors;
    op_lacks: op + extents of the span's common ranks that W lacks.

Usage: python -m research.index_coupling.private_lift STATES.jsonl.gz CASE
"""
from collections import defaultdict
import json
import sys

from research.index_coupling.census_tools import extents, graph_of, key_of, load_states, points_of, size_at
from research.index_coupling.graph.analysis import traffic_at


def exceeds(a, b, shift=0):
    """Some capacity C with traffic_at(C, a) > traffic_at(C - shift, b)."""
    capacities = {c for c, _ in a} | {c + shift for c, _ in b}
    return any(traffic_at(c, a) > traffic_at(c - shift, b) for c in capacities)


def pairs(graph, index):
    produced = graph.produced()
    for key, mine in index.items():
        users = defaultdict(list)
        for i, op in enumerate(key.ops):
            for t in graph.access[op]:
                users[t].append(i)
        for w, at in users.items():
            if w in key.external or len(at) != 1 or w in produced:
                continue
            partner = index.get(key._replace(external=key.external | {w}))
            if partner is not None:
                yield key, w, at[0], mine, partner


def main(path, case):
    graph = graph_of(case)
    index = {key_of(s): points_of(s) for s in load_states(path)}
    entries = ('solve', 'group')
    report = dict(case=case, states=len(index),
                  **{e: dict(pairs=0, monotone=0, keep_bound=0, free=0, keep=0, between=0) for e in entries})
    lifts = {f'{name}_{e}': defaultdict(set) for name in ('size', 'op', 'op_lacks') for e in entries}
    for key, w, position, mine, partner in pairs(graph, index):
        ext = extents(graph, dict(ext=key.ext))
        op = key.ops[position]
        dims = graph.access[op][w]
        size = size_at(dims, ext)
        if size == 1:
            continue
        row = report[key.stage]
        row['pairs'] += 1
        row['monotone'] += exceeds(partner, mine)
        row['keep_bound'] += exceeds(mine, partner, size)
        free, keep = mine == partner, mine == tuple((c + size, q) for c, q in partner)
        row['free' if free else 'keep' if keep else 'between'] += 1
        common = set.intersection(*(graph.rank_vars((o,)) for o in key.ops))
        others = tuple(sorted(size_at(d, ext) for t, d in graph.access[op].items()
                              if t != w and t not in key.external))
        place = (position == 0, position == len(key.ops) - 1, len(key.ops) == 1)
        base = (size, tuple(sorted(ext[v] for v in dims)))
        lacks = tuple(sorted(ext[v] for v in common if v not in dims))
        for name, d in (('size', base), ('op', base + (place, others)),
                        ('op_lacks', base + (place, others, lacks))):
            lifts[f'{name}_{key.stage}'][(partner, d)].add(mine)
    for name, groups in lifts.items():
        report[f'lift_{name}'] = dict(classes=len(groups), violations=sum(len(v) > 1 for v in groups.values()))
    print(json.dumps(report))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
