"""Upper bound on symmetry redundancy inside an archived fixed-order call DAG.

States are mapped by certified whole-graph automorphisms (unified_search). A
state whose image is another archived state with an equal frontier is
redundant: a quotient would answer it by renaming. The redundant share is the
exclusive work of every orbit member except the first; it is an upper bound,
since fixed-order spans may still need their own parents.
"""
import gzip
import json
import sys

from research.index_coupling.c2_bound_audit import COUNTERS
from research.index_coupling.decode_census import CASES
from research.index_coupling.unified_search import certified_automorphisms


def image(graph, state, mapping):
    order = {o: i for i, o in enumerate(graph.ops)}
    ops = tuple(sorted((mapping.ops[o] for o in state['ops']), key=order.__getitem__))
    rename = lambda ts: tuple(sorted(mapping.tensors.get(t, t) for t in ts))
    return (state['stage'], ops, tuple(state['ext']), rename(state['external']), rename(state['owned']),
            state['constrained'])


def key(state):
    return (state['stage'], tuple(state['ops']), tuple(state['ext']), tuple(sorted(state['external'])),
            tuple(sorted(state['owned'])), state['constrained'])


def main(out, case):
    builder, m = CASES[case]
    graph = builder(m)
    group, tested = certified_automorphisms(graph)
    with gzip.open(f'{out}/{case}.baseline.json.gz', 'rt') as stream:
        nodes = json.load(stream)['nodes']
    by_key = {key(n['state']): n for n in nodes}
    seen, redundant, mismatched = set(), {k: 0 for k in COUNTERS}, 0
    for n in nodes:
        k = key(n['state'])
        if k in seen:
            continue
        orbit = {image(graph, n['state'], g) for g in group} & by_key.keys()
        members = sorted(orbit)
        frontiers = {json.dumps(by_key[o]['points']) for o in members}
        seen |= orbit
        if len(frontiers) != 1:
            mismatched += 1
            continue
        for o in members[1:]:
            for c in COUNTERS:
                redundant[c] += by_key[o]['work'][c]
    total = {c: sum(n['work'][c] for n in nodes) for c in COUNTERS}
    print(json.dumps(dict(case=case, automorphisms=len(group), tested=tested, states=len(nodes),
                          mismatched_orbits=mismatched,
                          redundant_share={c: round(redundant[c] / total[c], 4) if total[c] else None
                                           for c in COUNTERS})))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
