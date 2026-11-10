"""Archived call DAGs: loading, reachability and exclusive-work accounting.

The archives are the C2-audit baselines (results/c2_bound/<case>/baseline.json.gz):
every memoised solve/group state with its frontier and exclusive work
counters, and every cache-query edge. Work removed by a change is the
exclusive work of states no longer reachable from the root, so shared
children are never double-counted.
"""
from collections import defaultdict
import gzip
import json
from pathlib import Path

from research.index_coupling.c2_bound_audit import COUNTERS

ARCHIVE = Path(__file__).resolve().parent.parent / 'results/c2_bound'
DOMAIN = 'halving'  # run_c2_bound_audit.py
CASES = ('ffn_forward_l1', 'ffn_forward_l2', 'ffn_forward_l3', 'ffn_forward_l4',
         'attention_forward_l2', 'attention_forward_l4', 'ffn_forward_l1_m8', 'ffn_forward_l2_m8')


def load(case):
    """(archive dict, nodes by id, children by parent id)."""
    with gzip.open(ARCHIVE / case / 'baseline.json.gz', 'rt') as stream:
        data = json.load(stream)
    nodes = {n['id']: n for n in data['nodes']}
    children = defaultdict(list)
    for e in data['edges']:
        children[e['parent']].append(e['child'])
    return data, nodes, children


def reach(root, children, terminal=frozenset(), cut=frozenset()):
    """States reachable from root; terminal states are reached but not expanded; cut edges are skipped."""
    seen, stack = set(), [root]
    while stack:
        i = stack.pop()
        if i in seen:
            continue
        seen.add(i)
        if i not in terminal:
            stack.extend(c for c in children.get(i, ()) if (i, c) not in cut)
    return seen


def removed(nodes, kept):
    """Fraction of each exclusive counter outside `kept`."""
    total = {k: sum(n['work'][k] for n in nodes.values()) for k in COUNTERS}
    left = {k: sum(nodes[i]['work'][k] for i in kept) for k in COUNTERS}
    return {k: round(1 - left[k] / total[k], 4) if total[k] else None for k in COUNTERS}


def terminal_work(data, nodes, children, terminal):
    """Work removed when `terminal` states are answered without expanding them."""
    return removed(nodes, reach(data['root'], children, terminal) - set(terminal))
