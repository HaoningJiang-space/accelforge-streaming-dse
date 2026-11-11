"""Offline audit of resident-separated intervals under the strong prefix+i arm.

This module does not change a solver default or install a new reduction. It
records the actual prefix cache as well as response caches: ignoring that cache
would overestimate removable work when a prefix has several callers.
"""
import argparse
import ast
from collections import Counter, defaultdict
from functools import wraps
import gzip
import hashlib
import json
from math import prod
from pathlib import Path
import platform
import subprocess
from time import perf_counter

from research.index_coupling.c2_bound_audit import COUNTERS
from research.index_coupling.graph.curve import pareto
from research.index_coupling.response import prefix
from research.index_coupling.simulate_nest import simulate
from .bench_reuse import graph_for, select_orders
from .bench_composition import SOURCES as BASE_SOURCES
from .boundary import resized
from .hierarchy import analyze, decode

CASES = ('two_stage_join', 'asymmetric_join', 'mixed_join')
OPTIONS = dict(partitions='dp', scalar_leaf='v2', independent_ops=True)
SOURCES = tuple(sorted(set(BASE_SOURCES) | {
    'research/dag_mapping/conditional_separation.py',
    'research/dag_mapping/test_conditional_separation.py',
    'research/dag_mapping/CONDITIONAL_SEPARATION.md',
    'research/index_coupling/c2_bound_audit.py'}))


def intervals(graph, ops, external):
    """Finest CONTIGUOUS split with no nonresident tensor crossing any cut.

    Full operator domains are retained; only tensor incidence is projected.
    Unlike connected components, this never changes the fixed operator order.
    """
    positions = defaultdict(list)
    for i, op in enumerate(ops):
        for t in graph.access[op]:
            if t not in external:
                positions[t].append(i)
    delta = [0] * (len(ops)+1)
    for uses in positions.values():
        delta[uses[0]+1] += 1
        delta[uses[-1]+1] -= 1
    cuts, active = [0], 0
    for p in range(1, len(ops)):
        active += delta[p]
        if not active:
            cuts.append(p)
    cuts.append(len(ops))
    return tuple(tuple(ops[a:b]) for a, b in zip(cuts, cuts[1:]))


def candidate(graph, state):
    if state['stage'] != 'solve' or state.get('constrained'):
        return None
    blocks = intervals(graph, state['ops'], state['external'])
    # All-singleton cases are ALREADY handled by the strong baseline's i rule.
    return blocks if len(blocks) > 1 and any(len(b) > 1 for b in blocks) else None


