"""Observer transparency and the precise scope of residency type histograms."""
from collections import defaultdict
from itertools import product
import unittest

from research.index_coupling.audit_residency_states import instrumented_curve
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import fork, residual
from research.index_coupling.simulate_nest import simulate
from research.index_coupling.summarize_residency_states import classify


class ResidencyStateTests(unittest.TestCase):
    def test_observer_preserves_full_frontiers_witnesses_and_cache_counts(self):
        graphs = [fork(2, 2, 2, 2, roles) for roles in ('kk', 'ki', 'kkk')]
        graphs += [residual(2, 2, 2, 2, x) for x in (False, True)]
        for g in graphs:
            with self.subTest(ops=g.ops):
                records, stats, baseline_stats = [], {}, {}
                actual = instrumented_curve(records.append)(g, partitions='dp', witness=True, stats=stats)
                expected = curve(g, partitions='dp', witness=True, stats=baseline_stats)
                self.assertEqual(actual, expected)
                for field in ('solve_cache', 'group_cache', 'loop_choices', 'dp_transitions'):
                    self.assertEqual(stats[field], baseline_stats[field])
                self.assertEqual(len(records), stats['solve_cache']['currsize'] + stats['group_cache']['currsize'])
                keys = [(r['stage'], r['ops'], r['ext'], r['external'], r['owned'], r['constrained']) for r in records]
                self.assertEqual(len(keys), len(set(keys)))
                for c, q, witness in actual:
                    replay = simulate(g, witness)
                    self.assertTrue(replay['valid'])
                    self.assertEqual((replay['peak'], replay['traffic']), (c, q))

    def test_profile_histogram_is_conditional_on_shared_residency(self):
        g = fork(2, 2, 2, 2, 'kkk')
        for resident_x in (False, True):
            buckets = defaultdict(set)
            for profiles in product(range(4), repeat=3):
                external = {'X'} if resident_x else set()
                for a, profile in enumerate(profiles):
                    if profile & 1:
                        external.add(f'C{a}')
                    if profile & 2:
                        external.add(f'U{a}')
                points = curve(g, partitions='dp', external=external)
                state = dict(stage='solve', ops=g.ops, ext=(2, 2, 2, 2),
                             external=sorted(external), owned=(), constrained=False)
                category = classify(g, state)
                self.assertEqual(category['eligible'], resident_x)
                buckets[category['key']].add(points)
                if resident_x:
                    self.assertEqual(points, curve(g, partitions='dp', external=external, independent_ops=True))
            self.assertEqual(len(buckets), 20)
            self.assertEqual(sum(len(values) > 1 for values in buckets.values()), 0 if resident_x else 2)

    def test_entry_ownership_extents_and_scalar_rule_are_not_dropped(self):
        g = fork(2, 2, 2, 2, 'kkk')
        base = dict(stage='solve', ops=g.ops, ext=(2, 2, 2, 2), external=('X',), owned=(), constrained=False)
        a = classify(g, base)
        self.assertTrue(a['eligible'])
        for changes in (dict(stage='group'), dict(constrained=True), dict(owned=('X',)), dict(ext=(1, 2, 2, 2))):
            self.assertNotEqual(classify(g, dict(base, **changes))['key'], a['key'])
        self.assertFalse(classify(g, dict(base, stage='group'))['eligible'])
        self.assertFalse(classify(g, dict(base, constrained=True))['eligible'])
        scalar = classify(g, dict(base, ext=(1, 1, 1, 1)))
        self.assertEqual(scalar['bucket'], 'scalar_leaf')
        self.assertFalse(scalar['eligible'])

    def test_unproved_count_classes_retain_the_known_counterexample(self):
        g = fork(2, 2, 2, 2, 'kkk')
        a = dict(stage='solve', ops=g.ops, ext=(2, 2, 2, 2),
                 external=('C1', 'C2'), owned=(), constrained=False)
        b = dict(a, external=('C0', 'C2'))
        self.assertEqual(classify(g, a)['key'], classify(g, b)['key'])
        self.assertEqual(classify(g, a)['bucket'], 'coupled_or_constrained')
        self.assertEqual(curve(g, external=a['external'])[0], (3, 52))
        self.assertEqual(curve(g, external=b['external'])[0], (3, 56))


if __name__ == '__main__':
    unittest.main()
