"""Check the chain zero-traffic lower bound (CHAIN_THRESHOLD.md) on archived states.

For every node of a C2-audit baseline (results/c2_bound/<case>/baseline.json.gz)
that qualifies, computes L(S) and compares it with the node's actual
zero-extra-traffic capacity, the least capacity with internal traffic 0. A node
qualifies when:
- the case is a forward FFN or attention stack;
- the M extent is 1;
- no resident tensor carries M (no resident activation);
- the frontier has a point with zero extra traffic.

A violation (L > actual) would refute the theorem or this implementation.

Usage: python -m research.index_coupling.check_chain_threshold CASE [CASE ...]
"""
import gzip
import json
from pathlib import Path
import sys

from research.index_coupling.census_tools import extents, graph_of, size_at

HERE = Path(__file__).resolve().parent


def chain_bound(graph, state, row='M'):
    """L(S) of CHAIN_THRESHOLD.md, or None if the state does not qualify."""
    ext, resident = extents(graph, state), set(state['external'])
    if ext[row] != 1 or any(row in graph.dims(t) for t in resident):
        return None
    chain, contractions = {}, []
    for op in state['ops']:
        access = graph.access[op]
        out = graph.output(op)
        weights = [t for t in access if row not in access[t]]
        inputs = [t for t in access if t != out and row in access[t]]
        if len(weights) == 1 and len(inputs) == 1:
            contractions.append((inputs[0], out, weights[0]))
        elif not weights and len(inputs) == 1:
            chain[out] = chain.get(inputs[0], inputs[0])  # elementwise: same vector
        else:
            return None
    vec = lambda t: chain.get(t, t)
    size = lambda t: size_at(graph.dims(t), ext)
    s = [int(w not in resident) for _, _, w in contractions]
    slots = max(sum(t not in resident for t in graph.access[op]) for op in state['ops'])
    bound = slots
    for j, (a, b, _) in enumerate(contractions):
        pred = j > 0 and vec(contractions[j - 1][1]) == vec(a)
        succ = j + 1 < len(contractions) and vec(contractions[j + 1][0]) == vec(b)
        both = size(a) + size(b) + s[j]
        ti = (min(both, size(a) + size(contractions[j + 1][1]) + 1 + s[j + 1]) if succ
              else size(a) + 1 + s[j])
        to = (min(both, size(b) + size(contractions[j - 1][0]) + 1 + s[j - 1]) if pred
              else size(b) + 1 + s[j])
        bound = max(bound, min(ti, to))
    return bound


def main(cases):
    for case in cases:
        graph = graph_of(case)
        with gzip.open(HERE / 'results/c2_bound' / case / 'baseline.json.gz', 'rt') as stream:
            nodes = json.load(stream)['nodes']
        counts = dict(nodes=len(nodes), qualifying=0, equal=0, below=0, violations=0)
        gaps, example = {}, None
        for node in nodes:
            zero = [c for c, q in node['points'] if q == 0]
            bound = chain_bound(graph, node['state']) if zero else None
            if bound is None:
                continue
            actual = min(zero)
            counts['qualifying'] += 1
            counts['equal'] += bound == actual
            counts['below'] += bound < actual
            gaps[actual - bound] = gaps.get(actual - bound, 0) + 1
            if bound > actual:
                counts['violations'] += 1
                example = example or dict(state=node['state'], points=node['points'], bound=bound)
        print(json.dumps(dict(case=case, **counts, gap_histogram=dict(sorted(gaps.items())),
                              violation_example=example)))


if __name__ == '__main__':
    main(sys.argv[1:])