class Recorder:
    def __init__(self):
        self.ids, self.nodes, self.edges, self.stack = {}, {}, {}, []
        self.stats, self.root = {}, None

    def identify(self, stage, args):
        if stage == 'prefix':
            ops, q, ext, external, owned, bits = args
            tail = (q, tuple(bits))
        else:
            ops, ext, external, owned, *rest = args
            q, bits, tail = None, None, (bool(rest and rest[0]),)
        key = (stage, tuple(ops), tuple(ext), frozenset(external), frozenset(owned), tail)
        if key not in self.ids:
            self.ids[key] = len(self.ids)
        state = dict(stage=stage, ops=ops, ext=ext, external=sorted(external), owned=sorted(owned),
                     constrained=bool(stage == 'solve' and tail[0]))
        if stage == 'prefix':
            state.update(q=q, bits=bits)
        return self.ids[key], state

    def call(self, stage):
        def wrap(fn):
            @wraps(fn)
            def run(*args):
                ident, _ = self.identify(stage, args)
                if self.stack:
                    key = (self.stack[-1]['id'], ident)
                    self.edges[key] = self.edges.get(key, 0) + 1
                else:
                    assert self.root is None
                    self.root = ident
                return fn(*args)
            run.cache_info = fn.cache_info
            return run
        return wrap

    def miss(self, stage):
        def wrap(fn):
            @wraps(fn)
            def run(*args):
                ident, state = self.identify(stage, args)
                before = {k: self.stats[k] for k in COUNTERS}
                frame = dict(id=ident, children=Counter(), child_seconds=0.)
                self.stack.append(frame)
                start = perf_counter()
                points = fn(*args)
                seconds = perf_counter() - start
                self.stack.pop()
                inclusive = {k: self.stats[k] - before[k] for k in COUNTERS}
                work = {k: inclusive[k] - frame['children'][k] for k in COUNTERS}
                assert ident not in self.nodes and all(v >= 0 for v in work.values())
                self.nodes[ident] = dict(id=ident, state=state, points=[p[:2] for p in points],
                                        work=work, own_seconds=seconds-frame['child_seconds'])
                if self.stack:
                    self.stack[-1]['children'].update(inclusive)
                    self.stack[-1]['child_seconds'] += seconds
                return points
            return run
        return wrap

    def run(self, graph):
        tree = ast.parse(prefix.SOURCE.read_text())
        prefix.transform(tree, frames=True, composition='numeric', reductions=True)
        stages = {'_solve': 'solve', '_group_curve': 'group', 'prefix_cached': 'prefix'}
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in stages:
                stage = stages[node.name]
                assert len(node.decorator_list) == 1
                node.decorator_list.insert(0, ast.Call(ast.Name('_record_call', ast.Load()),
                                                     [ast.Constant(stage)], []))
                node.decorator_list.append(ast.Call(ast.Name('_record_miss', ast.Load()),
                                                    [ast.Constant(stage)], []))
                found.add(stage)
        assert found == set(stages.values())
        ns = dict(__name__='research.index_coupling.graph._separation_audit',
                  __package__='research.index_coupling.graph',
                  _record_call=self.call, _record_miss=self.miss)
        exec(compile(ast.fix_missing_locations(tree), str(prefix.SOURCE), 'exec'), ns)
        start = perf_counter()
        points = ns['curve'](graph, witness=True, stats=self.stats, **OPTIONS)
        seconds = perf_counter()-start
        assert not self.stack and len(self.nodes) == len(self.ids)
        assert len(self.nodes) == sum(self.stats[k]['currsize'] for k in
                                     ('solve_cache', 'group_cache', 'prefix_cache'))
        assert all(sum(n['work'][k] for n in self.nodes.values()) == self.stats[k] for k in COUNTERS)
        return dict(root=self.root, nodes=[self.nodes[i] for i in sorted(self.nodes)],
                    edges=[dict(parent=p, child=c, calls=n) for (p, c), n in self.edges.items()],
                    stats=self.stats, frontier=[p[:2] for p in points], witnesses=[p[2] for p in points],
                    instrumented_seconds=seconds)


class Oracle:
    """Native closures preserve GLOBAL tensor roles; never make a new subgraph.

    Queries return extra traffic, with no root compulsory charge. Used only
    after the baseline recording, so its work cannot enter coverage counters.
    """
    def __init__(self, graph, tile_domain='halving'):
        self.graph, self.names = graph, tuple(sorted(graph.sizes))
        tree = ast.parse(prefix.SOURCE.read_text())
        outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
        at = next(i for i, n in enumerate(outer.body) if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'ext0' for t in n.targets))
        outer.body[at:at] = ast.parse('_capture(solve, group_curve)\nreturn ()').body
        def capture(solve, group):
            self.solve, self.group = solve, group
        ns = dict(__name__='research.index_coupling.graph._separation_oracle',
                  __package__='research.index_coupling.graph', _capture=capture)
        exec(compile(ast.fix_missing_locations(tree), str(prefix.SOURCE), 'exec'), ns)
        self.flatten = ns['flatten']
        ns['curve'](graph, witness=True, scalar_leaf='v2', partitions='dp', tile_domain=tile_domain)

    def query(self, ops, ext, external=(), owned=(), entry='solve'):
        fn = self.solve if entry == 'solve' else self.group
        return fn(tuple(ops), tuple(ext), frozenset(external), frozenset(owned))

    def compose(self, state, blocks):
        """Numeric max/sum product plus executable concatenated partitions."""
        ext, external, owned = state['ext'], set(state['external']), state['owned']
        sizes = dict(zip(self.names, ext))
        level = ((0, 0, ((), (), (), ())),)
        for block in blocks:
            points = self.query(block, ext, external, owned)
            scalar = all(prod(sizes[v] for v in self.graph.dims(t)) == 1
                         for t in self.graph.tensors(block)-external)
            lifted = []
            for c, q, notes in points:
                notes = self.flatten(notes)
                if scalar:
                    # A proper scalar part enters group, which can repartition.
                    parts, kept, dropped, body = (tuple(block),), (), (), notes
                else:
                    head, *body = notes
                    assert head[0] == 'groups'
                    parts, kept, dropped, body = head[1], head[3], head[5], tuple(body)
                lifted.append((c, q, (parts, kept, dropped, body)))
            level = pareto((max(c, p), q+t, tuple(a+b for a, b in zip(w, v)))
                           for c, q, w in level for p, t, v in lifted)
        return tuple((c, q, (('groups', parts, 'kept', tuple(sorted(kept)),
                              'via DRAM', tuple(sorted(dropped))),) + body)
                     for c, q, (parts, kept, dropped, body) in level)


