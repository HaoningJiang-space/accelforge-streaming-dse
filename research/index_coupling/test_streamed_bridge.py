"""Non-scalar theorem checks, entry guards, and complete parent-frame replay."""
from itertools import product
import unittest

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import fork, residual
from research.index_coupling.scalar_bridge import make_scalar_bridge_curve
from research.index_coupling.simulate_nest import simulate
from research.index_coupling.streamed_bridge import make_streamed_bridge_curve, streamed_response
from research.index_coupling.test_scalar_bridge import framed_witness


def framed_streamed_witness(graph, resident, child):
    """Extend the old scalar-only frame helper to multi-axis final copies."""
    framed, notes, capacity, traffic = framed_witness(graph, resident, child)
    fixed = []
    for note in notes:
        if (fixed and note[0] == 'loop' and fixed[-1][0] == 'loop'
                and note[1] == fixed[-1][1]):
            fixed.append(('groups', (note[1],), 'kept', (), 'via DRAM', ()))
        fixed.append(note)
    return framed, tuple(fixed), capacity, traffic


def conditional_cases():
    """All supersets of missing-axis obligations for bounded vector/matrix X."""
    for shape in ((4,2,1,3,'kkk'), (4,2,1,3,'kii'),
                  (1,2,4,3,'kkk'), (1,2,4,3,'kii'),
                  (3,2,1,5,'kik'), (1,3,6,2,'kki'),
                  (3,2,4,3,'kki'), (4,3,2,2,'kii')):
        graph = fork(*shape)
        active = [v for v in ('I', 'K') if graph.sizes[v] > 1]
        private = graph.tensors(graph.ops) - {'X'}
        mandatory = {t for t in private if any(v not in graph.dims(t) for v in active)}
        optional = sorted(private - mandatory)
        for bits in product((False, True), repeat=len(optional)):
            yield shape, graph, mandatory | {t for t, bit in zip(optional, bits) if bit}


class StreamedBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fast = staticmethod(make_streamed_bridge_curve())
        cls.scalar = staticmethod(make_scalar_bridge_curve())

    def test_conditional_frontiers_and_parent_frame_replay(self):
        count = 0
        for shape, graph, resident in conditional_cases():
            with self.subTest(shape=shape, resident=sorted(resident)):
                child = streamed_response(graph, graph.ops, tuple(graph.sizes.values()),
                                          resident, set(), tuple(graph.sizes), witness=True)
                self.assertIsNotNone(child)
                compulsory = sum(graph.size(t, set()) for t in
                                 (graph.consumed() ^ graph.produced()) - resident)
                expected = tuple((c, q + compulsory) for c, q, _ in child)
                for partitions in ('enumerate', 'dp'):
                    self.assertEqual(curve(graph, external=resident, partitions=partitions), expected)
                    self.assertEqual(self.fast(graph, external=resident, partitions=partitions), expected)
                framed, notes, capacity, traffic = framed_streamed_witness(graph, resident, child)
                actual = simulate(framed, notes)
                self.assertTrue(actual['valid'])
                self.assertEqual((actual['peak'], actual['traffic']), (capacity, traffic))
                count += 1
        self.assertEqual(count, 98)

    def test_scalar_leaf_is_a_real_obstruction(self):
        graph = fork(2,1,1,1,'kkk')
        resident = {'B','C0','C1','C2'}
        self.assertIsNone(streamed_response(graph, graph.ops, (2,1,1,1), resident,
                                           set(), ('I','J','K','L')))
        self.assertEqual(curve(graph, external=resident), ((2,16),(3,8)))
        self.assertEqual(self.fast(graph, external=resident), ((2,16),(3,8)))
        # One previously resident tensor removed: the no-obligation proof no
        # longer applies, regardless of any equality that happens to survive.
        graph = fork(4,2,1,3,'kkk')
        for tensor in resident:
            self.assertIsNone(streamed_response(graph, graph.ops, (4,2,1,3), resident-{tensor},
                                               set(), ('I','J','K','L')))

    def test_root_frontiers_guards_and_replay(self):
        for shape in ((4,2,2,2,'kkk'), (4,2,4,2,'kki'), (3,2,2,3,'ki')):
            graph = fork(*shape)
            for partitions in ('enumerate', 'dp'):
                expected = curve(graph, partitions=partitions)
                points = self.fast(graph, partitions=partitions, witness=True)
                self.assertEqual(tuple(p[:2] for p in points), expected)
                for c, q, notes in points:
                    actual = simulate(graph, notes)
                    self.assertTrue(actual['valid'])
                    self.assertEqual((actual['peak'], actual['traffic']), (c, q))
        graph = fork(4,2,1,3,'kii')
        resident = {'B','C0','V1','V2'}
        options = [dict(entry='group'), dict(whole_span_cuts=()), dict(whole_span_cuts=(2,)),
                   dict(root_groups=(graph.ops,)), dict(root_groups=tuple((op,) for op in graph.ops), root_kept=()),
                   dict(grid=1.2), dict(spill_cost=1), dict(write_through=False), dict(split_shared=False),
                   dict(legacy_nested_writes=True), dict(canonical_spans=True), dict(independent_ops=True),
                   dict(written={'X'}), dict(tile_domain='divisors')]
        options += [dict(max_capacity=c) for c in (1,2,3,4)]
        for opts in options:
            with self.subTest(options=opts):
                self.assertEqual(self.fast(graph, external=resident, **opts),
                                 curve(graph, external=resident, **opts))
        for graph in (fork(2,2,2,2,'kkk'), residual(2,2,2,2,True)):
            self.assertEqual(self.fast(graph), self.scalar(graph))


if __name__ == '__main__':
    unittest.main()
