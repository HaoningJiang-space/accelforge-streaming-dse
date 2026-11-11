"""Exactness of the downset recursion on small graphs (DOWNSET_PROTOCOL.md)."""
import unittest

from research.index_coupling.graph.branch_symmetry import topological_orders
from research.index_coupling.graph.curve import curve, pareto
from research.index_coupling.simulate_nest import simulate
from .bench_reuse import graph_for
from .boundary import resized
from .downset import make_downset_kernel, normalize

OPTIONS = dict(scalar_leaf='v2', partitions='dp')


class DownsetTest(unittest.TestCase):
    def check(self, name, **options):
        g = graph_for(name)
        native = pareto([p[:2] + (o,) for o in topological_orders(g)
                         for p in curve(resized(g, g.sizes, o), **OPTIONS, **options)])
        points = make_downset_kernel()(g, witness=True, **OPTIONS, **options)
        self.assertEqual([p[:2] for p in native], [p[:2] for p in points])
        for c, q, w in points:
            order, notes = normalize(g, w)
            run = simulate(resized(g, g.sizes, order), notes, scalar_leaf='v2')
            self.assertTrue(run['valid'])
            self.assertEqual((run['peak'], run['traffic']), (c, q))

    def test_chain_equals_native(self):
        self.check('chain_tiny')

    def test_residual(self):
        self.check('residual_tiny')

    def test_fork_join_two_orders(self):
        self.check('fork_join_tiny')

    def test_gated_three_orders(self):
        self.check('gated_fork_join_tiny')

    def test_divisor_tiles(self):
        self.check('fork_join_rectangle', tile_domain='divisors')

    def test_rejects_unsupported_options(self):
        g = graph_for('fork_join_tiny')
        with self.assertRaises(ValueError):
            make_downset_kernel()(g, scalar_leaf='v2', partitions='enumerate')


if __name__ == '__main__':
    unittest.main()
