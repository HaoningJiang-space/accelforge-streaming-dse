"""Bounded factorized loop closure; see LOOP_CLOSURE_PROTOCOL.md.

This opt-in, in-memory kernel preserves the original proper-partition DP.
It is not installed in graph/curve.py. Run through run_loop_closure_pilot.py
for process limits, fresh timings and archived outcomes.
"""
import ast
from collections import Counter, defaultdict
import copy
from functools import lru_cache
import gzip
import hashlib
import json
from math import prod
from pathlib import Path
import resource
import sys
import time

from .c2_bound_audit import BaselineRecorder
from .census_tools import graph_of
from .graph.curve import curve
from .graph.model import Graph
from .prefix_dominance_audit import recover_actions
from .simulate_nest import simulate

HERE = Path(__file__).resolve().parent
OPTIONS = dict(partitions='dp', scalar_leaf='v2')
WORK = ('dp_transitions', 'loop_choices', 'pareto_candidates', 'merge_inputs')


def graph_for(case):
    if case == 'prefix_control':
        return Graph(dict(M=4, D=1, F=4), [('E', {'X': ('M', 'D'), 'W': ('D', 'F'), 'Y': ('M', 'F')})])
    return graph_of(case)


def peak_mib():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (2**20 if sys.platform == 'darwin' else 2**10)


def census(case, depth):
    graph = graph_for(case)
    if case == 'prefix_control':
        data = BaselineRecorder().run(graph)
        digest = None
    else:
        path = (HERE / 'results/prefix_dominance/run4_seed0/fork_kki_baseline.json.gz' if case == 'fork_kki'
                else HERE / 'results/c2_bound' / case / 'baseline.json.gz')
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        data = json.loads(gzip.decompress(raw))
    setup_start = time.perf_counter()
    nodes, actions, grouped, bridges = recover_actions(graph, data)
    setup_seconds = time.perf_counter() - setup_start
    counts = Counter()

    @lru_cache(maxsize=None)
    def close(gid, remaining):
        candidates, raw_paths = defaultdict(list), Counter()
        for aid in grouped.get(gid, ()):
            a = actions[aid]
            candidates[a['child']].append((a['a'], a['d']))
            raw_paths[a['child']] += 1
            if remaining == 1 or a['child'] not in bridges:
                continue
            tail = close(bridges[a['child']], None if remaining is None else remaining - 1)
            for end, (labels, number) in tail.items():
                candidates[end].extend((a['a'] + x, a['d'] + a['r'] * y) for x, y in labels)
                raw_paths[end] += number
        out = {}
        for end, choices in candidates.items():
            best, kept = float('inf'), []
            for a, d in sorted(choices):
                if d < best:
                    kept.append((a, d))
                    best = d
            counts['label_candidates'] += len(choices)
            counts['retained_across_helper_rows'] += len(kept)
            out[end] = (tuple(kept), raw_paths[end])
        counts['helper_rows'] += 1
        counts['pairs_across_helper_rows'] += len(out)
        return out

    start = time.perf_counter()
    hist, pairs, labels, paths = Counter(), 0, 0, 0
    for gid in grouped:
        row = close(gid, depth)
        pairs += len(row)
        for values, number in row.values():
            hist[len(values)] += 1
            labels += len(values)
            paths += number
    seconds = time.perf_counter() - start
    if depth == 2 and case != 'prefix_control':
        previous = json.loads((HERE / 'results/prefix_dominance/run4_seed0' / (case + '.json')).read_text())
        expected = previous['census']['counts']
        assert (pairs, labels, paths) == (expected['buckets'], expected['pareto_labels'], expected['paths'])
    control = None
    if case == 'prefix_control' and depth is None:
        start_ids = [i for i in grouped if tuple(nodes[i]['state']['ext']) == (1, 4, 4)
                     and not nodes[i]['state']['external'] and not nodes[i]['state']['owned']]
        assert len(start_ids) == 1
        control = []
        for end, (values, _) in close(start_ids[0], None).items():
            s = nodes[end]['state']
            if tuple(s['ext']) == (1, 1, 1) and set(s['external']) == {'W', 'X'}:
                control = values
        assert (3, 4) in control and (5, 0) in control, control
    return dict(kind='census', case=case, depth='full' if depth is None else depth,
                archive_sha256=digest, action_recovery_seconds=setup_seconds,
                construction_seconds=seconds, peak_rss_mib=peak_mib(),
                state_pairs=pairs, retained_labels=labels, raw_path_count=paths,
                labels_per_pair=dict(sorted(hist.items())), max_labels=max(hist, default=0),
                construction_work=dict(counts), cache=close.cache_info()._asdict(),
                incomparable_control=control)


