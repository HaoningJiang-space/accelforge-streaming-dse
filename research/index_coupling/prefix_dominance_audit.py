"""Read-only one/two-loop convergence census; see PREFIX_DOMINANCE_PROTOCOL.md.

python -m research.index_coupling.prefix_dominance_audit --out NEW_DIRECTORY
"""
import argparse
import ast
from collections import Counter, defaultdict
from functools import wraps
import gzip
import hashlib
from itertools import product
import json
from math import prod
import os
from pathlib import Path

from .c2_bound_audit import (BaselineRecorder, COUNTERS, dominates, frontier,
                             state, state_key, transformed)
from .census_tools import graph_of
from .graph.curve import tile_sizes
from .simulate_nest import simulate

HERE = Path(__file__).resolve().parent
CASES = ('ffn_forward_l1_m8', 'ffn_forward_l2_m8', 'ffn_training_l1', 'fork_kki')
TAG = '_audit_state'
PROTOCOL_COMMIT = '3628f51d'


def recover_actions(graph, data):
    """Recover every actual loop choice, including anchors, from its states."""
    nodes = {n['id']: n for n in data['nodes']}
    outgoing = defaultdict(list)
    edge_pairs = set()
    for edge in data['edges']:
        outgoing[edge['parent']].append(edge)
        edge_pairs.add((edge['parent'], edge['child']))
    names = sorted(graph.sizes)
    actions, grouped = [], defaultdict(list)
    for pid, parent in nodes.items():
        s = parent['state']
        if s['stage'] != 'group':
            continue
        ops, ext, resident = tuple(s['ops']), tuple(s['ext']), set(s['external'])
        tensors = graph.tensors(ops)
        dims = {t: set(graph.dims(t)) for t in tensors}
        sizes = dict(zip(names, ext))
        size = lambda t: prod(sizes[v] for v in dims[t])
        live = tensors - resident
        if all(size(t) == 1 for t in live):
            continue
        made = {graph.output(o) for o in ops}
        inside = made & {t for o in ops for t in graph.access[o] if t != graph.output(o)}
        common = set.intersection(*(graph.rank_vars((o,)) for o in ops))
        axes = {v for v in common if sizes[v] > 1 and all(v in dims[t] for t in inside - resident)}
        expected = set()
        for v in axes:
            lacking = sorted(t for t in live if v not in dims[t])
            for b in tile_sizes(sizes[v]):
                for bits in product((False, True), repeat=len(lacking)):
                    expected.add((v, b, tuple(t for t, yes in zip(lacking, bits) if yes)))
        recovered = set()
        actual_points = []
        for edge in outgoing[pid]:
            cs = nodes[edge['child']]['state']
            assert cs['stage'] == 'solve' and tuple(cs['ops']) == ops and not cs['constrained']
            changed = [i for i, (a, b) in enumerate(zip(ext, cs['ext'])) if a != b]
            assert len(changed) == 1
            i = changed[0]
            v, b = names[i], cs['ext'][i]
            lacking = {t for t in live if v not in dims[t]}
            kept = set(cs['external']) - resident
            assert kept <= lacking and resident <= set(cs['external'])
            assert tuple(cs['owned']) == tuple(s['owned']) and edge['calls'] == 1
            recovered.add((v, b, tuple(sorted(kept))))
            r = sizes[v] // b
            a = sum(size(t) for t in kept)
            d = (r - 1) * sum((2 if t in made else 1) * size(t) for t in lacking - kept)
            aid = len(actions)
            actions.append(dict(id=aid, parent=pid, child=edge['child'], axis=v, tile=b,
                                kept=sorted(kept), refetched=sorted(lacking-kept), a=a, d=d, r=r))
            grouped[pid].append(aid)
            actual_points.extend(transformed(nodes[edge['child']]['points'], a, d, r))
        assert recovered == expected, (pid, recovered ^ expected)
        assert frontier(actual_points) == frontier(parent['points']), pid
    assert len(actions) == data['stats']['loop_choices']

    # The only allowed bridge is the observed whole-span singleton partition.
    lookup = {state_key(n['state']): i for i, n in nodes.items()}
    bridges = {}
    for sid, node in nodes.items():
        s = node['state']
        if s['stage'] != 'solve' or s['constrained']:
            continue
        gid = lookup.get(state_key(dict(s, stage='group')))
        if gid is not None and (sid, gid) in edge_pairs:
            bridges[sid] = gid
    return nodes, actions, grouped, bridges


