"""Test candidate sufficient statistics of a conditional state (span, R).

Each candidate is an isomorphism-invariant label (Weisfeiler-Leman refinement)
of a typed graph built from the ordered span: operator nodes (labelled by
position), tensor nodes (size at the current extents, global role, owned) and
rank nodes (full size, current extent). Isomorphic states always get the same
label; non-isomorphic ones may collide, which only makes the test stricter.
A candidate is sufficient on a census when no label class contains two
different frontiers.

- symmetric: every tensor kept, external ones marked. Orbit-level version of
  redundancy_census.signature (removes rank/tensor symmetry only).
- residual: external tensors deleted; a rank survives only through the
  remaining tensors.
- residual_domain: external tensors deleted, but each operator keeps edges to
  its whole iteration domain (all ranks it accesses).

Usage: python -m research.index_coupling.sufficient_stat STATES.jsonl.gz CASE
"""
from collections import defaultdict
import gzip
import json
from math import prod
import sys

from research.index_coupling.analyze_redundancy import graph_of

TABLE = {}


def intern(label):
    return TABLE.setdefault(label, len(TABLE))


def wl(nodes, edges, rounds):
    adjacent = defaultdict(list)
    for a, b, kind in edges:
        adjacent[a].append((kind, b))
        adjacent[b].append((kind, a))
    labels = {n: intern(('init', l)) for n, l in nodes.items()}
    for _ in range(rounds):
        labels = {n: intern((labels[n], tuple(sorted((k, labels[m]) for k, m in adjacent[n]))))
                  for n in nodes}
    return tuple(sorted(labels.values()))


def statistic(graph, state, variant, facts):
    produced, consumed, consumers = facts
    ext = dict(zip(sorted(graph.sizes), state['ext']))
    external, owned = set(state['external']), set(state['owned'])
    nodes, edges = {}, []
    for i, op in enumerate(state['ops']):
        nodes[('op', op)] = ('op', i)
        out = graph.output(op)
        for t, dims in graph.access[op].items():
            if variant == 'residual_domain':
                for v in dims:
                    edges.append((('op', op), ('rank', v), 'domain'))
            if t in external and variant != 'symmetric':
                continue
            nodes[('t', t)] = ('t', prod(ext[v] for v in dims), t in produced, t in consumed,
                               consumers[t], t in external, t in owned)
            edges.append((('op', op), ('t', t), 'out' if t == out else 'in'))
            for v in dims:
                edges.append((('t', t), ('rank', v), 'carries'))
    for _, b, _ in edges:
        if b[0] == 'rank':
            nodes[b] = ('rank', graph.sizes[b[1]], ext[b[1]])
    return (state['stage'], state['constrained'], wl(nodes, edges, 4))


def main(path, case):
    graph = graph_of(case)
    facts = (graph.produced(), graph.consumed(),
             {t: len(graph.consumers(t)) for t in graph.tensors(graph.ops)})
    variants = ('symmetric', 'residual', 'residual_domain')
    classes = {v: defaultdict(set) for v in variants}
    examples = {}
    keys = 0
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            s = json.loads(line)
            keys += 1
            frontier = (s['stage'], tuple(map(tuple, s['points'])))
            for v in variants:
                key = statistic(graph, s, v, facts)
                group = classes[v][key]
                if group and frontier not in {f for f, _ in group} and v not in examples:
                    other = next(iter(group))
                    examples[v] = [other[1], dict(ops=s['ops'], ext=s['ext'], external=s['external'],
                                                  owned=s['owned'], stage=s['stage'], points=s['points'])]
                if frontier not in {f for f, _ in group}:
                    group.add((frontier, json.dumps(dict(ops=s['ops'], ext=s['ext'], external=s['external'],
                                                         owned=s['owned'], stage=s['stage'],
                                                         points=s['points']))))
    report = dict(case=case, keys=keys)
    for v in variants:
        report[v] = dict(classes=len(classes[v]), violations=sum(len(g) > 1 for g in classes[v].values()))
        if v in examples:
            a, b = examples[v]
            report[v]['example'] = [json.loads(a), b]
    print(json.dumps(report))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
