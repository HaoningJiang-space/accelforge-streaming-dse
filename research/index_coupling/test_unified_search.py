"""Small contract checks; full six-op censuses run in bounded remote workers."""
import unittest

from .fork_order_oracle import replay_private_boundary
from .graph.branch_symmetry import is_automorphism, topological_orders
from .graph.curve import curve
from .graph.fork_quotient import Plan, reordered
from .graph.model import Graph
from .unified_search import (UnifiedSearch, certified_automorphisms, make_kernel,
    mixed_branch_graph, scalar_separator_certificate, validate_graph)


class UnifiedSearchTests(unittest.TestCase):
    def test_partial_symmetry_is_detected_from_incidence(self):
        g = mixed_branch_graph()
        group, attempts = certified_automorphisms(g)
        self.assertEqual((len(group), attempts), (2, 36))
        self.assertTrue(all(is_automorphism(g, p) for p in group))
        self.assertTrue(all(p.ops['E0'] == 'E0' for p in group))
        orders = list(topological_orders(g))
        self.assertEqual(len(orders), 12)
        self.assertEqual(len({min(tuple(p.ops[o] for o in o0) for p in group) for o0 in orders}), 6)

    def test_local_certificate_does_not_require_terminal_outputs(self):
        g = mixed_branch_graph((1, 2, 1, 2))
        ops = ('EX', 'E1', 'E2')
        cert = scalar_separator_certificate(g, ops, (1, 2, 1, 2), (), ('U1', 'U2'), ('I', 'J', 'K', 'L'))
        self.assertEqual((cert['capacity'], cert['extra_traffic'], cert['shared']), (3, 0, ('X',)))
        self.assertEqual(cert['singleton_peaks'], [3, 3, 3])
        # An induced solve provides an independent numerical/replay control;
        # the full-root census additionally checks actual nonterminal contexts.
        sub = reordered(g, ops)
        expected = curve(sub, witness=True, written={'U1', 'U2'})
        self.assertEqual(tuple(p[:2] for p in expected), ((3, 12),))
        actual = replay_private_boundary(sub, (), 3, 12, Plan(ops, cert['notes']))
        self.assertTrue(actual['exact'])

    def test_certificate_preserves_leaf_and_rejects_unproved_streaming(self):
        g = mixed_branch_graph((1, 1, 1, 1))
        self.assertIsNone(scalar_separator_certificate(g, g.ops, (1, 1, 1, 1), (), (), tuple(g.sizes)))
        g = mixed_branch_graph()
        self.assertIsNone(scalar_separator_certificate(g, ('EX', 'E1'), (2, 2, 2, 2), (), (), tuple(g.sizes)))
        # All shared objects scalar, but A(J), B(K) cannot both stream for free.
        g = Graph(dict(J=2, K=2), [('P', {'A': ('J',), 'B': ('K',), 'X': ()}),
                                 ('Q', {'X': (), 'C': ('J',), 'Y': ('J',)})])
        self.assertIsNone(scalar_separator_certificate(g, g.ops, (2, 2), (), (), ('J', 'K')))

    def test_interval_gaps_are_charged(self):
        g = Graph(dict(J=2), [('P', {'A': ('J',), 'X': ()}),
                             ('Q', {'B': ('J',), 'C': ('J',), 'Z': ('J',)}),
                             ('R', {'X': (), 'D': ('J',), 'Y': ('J',)})])
        # Keeping X across Q takes four cells although every op's bound is <=3.
        self.assertIsNone(scalar_separator_certificate(g, g.ops, (2,), (), (), ('J',)))

    def test_kernel_certificate_matches_enum_and_group_entry(self):
        g = reordered(mixed_branch_graph((1, 2, 1, 2)), ('EX', 'E1', 'E2'))
        for entry in ('solve', 'group'):
            events, stats = {}, {}
            result = make_kernel(certificate=True, events=events)(g, witness=True, stats=stats, entry=entry)
            self.assertEqual(tuple(p[:2] for p in result), tuple(p[:2] for p in curve(g, entry=entry)))
            self.assertEqual(stats.get('certificate_hits', 0), int(entry == 'solve'))
        # A fixed root grouping does not get replaced by the solve certificate.
        fn = make_kernel(certificate=True)
        kw = dict(root_groups=(g.ops,), root_kept=())
        self.assertEqual(tuple(p[:2] for p in fn(g, **kw)), curve(g, **kw))

    def test_small_all_switches_and_boundary_stabilizer(self):
        g = mixed_branch_graph((1, 2, 1, 2))
        reference = None
        for bits in ('000', '001', '010', '011', '100', '101', '110', '111'):
            search = UnifiedSearch(g, bits)
            points = search.query()
            numeric = tuple(p[:2] for p in points)
            if reference is None:
                reference = numeric
            self.assertEqual(numeric, reference)
            for c, q, p, _ in points:
                self.assertTrue(replay_private_boundary(g, (), c, q, p)['exact'])
        search = UnifiedSearch(g, '111')
        a = search.query(external={'C1'})
        self.assertEqual(search.stats['order_calls'], 12)  # Broken state stabilizer.
        b = search.query(external={'C2'})
        self.assertEqual(search.stats['cache_hits'], 1)  # Same state orbit.
        self.assertEqual(tuple(p[:2] for p in a), tuple(p[:2] for p in b))
        for c, q, p, _ in b:
            self.assertTrue(replay_private_boundary(g, {'C2'}, c, q, p)['exact'])

    def test_invalid_graph_is_rejected(self):
        g = mixed_branch_graph()
        g.access['F']['U0'] = ('I', 'K')
        with self.assertRaises(ValueError):
            validate_graph(g)


if __name__ == '__main__':
    unittest.main()
