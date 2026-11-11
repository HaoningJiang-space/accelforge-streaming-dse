"""Composition of existing exact reductions with the conditional prefix DP."""
from itertools import product
import unittest

from .graph.curve import curve
from .graph.model import fork, residual
from .graph.stacks import ffn_stack, attention_stack
from .response.prefix import make_kernel
from .run_ancestor_width import control
from .simulate_nest import simulate
from .test_remainder_search import renamed_pair


FLAGS = ('prune_infeasible_groups', 'independent_ops', 'canonical_remainders')
CONFIGS = tuple(dict(zip(FLAGS, bits)) for bits in product((False, True), repeat=3))
OPTIONS = dict(partitions='dp', scalar_leaf='v2')


class PrefixReductionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kernel = staticmethod(make_kernel(frames=True, composition='numeric', reductions=True)[0])

    def test_complete_frontiers_and_renamed_root_witnesses(self):
        graphs = (fork(2, 2, 2, 2, 'ki'), residual(2, 1, 2, 2, False),
                  ffn_stack(2), attention_stack(2), renamed_pair(), control(4))
        for graph in graphs:
            expected = curve(graph, partitions='enumerate', scalar_leaf='v2')
            for config in CONFIGS:
                with self.subTest(graph=graph.ops, config=config):
                    stats = {}
                    points = self.kernel(graph, witness=True, stats=stats, **OPTIONS, **config)
                    self.assertEqual(tuple(p[:2] for p in points), expected)
                    for c, q, notes in points:
                        actual = simulate(graph, notes, scalar_leaf='v2')
                        self.assertTrue(actual['valid'])
                        self.assertEqual((actual['peak'], actual['traffic']), (c, q))

    def test_every_private_residency_mask_both_entries_and_owned_writes(self):
        graph = fork(2, 2, 2, 2, 'ki')
        private = sorted(graph.tensors(graph.ops) - {'X'})
        self.assertEqual(len(private), 6)
        for bits in product((False, True), repeat=len(private)):
            external = frozenset(t for t, bit in zip(private, bits) if bit)
            for entry, owned in product(('solve', 'group'), ((), ('X',))):
                options = dict(OPTIONS, entry=entry, external=external, written=owned)
                expected = curve(graph, **options)
                for config in CONFIGS:
                    self.assertEqual(self.kernel(graph, **options, **config), expected)

    def test_tile_and_boundary_policies(self):
        graph = fork(3, 1, 2, 3, 'k')
        for domain, spill, split, through in product(
                ('halving', 'divisors'), (1, 2), (False, True), (False, True)):
            options = dict(OPTIONS, tile_domain=domain, spill_cost=spill,
                           split_shared=split, write_through=through)
            expected = curve(graph, **options)
            for config in CONFIGS:
                self.assertEqual(self.kernel(graph, **options, **config), expected)

    def test_all_scalar_whole_part_and_empty_group(self):
        for graph in (fork(1, 1, 1, 1, 'ki'), fork(1, 2, 1, 2, 'k')):
            for entry, external in product(('solve', 'group'), ((), ('A', 'B', 'C0', 'U0'))):
                options = dict(OPTIONS, entry=entry, external=external)
                expected = curve(graph, **options)
                for config in CONFIGS:
                    self.assertEqual(self.kernel(graph, **options, **config), expected)

    def test_real_coverage_and_precheck_before_prefix_recursion(self):
        graph = ffn_stack(2)
        base, checked = {}, {}
        expected = self.kernel(graph, stats=base, **OPTIONS)
        self.assertEqual(self.kernel(graph, stats=checked, prune_infeasible_groups=True, **OPTIONS), expected)
        self.assertGreater(checked['prefix_infeasible_skips'], 0)
        self.assertLess(checked['dp_transitions'], base['dp_transitions'])
        graph = fork(2, 2, 2, 2, 'ki')
        stats = {}
        self.kernel(graph, stats=stats, independent_ops=True, **OPTIONS)
        self.assertGreater(stats['independent_splits'], 0)
        stats = {}
        self.kernel(control(4), stats=stats, canonical_remainders=True, **OPTIONS)
        self.assertGreater(stats['renamed_calls'], 0)

    def test_eager_ordered_and_unprojected_adapters(self):
        graph = fork(2, 1, 2, 2, 'ki')
        expected = curve(graph, **OPTIONS)
        for projection, frames, composition in ((False, False, 'eager'), (True, True, 'eager'),
                                                (True, True, 'ordered')):
            kernel, _ = make_kernel(projection=projection, frames=frames, composition=composition,
                                    profile_prefix=True, reductions=True)
            for config in CONFIGS:
                self.assertEqual(kernel(graph, **OPTIONS, **config), expected)

    def test_unsupported_contracts_and_default_remain_explicit(self):
        graph = fork(2, 2, 2, 2, 'ki')
        old, _ = make_kernel(frames=True, composition='numeric')
        for flag in FLAGS:
            with self.assertRaises(ValueError):
                old(graph, **OPTIONS, **{flag: True})
        for change in (dict(max_capacity=5), dict(whole_span_cuts=()), dict(grid=2),
                       dict(scalar_leaf='v1'), dict(canonical_spans=True)):
            with self.assertRaises(ValueError):
                self.kernel(graph, **(OPTIONS | change), canonical_remainders=True)
        # Analytic composition now has an explicit transported-placeholder path;
        # its separate tests exercise recovery rather than silently disabling it.
        analytic, _ = make_kernel(unit=True, reductions=True)
        with self.assertRaises(ValueError):
            analytic(graph, **OPTIONS, spill_cost=1)


if __name__ == '__main__':
    unittest.main()
