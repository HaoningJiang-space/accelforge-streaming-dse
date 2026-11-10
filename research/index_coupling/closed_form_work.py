"""Exclusive work removed by treating closed-form solve states as terminal (CONTRACTION_ORACLE.md §15).

Reads the archived C2-audit call DAGs (results/c2_bound/<case>/baseline.json.gz).
A node is terminal when elementwise_chain.archived_chain gives it a closed
form (unit M). Its own work and every descendant no longer reachable from the
root through non-terminal nodes are removed. Shared children reachable by
another path are kept, so nothing is double-counted. Work is reported per
counter of the archived per-node ledger.

Usage: python -m research.index_coupling.closed_form_work CASE [CASE ...]
"""
import gzip
import json
from pathlib import Path
import sys

from research.index_coupling.census_tools import graph_of
from research.index_coupling.elementwise_chain import archived_chain

R = Path(__file__).resolve().parent / 'results/c2_bound'
COUNTERS = ('dp_transitions', 'loop_choices', 'pareto_candidates', 'merge_inputs')


def main(cases):
    for case in cases:
        g = graph_of(case)
        data = json.load(gzip.open(R / case / 'baseline.json.gz', 'rt'))
        nodes = {n['id']: n for n in data['nodes']}
        children = {}
        for e in data['edges']:
            children.setdefault(e['parent'], []).append(e['child'])
        terminal = {i for i, n in nodes.items() if archived_chain(g, n['state']) is not None}
        reach, stack = set(), [data['root']]
        while stack:
            i = stack.pop()
            if i in reach:
                continue
            reach.add(i)
            if i not in terminal:
                stack.extend(children.get(i, ()))
        kept = reach - terminal
        total = {k: sum(n['work'].get(k, 0) for n in nodes.values()) for k in COUNTERS}
        left = {k: sum(nodes[i]['work'].get(k, 0) for i in kept) for k in COUNTERS}
        out = dict(case=case, nodes=len(nodes), terminal=len(terminal), terminal_reached=len(terminal & reach),
                   nodes_left=len(kept),
                   removed={k: round(1 - left[k] / total[k], 4) if total[k] else None for k in COUNTERS})
        print(json.dumps(out), flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