def reach(root, links, terminal=()):
    seen, pending = set(), [root]
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        if node not in terminal:
            pending.extend(links[node])
    return seen


def projection(data, terminals, replacement_children=None):
    """Zero-construction-cost thought experiment, NOT an achievable speedup."""
    nodes = {n['id']: n for n in data['nodes']}
    links = defaultdict(set)
    for e in data['edges']:
        links[e['parent']].add(e['child'])
    assert reach(data['root'], links) == set(nodes)
    if replacement_children is None:
        reached = reach(data['root'], links, terminals)
    else:
        rewired = dict(links)
        for i in terminals:
            rewired[i] = replacement_children[i]
        reached = reach(data['root'], rewired)
    gone = set(nodes) - (reached-set(terminals))
    total = {k: sum(n['work'][k] for n in nodes.values()) for k in COUNTERS}
    removed = {k: sum(nodes[i]['work'][k] for i in gone) for k in COUNTERS}
    seconds = sum(n['own_seconds'] for n in nodes.values())
    return dict(eligible=len(terminals), reached_terminals=len(reached & set(terminals)),
                removed_states=len(gone), removed_work=removed,
                removed_fraction={k: removed[k]/total[k] if total[k] else 0 for k in COUNTERS},
                instrumented_own_seconds_fraction=sum(nodes[i]['own_seconds'] for i in gone)/seconds,
                warning=('free composition; existing component dependencies retained; not a speedup'
                         if replacement_children is not None else
                         'free complete responses; includes their computation; not a realizable factorization speedup'))


def projected_key(graph, ops, ext, external, owned):
    names = tuple(sorted(graph.sizes))
    used = graph.rank_vars(ops)
    tensors = graph.tensors(ops)
    made = {graph.output(o) for o in ops}
    return (tuple(ops), tuple(e if v in used else 1 for v, e in zip(names, ext)),
            tuple(sorted(set(external) & tensors)), tuple(sorted(set(owned) & made)))