def census(graph, data):
    nodes, actions, grouped, bridges = recover_actions(graph, data)
    counts, strata = Counter(), defaultdict(Counter)
    examples = {}
    point_sets = {i: {tuple(p) for p in n['points']} for i, n in nodes.items()}
    propagated_bad = set()
    propagation = Counter()
    for pid, aids in grouped.items():
        buckets = defaultdict(list)
        for aid in aids:
            a = actions[aid]
            buckets[a['child']].append(((a['a'], a['d'], a['r']), (aid,)))
            gid = bridges.get(a['child'])
            for bid in grouped.get(gid, ()):
                b = actions[bid]
                label = (a['a'] + b['a'], a['d'] + a['r'] * b['d'], a['r'] * b['r'])
                buckets[b['child']].append((label, (aid, bid)))
        start = nodes[pid]['state']
        span = 'single_op' if len(start['ops']) == 1 else 'multi_op'
        for end, paths in buckets.items():
            stop = nodes[end]['state']
            assert start['ops'] == stop['ops'] and start['owned'] == stop['owned']
            assert all(a % b == 0 for a, b in zip(start['ext'], stop['ext']))
            r_fixed = prod(a // b for a, b in zip(start['ext'], stop['ext']))
            assert all(label[2] == r_fixed for label, _ in paths)
            labels = sorted({label for label, _ in paths})
            pareto, best_d = set(), float('inf')
            for label in labels:
                if label[1] < best_d:
                    pareto.add(label)
                    best_d = label[1]
            seen, kept_paths, strict_paths = set(), [], []
            bucket_counts = Counter(buckets=1, convergent_buckets=int(len(paths) > 1),
                                    distinct_labels=len(labels), pareto_labels=len(pareto),
                                    incomparable_buckets=int(len(pareto) > 1), paths=len(paths))
            for label, path in paths:
                length = 'one_loop' if len(path) == 1 else 'two_loops'
                category = ('direct' if len(path) == 1 else
                            'same_axis' if actions[path[0]]['axis'] == actions[path[1]]['axis'] else 'distinct_axes')
                if label not in pareto:
                    status = 'strictly_dominated'
                    strict_paths.append((label, path))
                elif label in seen:
                    status = 'duplicate_survivor'
                else:
                    status = 'kept'
                    seen.add(label)
                    kept_paths.append((label, path))
                bucket_counts[status] += 1
                bucket_counts[length] += 1
                for name in (span, category, span + ':' + category):
                    strata[name]['paths'] += 1
                    strata[name][status] += 1
            points = nodes[end]['points']
            if len(paths) > 1:
                before = frontier(p for (a, d, r), _ in paths for p in transformed(points, a, d, r))
                after = frontier(p for (a, d, r), _ in kept_paths for p in transformed(points, a, d, r))
                assert before == after, (pid, end)
                assert dominates(frontier(nodes[pid]['points']), before)
                bucket_counts['envelopes_checked'] += 1
            bucket_counts['expanded_point_instances'] = len(points) * len(paths)
            bucket_counts['remaining_expanded_point_instances'] = len(points) * len(kept_paths)
            counts.update(bucket_counts)
            # Diagnostic added after the frozen local census: distinguish
            # expanded path points from candidates actually returned by the
            # intermediate solve and generated by the original parent group.
            for _, path in strict_paths:
                if len(path) != 2:
                    continue
                a, b = (actions[i] for i in path)
                for c, q in nodes[end]['points']:
                    propagation['strict_expanded_points'] += 1
                    inner = (b['a'] + c, b['d'] + b['r'] * q)
                    if inner not in point_sets[a['child']]:
                        propagation['already_filtered_by_intermediate'] += 1
                        continue
                    propagation['surviving_intermediate_path_instances'] += 1
                    propagated_bad.add((a['id'], *inner))
                    parent_point = (a['a'] + inner[0], a['d'] + a['r'] * inner[1])
                    assert parent_point not in point_sets[pid], (pid, end, parent_point)
            # Save one inspectable example for each span/axis category.
            for label, path in strict_paths:
                category = 'same_axis' if len(path) == 2 and actions[path[0]]['axis'] == actions[path[1]]['axis'] else 'distinct_axes'
                key = span + ':' + category
                if key in examples:
                    continue
                better = next((l, p) for l, p in kept_paths if l[0] <= label[0] and l[1] <= label[1])
                examples[key] = dict(start=start, end=stop, dominated_label=label,
                                     surviving_label=better[0], dominated_steps=[actions[i] for i in path],
                                     surviving_steps=[actions[i] for i in better[1]])
    assert counts['paths'] == counts['strictly_dominated'] + counts['duplicate_survivor'] + counts['kept']
    generated = sum(len(nodes[a['child']]['points']) for a in actions)
    assert generated == sum(n['work']['pareto_candidates'] for n in nodes.values() if n['state']['stage'] == 'group')
    propagation.update(unique_actual_parent_candidates=len(propagated_bad), original_group_candidates=generated,
                       original_all_pareto_candidates=data['stats']['pareto_candidates'])
    return dict(original_states=len(nodes), original_loop_choices=len(actions),
                zero_cost_bridges=len(bridges), counts=dict(counts), strata=dict(strata), examples=examples,
                post_hoc_parent_candidate_attribution=dict(propagation),
                actual_online_edges_removed=0, actual_saved_cache_misses=0,
                work_note='Expanded point instances are hypothetical two-step expansion work, not original solver counters.')


def witness_control(graph, data):
    """Track states of selected root witnesses without changing their choices."""
    nodes = {n['id']: n for n in data['nodes']}
    ids = {state_key(n['state']): i for i, n in nodes.items()}

    def tagged(stage):
        def decorate(fn):
            @wraps(fn)
            def run(ops, ext, external, owned, *tail):
                ident = ids[state_key(state(stage, ops, ext, external, owned, bool(tail and tail[0])))]
                result = fn(ops, ext, external, owned, *tail)
                return tuple((c, q, ns['cat'](((TAG, ident),), w)) for c, q, w in result)
            return run
        return decorate

    path = HERE / 'graph/curve.py'
    tree = ast.parse(path.read_text(), filename=str(path))
    found = set()
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name in ('_solve', '_group_curve'):
            stage = 'solve' if fn.name == '_solve' else 'group'
            fn.decorator_list.append(ast.Call(ast.Name('_tagged', ast.Load()), [ast.Constant(stage)], []))
            found.add(stage)
    assert found == {'solve', 'group'}
    ns = dict(__name__='research.index_coupling.graph._prefix_witness_audit',
              __package__='research.index_coupling.graph', _tagged=tagged)
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), ns)
    stats = {}
    points = ns['curve'](graph, partitions='dp', scalar_leaf='v2', witness=True, stats=stats)
    assert [tuple(p[:2]) for p in points] == [tuple(p[:2]) for p in data['points']]
    assert all(stats[k] == data['stats'][k] for k in COUNTERS)
    used, replays = set(), []
    for c, q, notes in points:
        selected = {note[1] for note in notes if note[0] == TAG}
        used.update(selected)
        native = tuple(note for note in notes if note[0] != TAG)
        replay = simulate(graph, native, scalar_leaf='v2')
        assert replay['valid'] and (replay['peak'], replay['traffic']) == (c, q)
        replays.append(dict(capacity=c, traffic=q, selected_states=len(selected), exact=True))
    attached = {k: sum(nodes[i]['work'][k] for i in used) for k in COUNTERS}
    return dict(root_points=len(points), replays=replays, union_states=len(used),
                total_states=len(nodes), original_work_on_union=attached,
                original_work_fraction={k: attached[k] / data['stats'][k] if data['stats'][k] else None for k in COUNTERS},
                note='Original exclusive work on chosen-witness states; not minimum mapping-generation work or an achievable pruning rate.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    hashes = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in
              ('graph/curve.py', 'c2_bound_audit.py', 'census_tools.py', 'simulate_nest.py',
               'prefix_dominance_audit.py', 'PREFIX_DOMINANCE_PROTOCOL.md')}
    for case in CASES:
        graph = graph_of(case)
        path = HERE / 'results/c2_bound' / case / 'baseline.json.gz'
        if case == 'fork_kki':
            data = BaselineRecorder().run(graph)
            path = args.out / 'fork_kki_baseline.json.gz'
            path.write_bytes(gzip.compress(json.dumps(data).encode(), mtime=0))
        else:
            data = json.loads(gzip.decompress(path.read_bytes()))
        assert data['grammar'] == 'v2'
        record = dict(case=case, protocol_commit=PROTOCOL_COMMIT,
                      pythonhashseed=os.environ.get('PYTHONHASHSEED', 'unset'),
                      source_sha256=hashes, archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      census=census(graph, data))
        print(json.dumps(dict(case=case, phase='census', **record['census']['counts'])), flush=True)
        (args.out / (case + '.json')).write_text(json.dumps(record, indent=2) + '\n')
        record['witness_control'] = witness_control(graph, data)
        (args.out / (case + '.json')).write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps(dict(case=case, phase='witness', union_states=record['witness_control']['union_states'],
                              replayed=record['witness_control']['root_points'])), flush=True)


if __name__ == '__main__':
    main()