HELPERS = r'''
def _lc_scalar(ops, ext, external):
    return all(size(t, ext) == 1 for t in project(ops)[0] - external)

def _lc_count(name, value=1):
    if stats is not None:
        stats[name] = stats.get(name, 0) + value

def _lc_p(ops, ext, external, owned):
    if len(ops) == 1 and not _lc_scalar(ops, ext, external):
        _lc_count('closure_empty_partition_calls')
        return ()
    return _partition_only(ops, ext, external, owned)

@lru_cache(maxsize=None)
def _lc_labels(ops, ext, external, owned):
    _lc_count('closure_rows')
    live = project(ops)[0] - external
    if _lc_scalar(ops, ext, external):
        return {}
    candidates = {}
    common, inside = loop_metadata(ops)
    made = project(ops)[2]
    bridge = ('groups', (ops,), 'kept', (), 'via DRAM', ())
    for v in common:
        i, extent = names.index(v), ext[names.index(v)]
        if extent == 1 or any(v not in dims_of[t] for t in inside - external):
            continue
        lacking = sorted(t for t in live if v not in dims_of[t])
        for b in tile_sizes(extent, tile_domain):
            trips = extent // b
            inner_ext = ext[:i] + (b,) + ext[i+1:]
            for bits in product((True, False), repeat=len(lacking)):
                _lc_count('loop_choices')
                kept = frozenset(t for t, keep in zip(lacking, bits) if keep)
                a = sum(size(t, ext) for t in kept)
                d = (trips-1) * sum((spill_cost if t in made else 1) * size(t, ext)
                                    for t in lacking if t not in kept)
                child = projected(ops, inner_ext, external | kept, owned)
                note = ('loop', ops, v, f'tile {b} x{trips}', 'kept', tuple(sorted(kept)),
                        'refetched', tuple(t for t in lacking if t not in kept))
                path = (note,) if witness else ()
                candidates.setdefault(child, []).append((a, d, trips, path))
                if _lc_scalar(*child[:3]):
                    continue
                for end, labels in _lc_labels(*child).items():
                    bucket = candidates.setdefault(end, [])
                    for aa, dd, rr, tail in labels:
                        path = (note, bridge) + tail if witness else ()
                        bucket.append((a+aa, d+trips*dd, trips*rr, path))
    out = {}
    for end, choices in candidates.items():
        _lc_count('closure_label_candidates', len(choices))
        expected_r = prod(a // b for a, b in zip(ext, end[1]))
        assert all(r == expected_r for _, _, r, _ in choices)
        best, kept = float('inf'), []
        for label in sorted(choices, key=lambda x: (x[0], x[1])):
            if label[1] < best:
                kept.append(label)
                best = label[1]
        out[end] = tuple(kept)
        _lc_count('closure_labels_retained', len(kept))
        if stats is not None:
            stats['closure_max_labels_per_pair'] = max(stats.get('closure_max_labels_per_pair', 0), len(kept))
    _lc_count('closure_pairs', len(out))
    return out
'''


