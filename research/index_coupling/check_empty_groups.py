"""Check the infeasible-group criterion (REMAINDER_LEMMAS.md, Lemma 2) on a census.

For every recorded group state, predicts emptiness without solving:
  empty  iff  some live tensor is not scalar, and no rank v common to all
  operators has extent > 1 and is carried by every non-resident tensor made
  and read inside the group.
Compares with the recorded frontier. Solve states are predicted nonempty.

Usage: python -m research.index_coupling.check_empty_groups STATES.jsonl.gz CASE
"""
import gzip
import json
from math import prod
import sys

from research.index_coupling.analyze_redundancy import graph_of


def predicted_empty(graph, state):
    if state['stage'] == 'solve':
        return False
    ops, external = state['ops'], set(state['external'])
    ext = dict(zip(sorted(graph.sizes), state['ext']))
    dims = {t: d for op in ops for t, d in graph.access[op].items()}
    live = set(dims) - external
    if all(prod(ext[v] for v in dims[t]) == 1 for t in live):
        return False
    common = set.intersection(*(graph.rank_vars((op,)) for op in ops))
    made = {graph.output(op) for op in ops}
    inside_made = {t for op in ops for t in list(graph.access[op])[:-1] if t in made} - external
    return not any(ext[v] > 1 and all(v in dims[t] for t in inside_made) for v in common)


def main(path, case):
    graph = graph_of(case)
    counts = dict(states=0, empty=0, predicted=0, false_empty=0, missed_empty=0)
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            s = json.loads(line)
            actual, predicted = not s['points'], predicted_empty(graph, s)
            counts['states'] += 1
            counts['empty'] += actual
            counts['predicted'] += predicted
            counts['false_empty'] += predicted and not actual
            counts['missed_empty'] += actual and not predicted
    print(json.dumps(dict(case=case, **counts)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
