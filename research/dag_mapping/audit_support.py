"""Audit infrastructure for exact prefix+i response calls.

Recorder includes prefix cache nodes and exclusive work. NativeResponses keeps
full-graph roles and its own witness namespace. Neither installs an optimizer.
"""
import ast
from collections import Counter
from functools import wraps
from time import perf_counter

from research.index_coupling.c2_bound_audit import COUNTERS
from research.index_coupling.response import prefix

OPTIONS = dict(partitions='dp', scalar_leaf='v2', independent_ops=True)


class Recorder:
    """Record one prefix+i root, including shared prefix-cache dependencies."""

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


class NativeResponses:
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
