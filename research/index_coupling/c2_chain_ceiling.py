"""Ideal-exclusion ceiling of C2 clipped by the chain threshold (CHAIN_THRESHOLD.md).

The chain theorem bounds only the zero-extra capacity L_K of a candidate
child. Below L_K its extra traffic is positive, so at least one element, but
nothing more is known. The strongest valid clip of the C2 anchor curve q_* is
therefore

    B_K(c) = infinity           if c < slots_K,
             max(q_*(c), 1)     if slots_K <= c < L_K,
             q_*(c)             otherwise.

This counts, per case, the proper retention choices whose parent-level bound
(A_K + c, D_K + r B_K(c)) is dominated by the final parent group frontier
(ideal exclusions). The same count is made for the existing slot bound. Only
the archived C2 records are read; nothing is searched.

Usage: python -m research.index_coupling.c2_chain_ceiling CASE [CASE ...]
"""
import gzip
import json
from pathlib import Path
import sys

from research.index_coupling.c2_bound_audit import dominates, frontier
from research.index_coupling.census_tools import graph_of
from research.index_coupling.check_chain_threshold import chain_bound
from research.index_coupling.graph.analysis import traffic_at

HERE = Path(__file__).resolve().parent


def clipped(anchor, slots, threshold):
    # Every capacity where B_K changes: anchor breakpoints, slots_K and L_K.
    caps = sorted({c for c, _ in anchor} | {slots, threshold})
    points = []
    for c in caps:
        if c < slots:
            continue
        q = traffic_at(c, anchor)
        if threshold is not None and c < threshold:
            q = max(q, 1)
        points.append((c, q))
    return frontier(points)


def main(cases):
    for case in cases:
        graph = graph_of(case)
        root = HERE / 'results/c2_bound' / case
        with gzip.open(root / 'baseline.json.gz', 'rt') as stream:
            nodes = {n['id']: n for n in json.load(stream)['nodes']}
        counts = dict(proper=0, chain_applicable=0, ideal_slots=0, ideal_chain=0, raised=0)
        with gzip.open(root / 'choices.jsonl.gz', 'rt') as stream:
            for line in stream:
                r = json.loads(line)
                counts['proper'] += 1
                parent, child = nodes[r['parent']], nodes[r['child']]
                parent_curve = frontier(parent['points'])
                slots_bound = [tuple(p) for p in r['slots_bound']]
                counts['ideal_slots'] += dominates(parent_curve, slots_bound)
                threshold = chain_bound(graph, child['state'])
                if threshold is None:
                    counts['ideal_chain'] += dominates(parent_curve, slots_bound)
                    continue
                counts['chain_applicable'] += 1
                # Recover the anchor's child curve from the raw parent-level bound.
                alloc, extra = r['allocation'], r['extra']
                trips = parent['state']['ext'][sorted(graph.sizes).index(r['axis'])] // r['tile']
                anchor = [((c - alloc), (q - extra) // trips) for c, q in r['raw']]
                child_bound = clipped(anchor, r['slots'], threshold)
                bound = frontier((alloc + c, extra + trips * q) for c, q in child_bound)
                counts['raised'] += bound != tuple(slots_bound)
                assert dominates(bound, [tuple(p) for p in r['actual']]), (case, r)
                counts['ideal_chain'] += dominates(parent_curve, bound)
        print(json.dumps(dict(case=case, **counts)))


if __name__ == '__main__':
    main(sys.argv[1:])
