"""Differential grammar checks and independent execution, kept deliberately tiny."""
from collections import Counter
from itertools import product
import random
import unittest
from unittest.mock import patch

import research.index_coupling.graph.curve as cm
from research.index_coupling.audit_all_plans import audit
from research.index_coupling.graph.model import Graph, coupling, fork, residual
from research.index_coupling.graph.plan_stream import Budget, BudgetExceeded, iter_plans
from research.index_coupling.simulate_nest import simulate


class SolverScalingTests(unittest.TestCase):
    def test_linear_merge_against_cartesian_product(self):
        rng = random.Random(21)
        for _ in range(100):
            a, b = [cm.pareto([(rng.randrange(1, 30), rng.randrange(100), ())
                               for _ in range(20)]) for _ in range(2)]
            for cap, grid in product((5, 25, float('inf')), (None, 1.2)):
                expected = cm.pareto(((max(x[0], y[0]), x[1] + y[1], ())
                                      for x in a for y in b), cap, grid)
                self.assertEqual(cm.combine_max_sum(a, b, cap, grid), expected)
        self.assertEqual(cm.combine_max_sum((), ((1, 1, ()),)), ())

    def test_dp_and_projection_against_enumeration_and_execution(self):
        graphs = [coupling(2, 2, 2, 2, cross) for cross in (False, True)]
        graphs += [fork(2, 2, 2, 2, roles) for roles in ('kki', 'kii', 'ik')]
        graphs += [residual(2, 2, 2, d, x) for d, x in product((2, 3), (False, True))]
        for g in graphs:
            ref = cm.curve(g, ownership_projection=False)
            for mode, projected in product(('enumerate', 'dp'), (False, True)):
                with self.subTest(ops=g.ops, mode=mode, projected=projected):
                    stats = {}
                    points = cm.curve(g, witness=True, partitions=mode,
                                      ownership_projection=projected, stats=stats)
                    self.assertEqual(tuple(p[:2] for p in points), ref)
                    self.assertGreater(stats['solve_cache']['currsize'], 0)
                    for c, q, w in points:
                        a = simulate(g, w)
                        self.assertTrue(a['valid'])
                        self.assertEqual((a['peak'], a['traffic']), (c, q))

    def test_conditional_interfaces(self):
        g = residual(2, 2, 2, 2, True)
        groups = ((g.ops[0],), g.ops[1:-1], (g.ops[-1],))
        options = [dict(whole_span_cuts=cuts) for cuts in ((), (1,), (2, 3), range(1, 4))]
        options += [dict(external={'X'}, written={'X'}), dict(entry='group'),
                    dict(written={'X'}), dict(write_through=False), dict(split_shared=False),
                    dict(spill_cost=1), dict(max_capacity=4), dict(legacy_nested_writes=True),
                    dict(root_groups=groups), dict(root_groups=groups, root_kept=())]
        for opts in options:
            with self.subTest(opts=opts):
                expected = cm.curve(g, ownership_projection=False, **opts)
                for mode, projected in product(('enumerate', 'dp'), (False, True)):
                    self.assertEqual(cm.curve(g, partitions=mode, ownership_projection=projected, **opts), expected)
        with self.assertRaises(ValueError):
            cm.curve(g, partitions='dp', grid=1.1)

    def test_multiwriter_fallback(self):
        g = Graph({'I': 2}, [('E0', {'A': ('I',), 'Z': ('I',)}),
                            ('E1', {'B': ('I',), 'Z': ('I',)})])
        stats = {}
        self.assertEqual(cm.curve(g, partitions='dp', stats=stats), cm.curve(g))
        self.assertGreater(stats['dp_multiwriter_fallbacks'], 0)

    def test_deterministic_dag_differential(self):
        # Exercise gaps in tensor use and cut decisions beyond the named motifs.
        rng = random.Random(21)
        for case in range(120):
            dims, ops = {}, []
            for i in range(rng.randrange(2, 6)):
                inputs = [f'W{i}'] + [f'X{j}' for j in range(i) if rng.random() < .5]
                access = {}
                for tensor in inputs + [f'X{i}']:
                    if tensor not in dims:
                        dims[tensor] = tuple(v for v in ('I', 'K') if rng.random() < .7)
                    access[tensor] = dims[tensor]
                ops.append((f'E{i}', access))
            g = Graph(dict(I=2, K=2), ops)
            for opts in ({}, dict(write_through=False), dict(split_shared=False),
                         dict(whole_span_cuts=tuple(range(2, len(ops))))):
                with self.subTest(case=case, opts=opts):
                    expected = cm.curve(g, ownership_projection=False, **opts)
                    self.assertEqual(cm.curve(g, partitions='dp', **opts), expected)

    def test_stream_multiset_matches_eager_unpruned_grammar(self):
        # The old audit strategy is safe ONLY on these deliberately small graphs.
        def keep_all(points, max_capacity=float('inf'), grid=None):
            return tuple(p for p in points if p[0] <= max_capacity)

        def cartesian(a, b, max_capacity=float('inf'), grid=None):
            return tuple((max(x[0], y[0]), x[1] + y[1], cm.cat(x[2], y[2]))
                         for x in a for y in b if max(x[0], y[0]) <= max_capacity)

        graphs = [coupling(2, 1, 1, 1, True), fork(2, 1, 1, 1, 'kki'),
                  residual(2, 1, 1, 2, True), residual(1, 2, 1, 2, False)]
        for g, legacy in product(graphs, (False, True)):
            with self.subTest(ops=g.ops, legacy=legacy):
                with patch.object(cm, 'pareto', keep_all), patch.object(cm, 'combine_max_sum', cartesian):
                    eager = cm.curve(g, witness=True, legacy_nested_writes=legacy, ownership_projection=False)
                streamed = tuple(iter_plans(g, legacy_nested_writes=legacy))
                self.assertEqual(Counter(streamed), Counter(eager))
                if not legacy:
                    for c, q, w in streamed:
                        a = simulate(g, w)
                        self.assertTrue(a['valid'])
                        self.assertEqual((a['peak'], a['traffic']), (c, q))

    def test_generation_budgets_do_not_claim_completion(self):
        g = fork(2, 2, 2, 2, 'kki')
        limited = audit('kki', g, limit=3)
        self.assertEqual((limited['status'], limited['checked'], limited['complete']), ('plan_limit', 3, False))
        exhausted = audit('scalar', coupling(1, 1, 1, 1, False), limit=10)
        self.assertTrue(exhausted['complete'])
        self.assertEqual(exhausted['checked'], 1)
        limited = audit('kki', g, nodes=1)
        self.assertEqual((limited['status'], limited['expanded']), ('node_limit', 1))
        with self.assertRaises(BudgetExceeded):
            next(iter_plans(g, budget=Budget(deadline=0)))


if __name__ == '__main__':
    unittest.main()
