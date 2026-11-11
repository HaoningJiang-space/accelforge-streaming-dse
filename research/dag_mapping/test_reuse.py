"""Cross-order closed responses, ownership, and complete-parent execution."""
from itertools import product
import unittest

from research.index_coupling.graph.branch_symmetry import topological_orders
from research.index_coupling.graph.curve import curve
from research.index_coupling.simulate_nest import simulate
from .boundary import resized, workload
from .hierarchy import analyze, decode
from .reuse import RegionSession


class ReuseTests(unittest.TestCase):
    def test_full_conditional_responses_across_orders_and_entries(self):
        graph, _ = workload('gated_fork_join', (1, 2, 2, 1))
        session = RegionSession(graph, shared=True, audit=True)
        for order in topological_orders(graph):
            ordered = resized(graph, graph.sizes, order)
            for entry, resident, owned in product(('solve', 'group'),
                    ((), ('X',), ('C0', 'U1'), ('U0', 'U1')), ((), ('X',))):
                reference = curve(ordered, partitions='enumerate', scalar_leaf='v2',
                                  external=resident, written=owned, entry=entry)
                actual = session.query(order, external=resident, owned=owned, entry=entry)
                self.assertEqual(tuple(p[:2] for p in actual), reference)
        counts = session.pool.summary()
        self.assertGreater(counts['cross_order_hits'], 0)
        self.assertEqual(counts['hits'], counts['verified'])
        self.assertGreater(counts['verified_multiop'], 0)

    def test_root_witnesses_execute_in_the_destination_parent(self):
        graph, _ = workload('gated_fork_join', (2, 2, 2, 2))
        session = RegionSession(graph, shared=True)
        for order in topological_orders(graph):
            ordered = resized(graph, graph.sizes, order)
            points = session.query(order)
            self.assertEqual(tuple(p[:2] for p in points),
                             curve(ordered, partitions='dp', scalar_leaf='v2'))
            for c, q, w in points:
                result = simulate(ordered, w, scalar_leaf='v2')
                typed = analyze(ordered, decode(ordered, w))
                self.assertTrue(result['valid'])
                self.assertEqual((result['peak'], result['traffic']), (c, q))
                self.assertEqual((typed['peak'], typed['traffic']), (c, q))

    def test_local_operator_order_is_not_removed_from_key(self):
        graph, _ = workload('fork_join', (1, 2, 2, 1))
        session = RegionSession(graph, shared=True)
        orders = tuple(topological_orders(graph))
        for order in orders:
            session.query(order)
        roots = {k[1] for k in session.pool.entries if k[0] == 'solve' and len(k[1]) == len(graph.ops)}
        self.assertTrue(set(orders) <= roots)

    def test_scalar_entry_stays_native_for_each_order(self):
        graph, _ = workload('fork_join', (1, 1, 1, 1))
        session = RegionSession(graph, shared=True)
        for order in topological_orders(graph):
            for entry in ('solve', 'group'):
                ordered = resized(graph, graph.sizes, order)
                actual = session.query(order, entry=entry)
                self.assertEqual(tuple(p[:2] for p in actual),
                                 curve(ordered, scalar_leaf='v2', partitions='dp', entry=entry))
        self.assertTrue(all(k[0] in ('solve', 'group') for k in session.pool.entries))

    def test_analytic_registry_survives_cross_order_reuse(self):
        graph, _ = workload('gated_fork_join', (1, 2, 2, 2))
        session = RegionSession(graph, shared=True, unit=True)
        for order in topological_orders(graph):
            ordered = resized(graph, graph.sizes, order)
            points = session.query(order)
            self.assertEqual(tuple(p[:2] for p in points),
                             curve(ordered, scalar_leaf='v2', partitions='dp'))
            for c, q, notes in points:
                restored = session.recover(notes)
                result = simulate(ordered, restored, scalar_leaf='v2')
                self.assertTrue(result['valid'])
                self.assertEqual((result['peak'], result['traffic']), (c, q))
        self.assertGreater(len(session.registry), 0)

    def test_divisor_policy_and_invalid_order(self):
        graph, _ = workload('fork_join', (1, 1, 3, 1))
        session = RegionSession(graph, shared=True, tile_domain='divisors')
        for order in topological_orders(graph):
            ordered = resized(graph, graph.sizes, order)
            self.assertEqual(tuple(p[:2] for p in session.query(order)),
                             curve(ordered, scalar_leaf='v2', partitions='dp', tile_domain='divisors'))
        with self.assertRaises(ValueError):
            session.query(tuple(reversed(graph.ops)))
        with self.assertRaises(ValueError):
            session.query(graph.ops[:-1])

    def test_existing_certificates_compose_with_v2_and_shared_responses(self):
        graph, _ = workload('gated_fork_join', (2, 2, 2, 2))
        session = RegionSession(graph, shared=True, unit=True, certificate=True)
        certificates = 0
        for order in topological_orders(graph):
            ordered = resized(graph, graph.sizes, order)
            ledger = {}
            points = session.query(order, stats=ledger)
            certificates += ledger.get('separator_hits', 0)
            self.assertEqual(tuple(p[:2] for p in points),
                             curve(ordered, scalar_leaf='v2', partitions='dp'))
            for c, q, notes in points:
                restored = session.recover(notes)
                typed = analyze(ordered, decode(ordered, restored))
                actual = simulate(ordered, restored, scalar_leaf='v2')
                self.assertTrue(actual['valid'])
                self.assertEqual((typed['peak'], typed['traffic']), (c, q))
                self.assertEqual((actual['peak'], actual['traffic']), (c, q))
        self.assertGreater(certificates, 0)


if __name__ == '__main__':
    unittest.main()
