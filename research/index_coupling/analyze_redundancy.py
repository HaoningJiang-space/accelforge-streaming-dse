"""Which parts of a conditional state determine its frontier? Field ablation.

Reads states saved by redundancy_census.py (or audit_residency_states.py) and,
for several projections of the alpha-canonical state, counts classes and
violations (classes whose members have different frontiers). A projection
with zero violations is empirically sufficient on that census; one with
violations is refuted by a concrete pair, which is printed.

Projections:
- alpha: full joint tensor/rank renaming (redundancy_census.signature);
- no_owned: drop final-write ownership;
- external_sizes: keep the span but replace WHICH tensors are resident by the
  multiset of their (size, role) - the count-style summary;
- no_incidence: keep per-tensor (size, role, resident, owned) and per-operator
  arity, but drop which operator touches which tensor through which rank.

Usage: python -m research.index_coupling.analyze_redundancy STATES.jsonl.gz CASE
  CASE names redundancy_census.CASES or audit_residency_states.CASES.
"""
from collections import defaultdict
import gzip
import json
from math import prod
import sys

from research.index_coupling.audit_residency_states import CASES as FORKS
from research.index_coupling.graph.model import fork
from research.index_coupling.redundancy_census import CASES, signature


def graph_of(case):
    if case in CASES:
        builder, args = CASES[case]
        return builder(*args)
    return fork(*FORKS[case])


def tensor_facts(graph, state):
    ext = dict(zip(sorted(graph.sizes), state['ext']))
    produced, consumed = graph.produced(), graph.consumed()
    facts = {}
    for op in state['ops']:
        for t, dims in graph.access[op].items():
            facts[t] = (prod(ext[v] for v in dims), t in produced, t in consumed, len(graph.consumers(t)))
    return facts


def projections(graph, state):
    alpha = signature(graph, state, True)
    facts = tensor_facts(graph, state)
    resident = sorted(facts[t] for t in state['external'])
    owned = sorted(facts[t] for t in state['owned'])
    arity = tuple(len(graph.access[op]) for op in state['ops'])
    return dict(
        alpha=alpha,
        no_owned=alpha[:6],
        external_sizes=alpha[:5] + (tuple(resident), alpha[6]),
        no_incidence=(state['stage'], state['constrained'], arity,
                      tuple(sorted((f, t in state['external'], t in state['owned']) for t, f in facts.items()))),
    )


def main(path, case):
    graph = graph_of(case)
    with gzip.open(path, 'rt') as stream:
        states = [json.loads(line) for line in stream]
    classes = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for s in states:
        frontier = tuple(map(tuple, s['points']))
        for name, key in projections(graph, s).items():
            classes[name][key][frontier].append(s)
    report = dict(case=case, keys=len(states))
    for name, groups in classes.items():
        bad = [g for g in groups.values() if len(g) > 1]
        report[name] = dict(classes=len(groups), violations=len(bad))
        if bad:
            (fa, sa), (fb, sb) = list(bad[0].items())[:2]
            report[name]['example'] = [dict(ops=sa[0]['ops'], ext=sa[0]['ext'], external=sa[0]['external'],
                                            owned=sa[0]['owned'], stage=sa[0]['stage'], points=fa),
                                       dict(ops=sb[0]['ops'], ext=sb[0]['ext'], external=sb[0]['external'],
                                            owned=sb[0]['owned'], stage=sb[0]['stage'], points=fb)]
    print(json.dumps(report))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
