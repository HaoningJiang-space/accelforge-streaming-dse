"""Offline v2 C2 ceilings and call-DAG work projections; never prune a solve.

Collect the unchanged baseline, then analyze archived responses. The ordered
shadow policy uses only preceding candidates, keeps every all-resident anchor,
and preserves every group response. Reachability accounts for shared children.
"""
import ast
from collections import Counter, defaultdict
from functools import wraps
from itertools import product
from math import prod
from pathlib import Path

from .census_tools import graph_of
from .graph.analysis import traffic_at
from .graph.curve import tile_sizes

COUNTERS = ('dp_transitions', 'loop_choices', 'pareto_candidates', 'merge_inputs')
CASES = ('ffn_forward_l1', 'ffn_forward_l2', 'ffn_forward_l3', 'ffn_forward_l4',
         'attention_forward_l2', 'attention_forward_l4', 'ffn_training_l1',
         'ffn_forward_l1_m8', 'ffn_forward_l2_m8')


def frontier(points):
    out, best = [], float('inf')
    for c, q in sorted(points):
        if q < best:
            out.append((c, q))
            best = q
    return tuple(out)


def dominates(incumbent, lower):
    # At each lower-curve breakpoint; inside its plateau incumbent cannot rise.
    return all(traffic_at(c, incumbent) <= q for c, q in lower)


def transformed(points, reservation, extra, trips, floor=0):
    return frontier((reservation + max(c, floor), extra + trips * q) for c, q in points)


def state(stage, ops, ext, external, owned, constrained=False):
    return dict(stage=stage, ops=tuple(ops), ext=tuple(ext), external=tuple(sorted(external)),
                owned=tuple(sorted(owned)), constrained=constrained)


def state_key(s):
    return (s['stage'], tuple(s['ops']), tuple(s['ext']), tuple(s['external']), tuple(s['owned']), s['constrained'])


class BaselineRecorder:
    """All cache-query edges plus once-per-miss responses/exclusive counters."""
    def __init__(self):
        self.ids, self.nodes, self.edges, self.stack = {}, {}, {}, []
        self.stats = {}
        self.root = None

    def identify(self, stage, args):
        ops, ext, external, owned, *tail = args
        s = state(stage, ops, ext, external, owned, bool(tail and tail[0]))
        k = state_key(s)
        if k not in self.ids:
            self.ids[k] = len(self.ids)
        return self.ids[k], s

    def call(self, stage):
        def decorate(fn):
            @wraps(fn)
            def recorded(*args):
                ident, _ = self.identify(stage, args)
                if self.stack:
                    parent = self.stack[-1]['id']
                    edge = self.edges.setdefault((parent, ident), dict(calls=0, cold=0))
                    edge['calls'] += 1
                    edge['cold'] += ident not in self.nodes
                else:
                    assert self.root is None
                    self.root = ident
                return fn(*args)
            recorded.cache_info = fn.cache_info
            return recorded
        return decorate

    def miss(self, stage):
        def decorate(fn):
            @wraps(fn)
            def recorded(*args):
                ident, s = self.identify(stage, args)
                before = {k: self.stats[k] for k in COUNTERS}
                frame = dict(id=ident, children=Counter())
                self.stack.append(frame)
                points = fn(*args)
                self.stack.pop()
                inclusive = {k: self.stats[k] - before[k] for k in COUNTERS}
                own = {k: inclusive[k] - frame['children'][k] for k in COUNTERS}
                assert ident not in self.nodes and all(v >= 0 for v in own.values())
                self.nodes[ident] = dict(id=ident, state=s, points=[p[:2] for p in points], work=own)
                if self.stack:
                    self.stack[-1]['children'].update(inclusive)
                return points
            return recorded
        return decorate

    def kernel(self):
        path = Path(__file__).parent / 'graph/curve.py'
        tree = ast.parse(path.read_text(), filename=str(path))
        found = set()
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef) and fn.name in ('_solve', '_group_curve'):
                assert len(fn.decorator_list) == 1 and isinstance(fn.decorator_list[0], ast.Call)
                assert getattr(fn.decorator_list[0].func, 'id', '') == 'lru_cache'
                stage = 'solve' if fn.name == '_solve' else 'group'
                fn.decorator_list.insert(0, ast.Call(ast.Name('_record_call', ast.Load()), [ast.Constant(stage)], []))
                fn.decorator_list.append(ast.Call(ast.Name('_record_miss', ast.Load()), [ast.Constant(stage)], []))
                found.add(stage)
        assert found == {'solve', 'group'}
        ns = dict(__name__='research.index_coupling.graph._c2_baseline',
                  __package__='research.index_coupling.graph',
                  _record_call=self.call, _record_miss=self.miss)
        exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), ns)
        return ns['curve']

    def run(self, graph):
        points = self.kernel()(graph, partitions='dp', scalar_leaf='v2', stats=self.stats)
        assert not self.stack
        assert len(self.nodes) == self.stats['solve_cache']['currsize'] + self.stats['group_cache']['currsize']
        assert len(self.nodes) == len(self.ids)
        assert all(sum(n['work'][k] for n in self.nodes.values()) == self.stats[k] for k in COUNTERS)
        return dict(grammar='v2', root=self.root, points=points, stats=self.stats,
                    nodes=[self.nodes[i] for i in sorted(self.nodes)],
                    edges=[dict(parent=p, child=c, **v) for (p, c), v in self.edges.items()])


