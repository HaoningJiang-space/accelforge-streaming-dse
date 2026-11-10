"""Global lower-bound certificates and their essential failure controls."""
from itertools import product
import unittest

from research.index_coupling.free_retention import (free_retention_response,
    make_free_retention_curve, retention_candidates)
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import fork
from research.index_coupling.simulate_nest import simulate
from research.index_coupling.test_streamed_bridge import framed_streamed_witness


def conditional_cases():
    shapes = ((1,2,2,1,'k'), (1,2,4,1,'kkk'), (1,2,4,1,'kii'),
              (4,2,1,1,'kki'), (1,1,4,2,'kkk'), (4,1,1,2,'kii'),
              (1,1,4,1,'kkk'), (1,2,1,3,'kki'))
    for shape in shapes:
        graph = fork(*shape)
        private = sorted(graph.tensors(graph.ops)-{'X'})
        for bits in product((False,True), repeat=len(private)):
            resident = {t for t,b in zip(private,bits) if b}
            child = free_retention_response(graph, graph.ops, tuple(graph.sizes.values()),
                                            resident, set(), tuple(graph.sizes), witness=True)
            if child is not None:
                yield shape, graph, resident, child


class FreeRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fast = staticmethod(make_free_retention_curve())

    def test_given_example_and_failure_controls(self):
        graph = fork(1,2,2,1,'k')
        args = (graph, graph.ops, (1,2,2,1))
        rest = (set(), ('I','J','K','L'))
        self.assertEqual(free_retention_response(*args, {'A'}, *rest)[0][:2], (3,0))
        rows = list(retention_candidates(*args, {'A'}, *rest))
        self.assertEqual([(r['tensor'],r['d'],r['child_bound']) for r in rows if r['eligible']], [('U0',3,2)])
        rows = list(retention_candidates(*args, {'A','C0'}, *rest))
        self.assertEqual(rows[0]['reason'], 'no_slot_drop')
        self.assertFalse(rows[0]['all_bottlenecks_access'])
        graph = fork(1,1,2,1,'kk')
        rows = list(retention_candidates(graph, graph.ops, (1,1,2,1), {'A','U1'}, *rest))
        self.assertEqual(rows[0]['reason'], 'child_above_slot_bound')
        self.assertIsNone(free_retention_response(graph, graph.ops, (1,1,2,1), {'A','U1'}, *rest))

    def test_all_eligible_conditional_masks_and_full_frames(self):
        checked = 0
        for shape, graph, resident, child in conditional_cases():
            with self.subTest(shape=shape, resident=resident):
                compulsory = sum(graph.size(t,set()) for t in
                                 (graph.consumed() ^ graph.produced())-resident)
                expected = tuple((c,q+compulsory) for c,q,_ in child)
                for method in ('enumerate','dp'):
                    self.assertEqual(curve(graph,external=resident,partitions=method),expected)
                    self.assertEqual(self.fast(graph,external=resident,partitions=method),expected)
                parent, notes, capacity, traffic = framed_streamed_witness(graph,resident,child)
                actual = simulate(parent,notes)
                self.assertTrue(actual['valid'])
                self.assertEqual((actual['peak'],actual['traffic']),(capacity,traffic))
                checked += 1
        self.assertGreater(checked, 50)

    def test_options_and_root_replay(self):
        graph = fork(1,2,4,1,'kki')
        options = [dict(entry='group'),dict(whole_span_cuts=()),dict(whole_span_cuts=(2,)),
                   dict(root_groups=(graph.ops,)),dict(external={'A'}),dict(external={'X'}),
                   dict(grid=1.2),dict(spill_cost=1),dict(write_through=False),dict(split_shared=False),
                   dict(legacy_nested_writes=True),dict(canonical_spans=True),dict(independent_ops=True),
                   dict(written={'X'}),dict(tile_domain='divisors')]
        options += [dict(max_capacity=c) for c in (1,2,3,4,8)]
        for opts in options:
            self.assertEqual(self.fast(graph,**opts),curve(graph,**opts),opts)
        points = self.fast(graph,partitions='dp',witness=True)
        self.assertEqual(tuple(p[:2] for p in points),curve(graph,partitions='dp'))
        for c,q,w in points:
            actual = simulate(graph,w)
            self.assertTrue(actual['valid'])
            self.assertEqual((actual['peak'],actual['traffic']),(c,q))


if __name__ == '__main__':
    unittest.main()
