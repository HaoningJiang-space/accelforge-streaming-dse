"""Independent accounting review of the closed-form terminal projection.

Run from the repository root:
  python -m research.index_coupling.audit_closed_terminals --out NEW.json

No solver or archive is modified. Returned analytic responses remain queries;
only their original recursive work is removed. Formula validation is offline
and uses archived capacity ranges, so it is not an online timing benchmark.
"""
import argparse
from collections import defaultdict, deque
import gzip
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from research.index_coupling.census_tools import graph_of
from research.index_coupling.elementwise_chain import archived_chain, predict
from research.index_coupling.graph.analysis import traffic_at


HERE = Path(__file__).resolve().parent
COUNTERS = ('dp_transitions', 'loop_choices', 'pareto_candidates', 'merge_inputs')
SOURCE_COMMIT = '39e592085d6e5522f7c916b252de25564ea69187'


def audit(case, expected):
    path = HERE / 'results/c2_bound' / case / 'baseline.json.gz'
    data = json.load(gzip.open(path, 'rt'))
    assert data['grammar'] == 'v2'
    nodes = {n['id']: n for n in data['nodes']}
    graph = graph_of(case)
    forms = {}
    for i, node in nodes.items():
        form = archived_chain(graph, node['state'])
        if form is not None:
            kinds, sizes, first, last, streamed = form
            forms[i] = (tuple(kinds), tuple(sizes), first, last, tuple(streamed))

    # Topological propagation independently checks root reachability after
    # terminal calls stop expanding. Keep all incoming paths to shared nodes.
    children = defaultdict(set)
    indegree = dict.fromkeys(nodes, 0)
    for edge in data['edges']:
        p, c = edge['parent'], edge['child']
        if c not in children[p]:
            children[p].add(c)
            indegree[c] += 1
    queue = deque(i for i, degree in indegree.items() if degree == 0)
    baseline_reach, reach = {data['root']}, {data['root']}
    visited = 0
    while queue:
        p = queue.popleft()
        visited += 1
        for c in children[p]:
            if p in baseline_reach:
                baseline_reach.add(c)
            if p in reach and p not in forms:
                reach.add(c)
            indegree[c] -= 1
            if indegree[c] == 0:
                queue.append(c)
    assert visited == len(nodes), 'call graph must be acyclic'
    assert baseline_reach == set(nodes)
    terminals = reach & forms.keys()
    ordinary = reach - terminals
    unreachable = nodes.keys() - reach

    # Equal structural keys may be evaluated once. Compare against every
    # corresponding archived response, including every integer capacity.
    caps_by_form = {}
    for i in terminals:
        points = nodes[i]['points']
        assert points[-1][1] == 0, 'tail check needs a zero-extra-traffic plateau'
        caps_by_form[forms[i]] = max(caps_by_form.get(forms[i], 0), max(c for c, _ in points) + 2)
    responses = {}
    for form, cap in caps_by_form.items():
        kinds, sizes, first, last, streamed = form
        responses[form] = [predict(kinds, sizes, c, 'halving', first, last, streamed)
                           for c in range(cap + 1)]
    comparisons = 0
    for i in terminals:
        points = nodes[i]['points']
        for c, value in enumerate(responses[forms[i]]):
            assert value == traffic_at(c, points), (case, i, c, value, points)
            comparisons += 1

    counters = {}
    for key in COUNTERS:
        total = sum(n['work'][key] for n in nodes.values())
        assert total == data['stats'][key]
        remaining = sum(nodes[i]['work'][key] for i in ordinary)
        terminal_work = sum(nodes[i]['work'][key] for i in terminals)
        unreachable_work = sum(nodes[i]['work'][key] for i in unreachable)
        assert remaining + terminal_work + unreachable_work == total
        fraction = 1 - remaining / total if total else None
        assert (round(fraction, 4) if fraction is not None else None) == expected['removed'][key]
        counters[key] = dict(original=total, remaining_recursive=remaining,
                             replaced_terminal=terminal_work, unreachable=unreachable_work,
                             removed_fraction=fraction)
    assert len(ordinary) == expected['nodes_left']
    assert len(terminals) == expected['terminal_reached']
    assert len(forms) == expected['terminal']
    return dict(case=case, archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                original_nodes=len(nodes), eligible_terminals=len(forms),
                returned_analytic_queries=len(terminals), ordinary_recursive_queries=len(ordinary),
                total_reachable_queries=len(reach), unreachable_nodes=len(unreachable),
                unique_analytic_keys=len(caps_by_form),
                analytic_scalar_evaluations=sum(len(v) for v in responses.values()),
                integer_capacity_comparisons=comparisons, counters=counters,
                formula_cost_charged=False, witness_synthesis_checked=False)


