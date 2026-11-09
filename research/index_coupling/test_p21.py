"""Small contract checks for the conditional curve API (seconds locally)."""
import unittest

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph, residual
from research.index_coupling.run_p21 import interface_case


class ConditionalCurveTests(unittest.TestCase):
    def test_external_input_has_no_local_transfer_or_allocation(self):
        graph = Graph({'I': 4}, [('E', {'X': ('I',), 'Y': ('I',)})])
        self.assertEqual(curve(graph), ((2, 8),))
        self.assertEqual(curve(graph, external={'X'}), ((1, 4),))
        self.assertEqual(curve(graph, external={'X', 'Y'}), ((0, 0),))

    def test_unused_external_projects_out(self):
        graph = Graph({'I': 4}, [('E', {'A': ('I',), 'B': ('I',)})])
        for entry in ('solve', 'group'):
            self.assertEqual(curve(graph, entry=entry),
                             curve(graph, entry=entry, external={'unused'}))

    def test_invalid_root_interfaces_rejected(self):
        graph = residual(2, 2, 2, 2, False)
        groups = ((graph.ops[0],), graph.ops[1:-1], (graph.ops[-1],))
        for args in (dict(entry='invalid'), dict(root_kept={'X'}),
                     dict(root_groups=groups[::-1]), dict(root_groups=groups, entry='group'),
                     dict(root_groups=groups, root_kept={'R'})):
            with self.subTest(args=args), self.assertRaises(ValueError):
                curve(graph, **args)

    def test_both_interfaces_match_and_execute(self):
        for reads_x in (False, True):
            result = interface_case((2, 2, 2), 2, reads_x, free=True)
            for key in ('keep', 'spill', 'composed'):
                self.assertTrue(result['checks'][key]['exact'])
            self.assertEqual(result['checks']['coarse']['exact'], not reads_x)
            for plans in result['replay'].values():
                self.assertTrue(all(p['exact'] for p in plans))


if __name__ == '__main__':
    unittest.main()
