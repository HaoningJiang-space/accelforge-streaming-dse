"""Reproduce aggregate counters and one explicit coupled-loop slice from archives."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from math import prod
from pathlib import Path
import subprocess

from .workloads import JOIN_CASES as CASES, dag_graph as graph_for
from .audit_support import COUNTERS


def summarize(root):
    cases, common_hashes, revision = {}, None, None
    for name in CASES:
        directory = root/'results'/name
        summary = json.loads((directory/'summary.json').read_text())
        if common_hashes is None:
            common_hashes, revision = summary['source_sha256'], summary['revision']
            for source, digest in common_hashes.items():
                content = subprocess.check_output(['git', 'show', f'{revision}:{source}'])
                assert hashlib.sha256(content).hexdigest() == digest, source
        assert (common_hashes, revision) == (summary['source_sha256'], summary['revision'])
        totals, counts, ceilings = Counter(), Counter(), {}
        own_seconds = 0.
        for i, order in enumerate(summary['orders']):
            path = directory/f'order_{i}.json.gz'
            assert hashlib.sha256(path.read_bytes()).hexdigest() == order['archive_sha256']
            with gzip.open(path) as stream:
                archive = json.load(stream)
            data = archive['data']
            assert archive['order'] == order['order']
            assert data['frontier'] == [p['point'] for p in
                                        order['oracle_substitution_check']['witnesses']]
            for key in COUNTERS:
                assert sum(n['work'][key] for n in data['nodes']) == order['totals'][key]
            totals.update(order['totals'])
            counts.update({key: order[key] for key in ('comparisons', 'conditional_typed_checks',
                'states', 'component_queries', 'unique_component_keys', 'component_keys_not_in_baseline',
                'private_input_flip_pairs', 'unequal_parent_response_pairs')})
            counts['oracle_replacements'] += order['oracle_substitution_check']['replacements']
            counts['substituted_root_replays'] += order['oracle_substitution_check']['root_replays']
            seconds = sum(n['own_seconds'] for n in data['nodes'])
            own_seconds += seconds
            for label in ('coverage', 'dependency_preserving_ceiling', 'nonscalar_coverage',
                          'nonscalar_x_coverage'):
                ceiling = ceilings.setdefault(label, dict(work=Counter(), eligible=0, saved_own_seconds=0.))
                ceiling['work'].update(order[label]['removed_work'])
                ceiling['eligible'] += order[label]['eligible']
                ceiling['saved_own_seconds'] += seconds*order[label]['instrumented_own_seconds_fraction']
        for ceiling in ceilings.values():
            ceiling['fraction'] = {k: ceiling['work'][k]/totals[k] for k in COUNTERS}
            ceiling['instrumented_seconds_fraction'] = ceiling['saved_own_seconds']/own_seconds
        cases[name] = dict(orders=summary['searched_orders'], baseline_root_replays=summary['root_replays'],
                           counts=counts, totals=totals, ceilings=ceilings,
                           per_order=[dict(order=a['order'], eligible=a['comparisons'],
                            dp_ceiling=a['dependency_preserving_ceiling']['removed_fraction']['dp_transitions'])
                            for a in summary['orders']])

    # Retrospective diagnostic: all eight actual masks in one non-scalar-X
    # group, preserving the recorded operator order and write ownership.
    path = root/'results/two_stage_join/order_0.json.gz'
    with gzip.open(path) as stream:
        archive = json.load(stream)
    graph = graph_for('two_stage_join')
    nodes = {n['id']: n for n in archive['data']['nodes']}
    state = dict(stage='group', ops=['E0', 'H0', 'E1', 'H1'], ext=[1,1,2,2,2],
                 external=[], owned=['V0','V1'], constrained=False)
    parent = next(n for n in nodes.values() if n['state'] == state)
    sizes = dict(zip(sorted(graph.sizes), state['ext']))
    lacking = sorted(t for t in graph.tensors(state['ops']) if 'L' not in graph.dims(t))
    made = {graph.output(o) for o in state['ops']}
    rows, envelope = [], []
    for edge in archive['data']['edges']:
        if edge['parent'] != parent['id']:
            continue
        child = nodes[edge['child']]
        assert child['state']['ext'] == [1,1,2,1,2]
        keep = set(child['state']['external'])
        reservation = sum(prod(sizes[v] for v in graph.dims(t)) for t in keep)
        extra = sum((2 if t in made else 1)*prod(sizes[v] for v in graph.dims(t))
                    for t in set(lacking)-keep)
        transformed = [(reservation+c, extra+2*q) for c,q in child['points']]
        envelope.extend(transformed)
        rows.append(dict(keep=sorted(keep), child=child['points'], reservation=reservation,
                         outer_extra=extra, transformed=transformed))
    assert len(rows) == 2**len(lacking) == 8
    frontier, best = [], float('inf')
    for c,q in sorted(envelope):
        if q < best:
            frontier.append([c,q]); best = q
    assert frontier == parent['points']
    return dict(revision=revision, verified_source_files=len(common_hashes), cases=cases,
                diagnostic_loop=dict(source='results/two_stage_join/order_0.json.gz', state=state,
                    ranks=sorted(graph.sizes), rank='L', tile=1, trips=2, obligations=lacking,
                    rows=rows, recovered_group_frontier=frontier),
                interpretation='All fractions are optimistic work ceilings, not measured search speedups; '
                               'component keys absent from baseline are treated as free in the rewired ceiling.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(json.dumps(summarize(args.directory), indent=2)+'\n')
