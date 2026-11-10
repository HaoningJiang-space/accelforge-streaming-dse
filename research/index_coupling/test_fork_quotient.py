"""All-order quotient vs literal-order oracle and independently executed plans."""
from itertools import product
import unittest

from .fork_order_oracle import envelope, orders, replay_private_boundary
from .graph.curve import curve
from .graph.fork_quotient import ForkQuotient


class ForkQuotientTests(unittest.TestCase):
    def check(self, shape, roles, external=(), **options):
        solver = ForkQuotient(shape, roles, tile_domain=options.get('tile_domain', 'halving'))
        query = {k: v for k, v in options.items() if k != 'tile_domain'}
        actual = solver.curve(external=external, **query)
        expected = envelope(solver.graph, external=external, quotient=False, **options)
        self.assertEqual(tuple(p[:2] for p in actual), tuple(p[:2] for p in expected))
        if not options.get('written') and options.get('entry', 'solve') == 'solve' and 'X' not in external:
            for c, q, plan in actual:
                self.assertTrue(replay_private_boundary(solver.graph, external, c, q, plan)['exact'])
        return actual

    def test_all_small_orders_rectangles_and_tile_domains(self):
        for roles in ('k', 'i', 'kk', 'ki', 'kkk', 'kki', 'iki'):
            self.check((2, 2, 2, 2), roles)
        for domain in ('halving', 'divisors'):
            self.check((6, 1, 2, 1), 'ki', tile_domain=domain)
            self.check((2, 1, 4, 2), 'kki', tile_domain=domain)
        self.check((1, 1, 1, 1), 'kki')

    def test_all_joint_private_profiles_two_consumers(self):
        for roles in ('kk', 'ki'):
            for profiles in product(range(4), repeat=2):
                external = set()
                for i, (role, profile) in enumerate(zip(roles, profiles)):
                    if profile & 1:
                        external.add(f'{"C" if role == "k" else "D"}{i}')
                    if profile & 2:
                        external.add(f'{"U" if role == "k" else "V"}{i}')
                self.check((2, 2, 2, 2), roles, external)

    def test_positional_counterexample_collapses_only_after_order_completion(self):
        solver = ForkQuotient((2, 2, 2, 2), 'kkk')
        a, b = {'C0', 'C2'}, {'C1', 'C2'}
        self.assertEqual(curve(solver.graph, external=a)[0], (3, 56))
        self.assertEqual(curve(solver.graph, external=b)[0], (3, 52))
        pa = solver.curve(external=a)
        counts = [solver.stats[f'{s}_cache']['misses'] for s in ('solve', 'group', 'sequence')]
        pb = solver.curve(external=b)
        self.assertEqual(counts, [solver.stats[f'{s}_cache']['misses'] for s in ('solve', 'group', 'sequence')])
        self.assertEqual(tuple(p[:2] for p in pa), ((3, 52), (4, 32), (7, 24)))
        self.assertEqual(tuple(p[:2] for p in pa), tuple(p[:2] for p in pb))
        for external, points in ((a, pa), (b, pb)):
            for c, q, plan in points:
                self.assertTrue(replay_private_boundary(solver.graph, external, c, q, plan)['exact'])

    def test_shared_context_ownership_and_entry_are_preserved(self):
        for external, entry, owned in product(((), ('X',), ('A', 'C1'), ('B', 'U0')), ('solve', 'group'), (False, True)):
            self.check((2, 2, 2, 2), 'kk', external, entry=entry, written=owned)

    def test_reference_order_orbits_keep_joint_profiles(self):
        g = ForkQuotient((2, 2, 2, 2), 'kkkkkk').graph
        self.assertEqual(len(list(orders(g))), 1)
        self.assertEqual(len(list(orders(g, {'C0', 'C2', 'C4'}))), 20)
        g = ForkQuotient((2, 2, 2, 2), 'kkkiii').graph
        self.assertEqual(len(list(orders(g))), 20)
        self.assertEqual(len(list(orders(g, quotient=False))), 720)

    def test_labeled_all_order_ablation(self):
        for roles in ('kkk', 'kki'):
            for external in ((), ('C0', 'U1')):
                a = ForkQuotient((2, 2, 2, 2), roles).curve(external=external)
                solver = ForkQuotient((2, 2, 2, 2), roles, quotient=False)
                b = solver.curve(external=external)
                self.assertEqual(tuple(p[:2] for p in a), tuple(p[:2] for p in b))
                for c, q, plan in b:
                    self.assertTrue(replay_private_boundary(solver.graph, external, c, q, plan)['exact'])

    def test_six_consumer_boundary_orbit_cardinalities(self):
        for roles, expected_input, expected_joint in (('kkkkkk',7,84),('kkkiii',16,400)):
            solver=ForkQuotient((2,2,2,2),roles);g=solver.graph
            ext=tuple(g.sizes[v] for v in solver.ranks)
            for choices, expected in ((range(2),expected_input),(range(4),expected_joint)):
                keys=set()
                for profiles in product(choices,repeat=6):
                    external=set()
                    for op,profile in zip(g.ops[1:],profiles):
                        _,inp,out=solver.info[op]
                        if profile & 1:external.add(inp)
                        if profile & 2:external.add(out)
                    keys.add(solver.canonical(g.ops,ext,external,False)[0])
                self.assertEqual(len(keys),expected)


if __name__ == '__main__':
    unittest.main()
