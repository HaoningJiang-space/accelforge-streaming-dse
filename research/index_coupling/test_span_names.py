"""Alpha-equivalent memo entries must preserve prices and executable names."""
from itertools import product
import unittest

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph, coupling, fork, residual
from research.index_coupling.graph.span_names import SpanNames
from research.index_coupling.simulate_nest import simulate


class SpanNameTests(unittest.TestCase):
    def test_curves_and_restored_execution(self):
        graphs = [fork(2, 2, 2, 2, roles) for roles in ('kk', 'kkkk', 'kiki', 'kkii')]
        graphs += [residual(2, 2, 2, 4, x) for x in (False, True)]
        for g, mode in product(graphs, ('enumerate', 'dp')):
            with self.subTest(ops=g.ops, mode=mode):
                old_stats, new_stats = {}, {}
                expected = curve(g, partitions=mode, stats=old_stats)
                points = curve(g, witness=True, partitions=mode, canonical_spans=True, stats=new_stats)
                self.assertEqual(tuple(p[:2] for p in points), expected)
                for c, q, w in points:
                    actual = simulate(g, w)
                    self.assertTrue(actual['valid'])
                    self.assertEqual((actual['peak'], actual['traffic']), (c, q))
                self.assertLessEqual(sum(new_stats[k]['currsize'] for k in ('solve_cache', 'group_cache')),
                                     sum(old_stats[k]['currsize'] for k in ('solve_cache', 'group_cache')))

    def test_conditional_and_root_constraints(self):
        g = fork(2, 2, 2, 2, 'kkkk')
        groups = (g.ops[:2], g.ops[2:])
        options = [dict(external={'U0', 'C2'}), dict(written={'X'}), dict(entry='group'),
                   dict(write_through=False), dict(split_shared=False), dict(spill_cost=1),
                   dict(whole_span_cuts=(2, 3)), dict(whole_span_cuts=()),
                   dict(root_groups=groups), dict(root_groups=groups, root_kept=()),
                   dict(max_capacity=5), dict(legacy_nested_writes=True)]
        for options, mode in product(options, ('enumerate', 'dp')):
            with self.subTest(options=options, mode=mode):
                self.assertEqual(curve(g, partitions=mode, **options),
                                 curve(g, partitions=mode, canonical_spans=True, **options))
        with self.assertRaises(ValueError):
            curve(g, canonical_spans=True, grid=1.1)

    def test_global_roles_are_not_erased(self):
        g = Graph(dict(I=2), [
            ('E0', {'A': ('I',), 'U': ('I',)}),
            ('E1', {'B': ('I',), 'V': ('I',)}),
            ('E2', {'V': ('I',), 'Z': ('I',)}),
        ])
        memo = SpanNames(g)
        self.assertNotEqual(memo.lookup(('E0',))[0], memo.lookup(('E1',))[0])
        for mode in ('enumerate', 'dp'):
            self.assertEqual(curve(g, partitions=mode), curve(g, partitions=mode, canonical_spans=True))

    def test_restored_witness_is_valid_after_renaming_entire_graph(self):
        g = fork(2, 2, 2, 2, 'kkk')
        renamed = Graph(g.sizes, [(f'op_{i}', {f't_{t}': dims for t, dims in g.access[op].items()})
                                  for i, op in enumerate(g.ops)])
        for c, q, w in curve(renamed, witness=True, canonical_spans=True, partitions='dp'):
            actual = simulate(renamed, w)
            self.assertTrue(actual['valid'])
            self.assertEqual((actual['peak'], actual['traffic']), (c, q))


if __name__ == '__main__':
    unittest.main()
