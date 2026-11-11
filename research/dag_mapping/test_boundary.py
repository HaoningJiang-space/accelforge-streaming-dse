import unittest

from research.index_coupling.graph.curve import curve
from research.index_coupling.simulate_nest import simulate
from .boundary import RegionComposer, boundary_description, compulsory, workload


class BoundaryTests(unittest.TestCase):
    def test_whole_scalar_part_uses_hold_instead_of_group_reentry(self):
        graph, _ = workload('fork_join', (1, 1, 1, 1))
        for external in ((), ('A',), ('X', 'U0')):
            points = RegionComposer(graph, verify=True).compose((graph.ops,), external=external)
            self.assertEqual(tuple(p[:2] for p in points), ((8-len(external), 0),))
            self.assertEqual(points[0][2][-1], ('hold', graph.ops))
        p, q, notes = RegionComposer(graph).compose((graph.ops,))[0]
        actual = simulate(graph, notes, scalar_leaf='v2')
        self.assertEqual((actual['peak'], actual['traffic']), (p, q+compulsory(graph, graph.sizes)))

    def test_scalar_join_keeps_caller_accounting_and_replays(self):
        graph, regions = workload('fork_join', (1, 2, 1, 1))
        composer = RegionComposer(graph, verify=True)
        for c, extra, notes in composer.compose(regions):
            actual = simulate(graph, notes, scalar_leaf='v2')
            self.assertEqual((actual['peak'], actual['traffic']),
                             (c, extra + compulsory(graph, graph.sizes)))
        self.assertGreater(composer.stats['native_checks'], 0)

    def test_producer_write_ownership_survives_region_reentry(self):
        graph, regions = workload('residual', (1, 2, 2))
        # X is written in one region and read in BOTH later regions. The parent
        # pays its single store; region composition must not add a second one.
        c = RegionComposer(graph, verify=True)
        c.compose(regions, owned={'X'})
        c.compose(regions, external={'W0'})
        self.assertGreater(c.stats['native_checks'], 1)

    def test_loop_legality_rejects_incomplete_reduction_and_absent_rank(self):
        graph, regions = workload('fork_join', (2, 2, 2, 1))
        with self.assertRaisesRegex(ValueError, 'illegal common loop'):
            RegionComposer(graph).shared_loop(regions, 'K')
        composer = RegionComposer(graph, verify=True)
        for capacity, extra, notes in composer.shared_loop(regions):
            actual = simulate(graph, notes, scalar_leaf='v2')
            self.assertEqual((actual['peak'], actual['traffic']),
                             (capacity, extra + compulsory(graph, graph.sizes)))

    def test_region_interface_retains_remaining_consumer_identity(self):
        graph, regions = workload('residual', (1, 1, 1))
        records = boundary_description(graph, regions)
        x = next(t for t in records[0]['boundary'] if t['tensor'] == 'X')
        self.assertEqual(x['remaining_consumers'], ['EH0', 'EAdd'])
        x = next(t for t in records[1]['boundary'] if t['tensor'] == 'X')
        self.assertEqual(x['remaining_consumers'], ['EAdd'])
        with self.assertRaisesRegex(ValueError, 'dependencies'):
            RegionComposer(graph).compose(tuple(reversed(regions)))


if __name__ == '__main__':
    unittest.main()