def reachable(root, edges, removed=()):
    links = defaultdict(list)
    for e in edges:
        if (e['parent'], e['child']) not in removed:
            links[e['parent']].append(e['child'])
    seen, pending = set(), [root]
    while pending:
        p = pending.pop()
        if p in seen:
            continue
        seen.add(p)
        pending.extend(links[p])
    return seen


def analyze(case, data):
    if data.get('grammar') != 'v2':
        raise ValueError('C2 requires a declared v2 baseline')
    graph = graph_of(case)
    names = sorted(graph.sizes)
    nodes = {n['id']: n for n in data['nodes']}
    assert set(nodes) == reachable(data['root'], data['edges'])
    by_parent = defaultdict(list)
    for e in data['edges']:
        by_parent[e['parent']].append(e)
    cuts = {'raw': set(), 'slots': set()}
    oracle_cuts = {'raw': set(), 'slots': set()}
    anchors, loop_edges, detail = set(), set(), []
    totals = Counter()
    strata = defaultdict(Counter)
    top_families = []
    all_full = tuple(graph.sizes[v] for v in names)

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
            continue  # v2 scalar partition redirect, not a loop retention choice.
        made = {graph.output(o) for o in ops}
        inside = made & {t for o in ops for t in graph.access[o] if t != graph.output(o)}
        common = set.intersection(*(graph.rank_vars((o,)) for o in ops))
        valid_axes = {v for v in common if sizes[v] > 1 and all(v in dims[t] for t in inside - resident)}
        families = defaultdict(list)
        actions = []
        for edge in by_parent[pid]:
            child = nodes[edge['child']]
            cs = child['state']
            assert cs['stage'] == 'solve' and tuple(cs['ops']) == ops and not cs['constrained']
            changed = [i for i, (a, b) in enumerate(zip(ext, cs['ext'])) if a != b]
            assert len(changed) == 1
            at = changed[0]
            v, b = names[at], cs['ext'][at]
            assert v in valid_axes and b in tile_sizes(sizes[v])
            lacking = tuple(sorted(t for t in live if v not in dims[t]))
            keep = set(cs['external']) - resident
            assert keep <= set(lacking) and resident <= set(cs['external'])
            assert tuple(cs['owned']) == tuple(s['owned']) and edge['calls'] == 1
            trips = sizes[v] // b
            allocation = sum(size(t) for t in keep)
            extra = (trips - 1) * sum((2 if t in made else 1) * size(t) for t in set(lacking) - keep)
            slots = max(len(set(graph.access[o]) - set(cs['external'])) for o in ops)
            actual = transformed(child['points'], allocation, extra, trips)
            a = dict(parent=pid, child=edge['child'], axis=v, tile=b, keep=tuple(sorted(keep)),
                     lacking=lacking, allocation=allocation, extra=extra, trips=trips,
                     slots=slots, actual=actual, cold=edge['cold'], full=len(keep) == len(lacking))
            actions.append(a)
            families[v, b].append(a)
            loop_edges.add((pid, edge['child']))
        expected = {(v, b) for v in valid_axes for b in tile_sizes(sizes[v])}
        assert set(families) == expected
        parent_curve = frontier(parent['points'])
        assert frontier(p for a in actions for p in a['actual']) == parent_curve
        for family in families.values():
            m = len(family[0]['lacking'])
            assert len(family) == 2**m and family[0]['full']
            assert len({a['keep'] for a in family}) == len(family)
            anchor = nodes[family[0]['child']]['points']
            anchors.add((pid, family[0]['child']))
            for a in family:
                a['raw'] = transformed(anchor, a['allocation'], a['extra'], a['trips'])
                a['slots_bound'] = transformed(anchor, a['allocation'], a['extra'], a['trips'], a['slots'])
                assert dominates(a['raw'], a['slots_bound']) and dominates(a['slots_bound'], a['actual'])
            totals['families'] += 1
            totals['bound_classes'] += len({(a['allocation'], a['extra']) for a in family})
            if ops == graph.ops and ext == all_full and not resident and not s['owned']:
                top_families.append(dict(axis=family[0]['axis'], tile=family[0]['tile'],
                    lacking=family[0]['lacking'], anchor=anchor, parent=parent_curve,
                    classes=len({(a['allocation'], a['extra']) for a in family}),
                    actions=family))
        incumbent = ()
        for a in actions:  # Captured baseline iteration order, not a sorted surrogate.
            pair = (pid, a['child'])
            totals['actions'] += 1
            totals['anchors' if a['full'] else 'proper'] += 1
            if not a['full']:
                labels = ('all', 'M' if a['axis'] == 'M' else 'other_axes',
                          f"lacking_{len(a['lacking'])}", 'multi_op' if len(ops) > 1 else 'single_op')
                flags = dict(raw_tight=a['raw'] == a['actual'], slots_tight=a['slots_bound'] == a['actual'],
                             raw_phantom=a['raw'][0][0] < a['actual'][0][0],
                             slots_phantom=a['slots_bound'][0][0] < a['actual'][0][0])
                finite_caps = {c for p in (a['actual'], a['raw'], a['slots_bound']) for c, _ in p
                               if c >= a['actual'][0][0]}
                max_gap = max(traffic_at(c, a['actual']) - traffic_at(c, a['raw']) for c in finite_caps)
                assert max_gap >= 0
                for mode, bound in (('raw', a['raw']), ('slots', a['slots_bound'])):
                    ideal = dominates(parent_curve, bound)
                    ordered = dominates(incumbent, bound)
                    assert not ordered or ideal
                    flags['ideal_' + mode] = ideal
                    flags['ordered_' + mode] = ordered
                    if ideal:
                        oracle_cuts[mode].add(pair)
                    if ordered:
                        assert frontier(incumbent + a['actual']) == incumbent
                        cuts[mode].add(pair)
                assert not flags['ideal_raw'] or flags['ideal_slots']
                assert not flags['ordered_raw'] or flags['ordered_slots']
                a.update(flags)
                for label in labels:
                    strata[label]['proper'] += 1
                    strata[label].update({k: int(v) for k, v in flags.items()})
                    strata[label]['raw_gap_sum_of_edge_maxima'] += max_gap
                detail.append(dict(parent=pid, child=a['child'], axis=a['axis'], tile=a['tile'],
                    lacking_count=len(a['lacking']), kept_count=len(a['keep']), allocation=a['allocation'],
                    extra=a['extra'], slots=a['slots'], raw=a['raw'], slots_bound=a['slots_bound'],
                    actual=a['actual'], raw_max_finite_gap=max_gap, **flags))
            incumbent = frontier(incumbent + a['actual'])
        assert incumbent == parent_curve
    assert totals['actions'] == data['stats']['loop_choices']
    assert not anchors & cuts['raw'] and not anchors & cuts['slots']
    projections = {}
    for mode in cuts:
        keep = reachable(data['root'], data['edges'], cuts[mode])
        gone = set(nodes) - keep
        work = {k: sum(nodes[i]['work'][k] for i in gone) for k in COUNTERS}
        projections[mode] = dict(removed_edges=len(cuts[mode]),
            skipped_calls_from_reachable_parents=sum(p in keep for p, _ in cuts[mode]),
            unreachable_states=len(gone), unreachable_by_entry=dict(Counter(nodes[i]['state']['stage'] for i in gone)),
            retained_states=len(keep), saved_exclusive_work=work,
            retained_anchor_calls=sum(p in keep for p, _ in anchors))
    assert projections['raw']['unreachable_states'] <= projections['slots']['unreachable_states']
    return dict(case=case, states=len(nodes), unique_call_edges=len(data['edges']),
                all_queries=sum(e['calls'] for e in data['edges']) + 1,
                baseline_work={k: data['stats'][k] for k in COUNTERS},
                counts=dict(totals), strata={k: dict(v) for k, v in strata.items()},
                ordered_work_projection=projections, top_families=top_families,
                validation=dict(all_loop_choices_reconstructed=True, all_child_contexts_found=True,
                    all_lower_bounds_valid=True, all_group_envelopes_equal=True,
                    all_ordered_shadow_envelopes_equal=True, exclusive_counters_sum=True)), detail