def coupling_example():
    from research.index_coupling.chain2_closed_form import grammar_curve, predict as pair
    from research.index_coupling.matmul_keep import predict as single
    points = grammar_curve(4, 4, 4, 'halving')
    actual = traffic_at(3, points) - 8
    analytic = pair(4, 4, 4, 3, 'halving')
    lower = 2 * single((1, 4, 4), ('X', 'Y'), 3, 'halving')
    assert actual == analytic == 12 and lower == 8
    return dict(shape=[4, 4, 4], capacity=3, weights_resident=True,
                compulsory_root_traffic=8, grammar_root_curve=points,
                chain_extra=actual, sum_operator_lower_bound=lower,
                note='Post-hoc diagnostic, not a frozen prediction or new theorem.')


def audit_operator_bound():
    from research.index_coupling import op_projection as model
    # Cache identical single-operator scalar queries during this read-only
    # audit. This changes neither bound values nor the solver being reviewed.
    model.op_response = lru_cache(maxsize=None)(model.op_response)
    archived = [json.loads(line) for line in
                (HERE / 'results/contraction_oracle/op_projection_check.jsonl').read_text().splitlines()]
    results = []
    for expected in archived:
        case = expected['case']
        graph = graph_of(case)
        path = HERE / 'results/c2_bound' / case / 'baseline.json.gz'
        data = json.load(gzip.open(path, 'rt'))
        counts = dict(qualifying=0, multi_row=0, violations=0, exact=0, positive=0)
        comparisons = 0
        for node in data['nodes']:
            ops = model.chain_ops(graph, node['state'])
            if ops is None:
                continue
            counts['qualifying'] += 1
            counts['multi_row'] += node['state']['ext'][sorted(graph.sizes).index('M')] > 1
            points = node['points']
            caps = range(max(c for c, _ in points) + 3)
            lower = [model.bound(ops, c) for c in caps]
            actual = [traffic_at(c, points) for c in caps]
            counts['violations'] += any(l > a for l, a in zip(lower, actual))
            counts['exact'] += lower == actual
            counts['positive'] += any(0 < a < float('inf') for a in actual)
            comparisons += len(actual)
        assert all(counts[k] == expected[k] for k in counts), (case, counts, expected)
        results.append(dict(case=case, **counts, integer_capacity_comparisons=comparisons))
        print(json.dumps(dict(operator_case=case, **counts)), flush=True)
    totals = {k: sum(row[k] for row in results) for k in counts}
    totals['integer_capacity_comparisons'] = sum(row['integer_capacity_comparisons'] for row in results)
    return dict(results=results, totals=totals)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in (HERE / 'results/contraction_oracle/closed_form_work.jsonl').read_text().splitlines()]
    results = []
    for row in rows:
        result = audit(row['case'], row)
        results.append(result)
        print(json.dumps({k: result[k] for k in ('case', 'returned_analytic_queries',
                         'ordinary_recursive_queries', 'integer_capacity_comparisons')}), flush=True)
    output = dict(reviewed_commit=SOURCE_COMMIT, scope='Eight archived v2 halving-domain cases',
                  results=results, coupling_example=coupling_example(),
                  operator_bound=audit_operator_bound())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
