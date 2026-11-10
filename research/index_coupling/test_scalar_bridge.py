"""Constructive scalar-X theorem, guarded prototype, and whole-frame replays."""
from itertools import product
import unittest

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph, fork, residual
from research.index_coupling.scalar_bridge import bridge_response, make_scalar_bridge_curve, standard_fork
from research.index_coupling.simulate_nest import simulate


def framed_witness(graph, resident, child):
    """Real parent reservations, plus a two-trip loop entering the child solve.

Each resident tensor is also read by a final copy, so the root may retain it
across the original span. Nonresident tensors carry a new T axis; resident
outputs accumulate across T. The child T loop enters the original solve state
with T=1. This avoids pretending standalone simulation supplies external data.
"""
    sizes = dict(graph.sizes, T=2)
    ops = [(op, {t: dims if t in resident else dims + ('T',)
                 for t, dims in graph.access[op].items()}) for op in graph.ops]
    copies = []
    for t in sorted(resident):
        name = f'Copy_{t}'
        ops.append((name, {t: graph.dims(t), f'Final_{t}': graph.dims(t)}))
        copies.append((name, t))
    framed = Graph(sizes, ops)
    groups = (graph.ops,) + tuple((name,) for name, _ in copies)
    notes = [('groups', groups, 'kept', tuple(sorted(resident)), 'via DRAM', ()),
             ('loop', graph.ops, 'T', 'tile 1 x2', 'kept', (), 'refetched', ())]
    notes.extend(child[0][2])
    for name, tensor in copies:
        for axis in graph.dims(tensor):
            if graph.sizes[axis] > 1:
                notes.append(('loop', (name,), axis, f'tile 1 x{graph.sizes[axis]}',
                              'kept', (), 'refetched', ()))
    peak = sum(graph.size(t, set()) for t in resident) + child[0][0]
    compulsory = sum(framed.size(t, set()) for t in framed.consumed() ^ framed.produced())
    return framed, tuple(notes), peak, compulsory


class ScalarBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fast = staticmethod(make_scalar_bridge_curve())

    def test_framed_execution_for_every_private_residency_pattern(self):
        checked = 0
        for roles in ('kkk', 'kii'):
            graph = fork(1, 2, 1, 3, roles)
            private = sorted(graph.tensors(graph.ops) - {'X'})
            for bits in product((False, True), repeat=len(private)):
                resident = {t for t, bit in zip(private, bits) if bit}
                child = bridge_response(graph, graph.ops, (1, 2, 1, 3), resident, set(),
                                        ('I', 'J', 'K', 'L'), witness=True)
                if child is None:
                    self.assertEqual(resident, set(private))  # original scalar leaf
                    continue
                framed, witness, capacity, traffic = framed_witness(graph, resident, child)
                actual = simulate(framed, witness)
                self.assertTrue(actual['valid'])
                self.assertEqual((actual['peak'], actual['traffic']), (capacity, traffic))
                checked += 1
        self.assertEqual(checked, 510)

    def test_default_frontier_equality_and_replay_on_additional_shapes(self):
        for shape in ((2,2,2,2,'kkk'), (2,2,2,2,'kki'), (2,1,4,3,'ki'),
                      (1,3,1,6,'kkk'), (1,4,1,5,'kii'), (3,2,2,2,'ki')):
            graph = fork(*shape)
            for partitions in ('enumerate', 'dp'):
                with self.subTest(shape=shape, partitions=partitions):
                    expected = curve(graph, partitions=partitions)
                    points = self.fast(graph, partitions=partitions, witness=True)
                    self.assertEqual(tuple(p[:2] for p in points), expected)
                    for c, q, w in points:
                        actual = simulate(graph, w)
                        self.assertTrue(actual['valid'])
                        self.assertEqual((actual['peak'], actual['traffic']), (c, q))

    def test_scalar_leaf_and_interface_guards(self):
        graph = fork(1,1,1,1,'kkk')
        stats = {}
        self.assertEqual(self.fast(graph, stats=stats), curve(graph))
        self.assertEqual(stats.get('scalar_bridge_hits', 0), 0)
        graph = fork(1,2,1,3,'kkk')
        groups = tuple((op,) for op in graph.ops)
        options = [dict(entry='group'), dict(whole_span_cuts=()), dict(whole_span_cuts=(2,)),
                   dict(root_groups=(graph.ops,)), dict(root_groups=groups, root_kept=()),
                   dict(external={'X'}), dict(external={'C0','U1'}), dict(written={'X'}),
                   dict(grid=1.2), dict(spill_cost=1), dict(write_through=False),
                   dict(split_shared=False), dict(legacy_nested_writes=True),
                   dict(canonical_spans=True), dict(independent_ops=True)]
        options += [dict(max_capacity=c) for c in (1,2,3,4)]
        for opts in options:
            with self.subTest(options=opts):
                self.assertEqual(self.fast(graph, **opts), curve(graph, **opts))
        for graph in (residual(2,2,2,2,True), Graph({'I':2}, [('E', {'A':('I',), 'B':('I',)})])):
            self.assertFalse(standard_fork(graph))
            self.assertEqual(self.fast(graph), curve(graph))


if __name__ == '__main__':
    unittest.main()
