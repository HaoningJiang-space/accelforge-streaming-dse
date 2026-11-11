from itertools import product
import unittest

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph
from research.index_coupling.simulate_nest import simulate
from .bench_reuse import graph_for
from .boundary import resized, compulsory
from .conditional_separation import Recorder, Oracle, intervals, candidate, projection, audit_order
from .hierarchy import analyze, decode


def state(g, external=(), owned=(), entry='solve'):
    return dict(stage=entry, ops=g.ops, ext=tuple(g.sizes[v] for v in sorted(g.sizes)),
                external=tuple(external), owned=tuple(owned), constrained=False)


class SeparationTests(unittest.TestCase):
    def test_interval_rule_preserves_order_and_resident_domains(self):
        g = graph_for('two_stage_join')
        ops = ('E0', 'H0', 'E1', 'H1')
        self.assertEqual(intervals(g, ops, {'X'}), (('E0', 'H0'), ('E1', 'H1')))
        self.assertEqual(intervals(g, ('E0', 'E1', 'H0', 'H1'), {'X'}),
                         (('E0', 'E1', 'H0', 'H1'),))
        self.assertEqual(intervals(g, ops, set()), (ops,))
        self.assertIn('K', g.rank_vars(('E0',)))
        self.assertIsNone(candidate(g, state(g, g.tensors(g.ops))))  # old i already covers this

    def test_conditional_frontiers_both_domains_and_ownership(self):
        count = 0
        for shape in (2, 3):
            g = graph_for('fork_join_tiny')
            g = resized(g, dict(g.sizes, K=shape))
            for domain in ('halving', 'divisors'):
                oracle = Oracle(g, domain)
                for bits in product((False, True), repeat=5):
                    external = {t for t, bit in zip(('X', 'U0', 'U1', 'C0', 'C1'), bits) if bit}
                    for owned in ((), ('U0', 'U1')):
                        s = state(g, external, owned)
                        blocks = intervals(g, g.ops, external)
                        if len(blocks) < 2:
                            continue
                        raw = oracle.query(g.ops, s['ext'], external, owned)
                        composed = oracle.compose(s, blocks)
                        self.assertEqual(tuple(p[:2] for p in raw), tuple(p[:2] for p in composed))
                        for c, q, notes in composed:
                            check = analyze(g, decode(g, notes, external=external, tile_domain=domain),
                                            external=external, owned=owned, tile_domain=domain)
                            self.assertEqual((check['peak'], check['extra_traffic']), (c, q))
                        count += 1
        # 16 masks with X, plus 4 without X but both join inputs resident.
        self.assertEqual(count, 160)

    def test_group_entry_cannot_use_solve_factorization(self):
        g = Graph(dict(I=2, J=2), [('A', {'x': ('I',), 'y': ('I',)}),
                                   ('B', {'u': ('J',), 'v': ('J',)})])
        oracle, s = Oracle(g), state(g)
        self.assertEqual(oracle.query(g.ops, s['ext'], entry='group'), ())
        self.assertTrue(oracle.query(g.ops, s['ext']))
        self.assertIsNone(candidate(g, state(g, entry='group')))

    def test_root_composed_witnesses_execute_with_scalar_and_nonscalar_blocks(self):
        g = Graph(dict(I=1, J=2), [('A', {'x': ('I',), 'y': ('I',)}),
                                  ('B', {'y': ('I',), 'z': ('I',)}),
                                  ('C', {'u': ('J',), 'v': ('J',)}),
                                  ('D', {'v': ('J',), 'w': ('J',)})])
        s, oracle = state(g), Oracle(g)
        pts = oracle.compose(s, intervals(g, g.ops, ()))
        self.assertEqual(tuple((c, q+compulsory(g, g.sizes)) for c, q, _ in pts),
                         curve(g, scalar_leaf='v2', partitions='enumerate'))
        for c, q, notes in pts:
            report = simulate(g, notes, scalar_leaf='v2')
            self.assertTrue(report['valid'])
            self.assertEqual((report['peak'], report['traffic']), (c, q+compulsory(g, g.sizes)))

    def test_shared_prefix_remains_reachable(self):
        # 0 -> {1,2}; both -> 3. Replacing 1 must not delete shared prefix 3.
        data = dict(root=0, nodes=[dict(id=i, work={k:1 for k in
                    ('dp_transitions', 'loop_choices', 'pareto_candidates', 'merge_inputs')},
                    own_seconds=1.) for i in range(4)],
                    edges=[dict(parent=p, child=c) for p,c in ((0,1),(0,2),(1,3),(2,3))])
        self.assertEqual(projection(data, {1})['removed_states'], 1)
        self.assertEqual(projection(data, {1,2})['removed_states'], 3)

    def test_recorder_uses_strong_baseline_and_counts_prefix_cache(self):
        g = graph_for('fork_join_tiny')
        data = Recorder().run(g)
        self.assertIn('prefix', {n['state']['stage'] for n in data['nodes']})
        self.assertEqual(tuple(data['frontier']), curve(g, scalar_leaf='v2', partitions='dp'))
        self.assertIn((5, 32), data['frontier'])
        for point, notes in zip(data['frontier'], data['witnesses']):
            report = simulate(g, notes, scalar_leaf='v2')
            self.assertTrue(report['valid'])
            self.assertEqual((report['peak'], report['traffic']), tuple(point))
        audit_order(g, data)


if __name__ == '__main__':
    unittest.main()