def audit_order(graph, data):
    oracle = Oracle(graph)
    candidates, comparisons, checked_points, examples = {}, 0, 0, []
    component_keys, requests, nonscalar, non_scalar_x = set(), 0, set(), set()
    state_index = {}
    baseline_keys = {projected_key(graph, n['state']['ops'], n['state']['ext'],
                                  n['state']['external'], n['state']['owned'])
                     : n['id'] for n in data['nodes'] if n['state']['stage'] == 'solve'}
    replacement_children = {}
    for node in data['nodes']:
        s = node['state']
        blocks = candidate(graph, s)
        if blocks is None:
            continue
        actual = oracle.compose(s, blocks)
        numeric = [p[:2] for p in actual]
        assert numeric == [tuple(p) for p in node['points']], (s, numeric, node['points'])
        candidates[node['id']] = blocks
        comparisons += 1
        key = projected_key(graph, s['ops'], s['ext'], s['external'], s['owned'])
        state_index[key] = node
        sizes = dict(zip(oracle.names, s['ext']))
        if any(prod(sizes[v] for v in graph.dims(t)) > 1
               for t in graph.tensors(s['ops'])-set(s['external'])):
            nonscalar.add(node['id'])
        if 'X' in graph.tensors(s['ops']) and prod(sizes[v] for v in graph.dims('X')) > 1:
            non_scalar_x.add(node['id'])
        replacement_children[node['id']] = set()
        for block in blocks:
            requests += 1
            ck = projected_key(graph, block, s['ext'], s['external'], s['owned'])
            component_keys.add(ck)
            if ck in baseline_keys:
                replacement_children[node['id']].add(baseline_keys[ck])
    # Private input flips do not change a separator. Verify both complete
    # responses and show that OTHER block query keys stay identical. This is
    # distinct from asserting that the two parent responses are equal.
    flips, changed, changed_examples = 0, 0, []
    inputs = graph.consumed()-graph.produced()
    for key, node in state_index.items():
        s, blocks = node['state'], candidates[node['id']]
        for t in set(s['external']) & inputs:
            owners = [i for i, b in enumerate(blocks) if t in graph.tensors(b)]
            if len(owners) != 1:
                continue
            without = set(s['external'])-{t}
            other = state_index.get(projected_key(graph, s['ops'], s['ext'], without, s['owned']))
            if other is None:
                continue
            assert blocks == candidates[other['id']]
            for i, block in enumerate(blocks):
                if i != owners[0]:
                    assert projected_key(graph, block, s['ext'], s['external'], s['owned']) == \
                           projected_key(graph, block, s['ext'], without, s['owned'])
            flips += 1
            if node['points'] != other['points']:
                changed += 1
                if len(changed_examples) < 2 and node['id'] in nonscalar & non_scalar_x:
                    changed_examples.append(dict(tensor=t, blocks=blocks, state=s,
                        with_resident=node['points'], without_resident=other['points'],
                        changed_block=owners[0], other_block_keys_unchanged=True))
    # Select by exclusive DP work in solve + directly attributed prefix cache;
    # the coverage projection below, not this rank, accounts for shared children.
    nodes = {n['id']: n for n in data['nodes']}
    direct = Counter({i: nodes[i]['work']['dp_transitions'] for i in candidates})
    for e in data['edges']:
        if e['parent'] in candidates and nodes[e['child']]['state']['stage'] == 'prefix':
            direct[e['parent']] += nodes[e['child']]['work']['dp_transitions']
    ranked = sorted(candidates, key=lambda i: (i not in nonscalar & non_scalar_x, -direct[i], i))[:3]
    for i in ranked:
        s, blocks = nodes[i]['state'], candidates[i]
        local = resized(graph, dict(zip(oracle.names, s['ext'])), s['ops'])
        points = oracle.compose(s, blocks)
        for c, q, notes in points:
            plan = decode(local, notes, external=s['external'])
            check = analyze(local, plan, external=s['external'], owned=s['owned'])
            assert (check['peak'], check['extra_traffic']) == (c, q), (s, check, (c, q))
            checked_points += 1
        loop_parents = []
        for edge in data['edges']:
            if edge['child'] != i:
                continue
            parent = nodes[edge['parent']]['state']
            if parent['stage'] == 'group' and tuple(parent['ops']) == tuple(s['ops']):
                changed_axes = [j for j, (a,b) in enumerate(zip(parent['ext'],s['ext'])) if a != b]
                if len(changed_axes) == 1:
                    j = changed_axes[0]
                    loop_parents.append(dict(rank=oracle.names[j], tile=s['ext'][j],
                        trips=parent['ext'][j]//s['ext'][j], parent_external=parent['external'],
                        newly_kept=sorted(set(s['external'])-set(parent['external']))))
        examples.append(dict(state=s, blocks=blocks, frontier=[p[:2] for p in points],
                             witnesses=[p[2] for p in points], direct_dp_rank_weight=direct[i],
                             incoming_loops=loop_parents))
    return dict(comparisons=comparisons, conditional_typed_checks=checked_points,
                coverage=projection(data, candidates), examples=examples,
                nonscalar_coverage=projection(data, nonscalar),
                nonscalar_x_coverage=projection(data, nonscalar & non_scalar_x),
                dependency_preserving_ceiling=projection(data, candidates, replacement_children),
                component_queries=requests, unique_component_keys=len(component_keys),
                component_keys_not_in_baseline=len(component_keys-baseline_keys.keys()),
                private_input_flip_pairs=flips, unequal_parent_response_pairs=changed,
                private_flip_examples=changed_examples,
                states_by_blocks=dict(Counter(str(tuple(map(len, b))) for b in candidates.values())))