def make_kernel():
    path = HERE / 'graph/curve.py'
    tree = ast.parse(path.read_text(), filename=str(path))
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
    functions = {n.name: n for n in outer.body if isinstance(n, ast.FunctionDef)}
    original = functions['_solve']
    partition = copy.deepcopy(original)
    partition.name = '_partition_only'
    for call in (n for n in ast.walk(partition) if isinstance(n, ast.Call)):
        if isinstance(call.func, ast.Name) and call.func.id == 'cut_dp':
            call.keywords.append(ast.keyword(arg='_lc_proper_only', value=ast.Constant(True)))
        if isinstance(call.func, ast.Name) and call.func.id == 'record_miss':
            call.args[0] = ast.Constant('partition')
    outer.body.insert(outer.body.index(original), partition)
    outer.body[1:1] = ast.parse('''
if not (grid is None and max_capacity == float('inf') and spill_cost == 2 and write_through
        and split_shared and ownership_projection and scalar_leaf == 'v2' and partitions == 'dp'
        and not legacy_nested_writes and not canonical_spans and not canonical_remainders
        and not independent_ops and not prune_infeasible_groups and whole_span_cuts is None
        and root_groups is None and root_kept is None and len(graph.produced()) == len(graph.ops)):
    raise ValueError('closure pilot requires the frozen exact single-writer v2 grammar')
''').body
    cut = functions['cut_dp']
    cut.args.args.append(ast.arg(arg='_lc_proper_only'))
    cut.args.defaults.append(ast.Constant(False))
    qloops = [n for n in ast.walk(cut) if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == 'q']
    assert len(qloops) == 1
    qloops[0].body[0:0] = ast.parse('''
if _lc_proper_only and p == 0 and q == n and not _lc_scalar(ops, ext, external):
    continue
''').body
    original.body = ast.parse('''
if stats is not None:
    record_miss('solve', ops, ext, external, owned)
assert not constrained
part = _lc_p(ops, ext, external, owned)
if _lc_scalar(ops, ext, external):
    return part
whole = group_curve(ops, ext, external, owned)
if witness:
    note = (('groups', (ops,), 'kept', (), 'via DRAM', ()),)
    whole = tuple((c, q, join(note, w)) for c, q, w in whole)
return prune(tuple(part) + tuple(whole), max_capacity, grid)
''').body
    functions['_group_curve'].body = ast.parse('''
if stats is not None:
    record_miss('group', group, ext, external, owned)
if _lc_scalar(group, ext, external):
    return solve(group, ext, external, owned)
results = []
for end, labels in _lc_labels(group, ext, external, owned).items():
    part = _lc_p(*end)
    for a, d, r, path in labels:
        _lc_count('closure_response_terms')
        for c, q, w in part:
            _lc_count('closure_response_points')
            results.append((a+c, d+r*q, join(path, w) if witness else ()))
return prune(results, max_capacity, grid)
''').body
    # All helpers are defined before the bottom-level root call.
    outer.body[outer.body.index(partition):outer.body.index(partition)] = ast.parse(HELPERS).body
    final = next(n for n in reversed(outer.body) if isinstance(n, ast.Try))
    stats_block = final.finalbody[0]
    assert isinstance(stats_block, ast.If)
    stats_block.body.extend(ast.parse('''
stats['partition_cache'] = _partition_only.cache_info()._asdict()
stats['closure_cache'] = _lc_labels.cache_info()._asdict()
stats['response_cache_misses_total'] = sum(stats[k]['misses'] for k in
                                         ('solve_cache', 'group_cache', 'partition_cache'))
''').body)
    ns = dict(__name__='research.index_coupling.graph._closure_pilot', __package__='research.index_coupling.graph')
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), ns)
    return ns['curve']


def once(case, mode, witness):
    graph = graph_for(case)
    setup = time.perf_counter()
    solver = curve if mode == 'baseline' else make_kernel()
    setup_seconds = time.perf_counter() - setup
    stats = {}
    start = time.perf_counter()
    points = solver(graph, witness=witness, stats=stats, **OPTIONS)
    seconds = time.perf_counter() - start
    record = dict(kind='solve', case=case, mode=mode, witness=witness, setup_seconds=setup_seconds,
                  seconds=seconds, peak_rss_mib=peak_mib(), frontier=[p[:2] for p in points],
                  work={k: stats[k] for k in WORK},
                  caches={k: v for k, v in stats.items() if k.endswith('_cache') and isinstance(v, dict)},
                  closure_work={k: v for k, v in stats.items() if k.startswith('closure_') and not isinstance(v, dict)})
    record['response_cache_misses_total'] = stats.get('response_cache_misses_total',
        stats['solve_cache']['misses'] + stats['group_cache']['misses'])
    if witness:
        start = time.perf_counter()
        for c, q, w in points:
            result = simulate(graph, w, scalar_leaf='v2')
            assert result['valid'] and (result['peak'], result['traffic']) == (c, q), (case, c, q, result)
        record.update(replayed=len(points), replay_seconds=time.perf_counter()-start,
                      witness_recovery_solver_calls=0)
    return record


if __name__ == '__main__':
    command, case, *args = sys.argv[1:]
    if command == 'census':
        result = census(case, None if args[0] == 'full' else int(args[0]))
    elif command == 'solve':
        result = once(case, args[0], args[1] == 'witness')
    else:
        raise ValueError(command)
    print(json.dumps(result), flush=True)
