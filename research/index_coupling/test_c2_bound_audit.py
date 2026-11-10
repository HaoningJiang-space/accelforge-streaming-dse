import unittest

from .c2_bound_audit import BaselineRecorder, analyze, dominates, reachable, transformed
from .census_tools import graph_of
from .graph.curve import curve


class C2AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = graph_of('ffn_forward_l1')
        cls.raw = BaselineRecorder().run(cls.graph)
        cls.report, cls.details = analyze('ffn_forward_l1', cls.raw)

    def test_observer_does_not_change_response(self):
        self.assertEqual(self.raw['points'], curve(self.graph, partitions='dp', scalar_leaf='v2'))
        self.assertTrue(all(self.report['validation'].values()))

    def test_phantom_capacity_and_remaining_traffic_gap(self):
        m = next(f for f in self.report['top_families'] if f['axis'] == 'M')
        self.assertEqual(tuple(map(tuple, m['anchor'])), ((2, 6), (3, 4), (4, 0)))
        empty = next(a for a in m['actions'] if not a['keep'])
        self.assertEqual(empty['actual'], ((3, 20), (4, 8)))
        self.assertEqual(empty['raw'], ((2, 20), (3, 16), (4, 8)))
        self.assertEqual(empty['slots_bound'], ((3, 16), (4, 8)))
        self.assertFalse(empty['ideal_slots'])
        self.assertEqual(m['classes'], 3)

    def test_clipping_is_not_a_capacity_shift(self):
        self.assertEqual(transformed(((2, 8), (3, 6), (5, 0)), 4, 2, 3, floor=4),
                         ((8, 20), (9, 2)))
        self.assertFalse(dominates(((3, 20), (4, 8)), ((2, 20), (4, 8))))

    def test_shared_child_stays_reachable(self):
        edges = [dict(parent=p, child=c) for p, c in ((0, 1), (0, 2), (1, 3), (2, 3))]
        self.assertEqual(reachable(0, edges, {(0, 1)}), {0, 2, 3})
        self.assertEqual(reachable(0, edges, {(1, 3), (2, 3)}), {0, 1, 2})

    def test_rejects_v1_and_keeps_anchors(self):
        with self.assertRaises(ValueError):
            analyze('ffn_forward_l1', dict(self.raw, grammar='v1'))
        self.assertGreater(self.report['ordered_work_projection']['slots']['retained_anchor_calls'], 0)
        self.assertGreaterEqual(self.report['strata']['all']['ordered_slots'],
                                self.report['strata']['all']['ordered_raw'])


if __name__ == '__main__':
    unittest.main()