def substitution_check(graph, expected):
    """Oracle-backed replacement for executable correctness ONLY, never timed.

    The independent native oracle constructs the block witnesses. This is not
    a proposed efficient implementation or part of the work recording.
    """
    oracle, replacements = Oracle(graph), []
    def replace(ops, ext, external, owned, constrained):
        s = dict(stage='solve', ops=ops, ext=ext, external=external,
                 owned=owned, constrained=constrained)
        blocks = candidate(graph, s)
        if blocks is None:
            return None
        replacements.append((ops, ext))
        return oracle.compose(s, blocks)
    tree = ast.parse(prefix.SOURCE.read_text())
    prefix.transform(tree, frames=True, composition='numeric', reductions=True)
    solve = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_solve')
    solve.body[:0] = ast.parse('''
_substituted = _audit_replace(ops, ext, external, owned, constrained)
if _substituted is not None:
    return _substituted
''').body
    ns = dict(__name__='research.index_coupling.graph._separation_witness_check',
              __package__='research.index_coupling.graph', _audit_replace=replace)
    exec(compile(ast.fix_missing_locations(tree), str(prefix.SOURCE), 'exec'), ns)
    points = ns['curve'](graph, witness=True, **OPTIONS)
    assert [tuple(p[:2]) for p in points] == [tuple(p) for p in expected]
    for c, q, notes in points:
        checked = simulate(graph, notes, scalar_leaf='v2')
        typed = analyze(graph, decode(graph, notes))
        assert checked['valid'] and (checked['peak'], checked['traffic']) == (c, q)
        assert (typed['peak'], typed['traffic']) == (c, q)
    return dict(replacements=len(replacements), root_replays=len(points),
                witnesses=[dict(point=p[:2], notes=p[2]) for p in points])


def run(case, out):
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    hashes = {}
    for source in SOURCES:
        content = Path(source).read_bytes()
        if subprocess.check_output(['git', 'show', f'{revision}:{source}']) != content:
            raise ValueError(f'uncommitted source: {source}')
        hashes[source] = hashlib.sha256(content).hexdigest()
    out.mkdir(parents=True, exist_ok=False)
    graph = graph_for(case)
    orders, all_orders, automorphisms = select_orders(graph, True)
    rows, roots = [], 0
    for index, order in enumerate(orders):
        ordered = resized(graph, graph.sizes, order)
        data = Recorder().run(ordered)
        control, _ = prefix.make_kernel(frames=True, composition='numeric', reductions=True)
        expected = control(ordered, **OPTIONS)
        assert [tuple(p) for p in data['frontier']] == list(expected)
        for point, notes in zip(data['frontier'], data['witnesses']):
            checked = simulate(ordered, notes, scalar_leaf='v2')
            assert checked['valid'] and (checked['peak'], checked['traffic']) == tuple(point)
            roots += 1
        report = audit_order(ordered, data)
        report['oracle_substitution_check'] = substitution_check(ordered, data['frontier'])
        path = out/f'order_{index}.json.gz'
        with gzip.GzipFile(filename=str(path), mode='wb', mtime=0) as stream:
            stream.write(json.dumps(dict(order=order, data=data, audit=report), sort_keys=True).encode())
        rows.append(dict(order=order, archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         states=len(data['nodes']), totals={k:data['stats'][k] for k in COUNTERS}, **report))
        print(json.dumps(dict(case=case, order=index, eligible=report['comparisons'],
                              coverage=report['coverage']['removed_fraction'])), flush=True)
    result = dict(case=case, searched_orders=len(orders), all_orders=all_orders,
                  automorphisms=automorphisms, root_replays=roots, orders=rows,
                  revision=revision, source_sha256=hashes,
                  python=platform.python_version(), kind='offline sufficiency and optimistic coverage audit')
    (out/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.case, args.out)


if __name__ == '__main__':
    main()
