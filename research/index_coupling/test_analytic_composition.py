"""Exact analytic responses transported through remainder renaming."""
from itertools import product
import json
import unittest

from .graph.curve import curve, flatten, _RENAME
from .graph.model import Graph, fork, residual
from .graph.stacks import ffn_stack
from .response.prefix import make_kernel
from .response.substitution import expand, native
from .simulate_nest import simulate
from .test_prefix_reductions import CONFIGS, OPTIONS
from research.dag_mapping.boundary import resized
from research.dag_mapping.hierarchy import analyze, decode
from research.dag_mapping.reuse import RegionSession
from research.dag_mapping.workloads import dag_graph as graph_for, select_orders


def twins(count=2):
    sizes = dict(M=1)
    for i in range(count):
        sizes.update({f'D{i}': 2, f'F{i}': 2})
    return Graph(sizes, [(f'E{i}', {f'X{i}': ('M', f'D{i}'), f'W{i}': (f'D{i}', f'F{i}'),
                                  f'Y{i}': ('M', f'F{i}')}) for i in range(count)])


class AnalyticCompositionTests(unittest.TestCase):
    def test_all_flag_combinations_and_full_root_replay(self):
        for graph in (ffn_stack(2), fork(2, 1, 2, 2, 'ki'), residual(2, 1, 2, 2, False), twins()):
            expected = curve(graph, scalar_leaf='v2', partitions='enumerate')
            for config in CONFIGS:
                kernel, registry = make_kernel(unit=True, reductions=True, frames=True, composition='numeric')
                stats, cache = {}, {}
                points = kernel(graph, witness=True, stats=stats, **OPTIONS, **config)
                self.assertEqual(tuple(p[:2] for p in points), expected)
                if graph.ops != ('EX', 'E0', 'E1'):
                    self.assertGreater(stats.get('exact_hits', 0), 0)
                for c, q, notes in points:
                    restored = expand(graph, notes, registry, cache)
                    actual = simulate(graph, restored, scalar_leaf='v2')
                    checked = analyze(graph, decode(graph, restored))
                    self.assertTrue(actual['valid'])
                    self.assertEqual((actual['peak'], actual['traffic']), (c, q))
                    self.assertEqual((checked['peak'], checked['traffic']), (c, q))

    def test_conditional_masks_entries_and_ownership(self):
        graph = ffn_stack(1)
        kernel, _ = make_kernel(unit=True, reductions=True, frames=True, composition='numeric')
        for bits in product((False, True), repeat=4):
            external = frozenset(t for t, on in zip(('X0', 'X1', 'W1_0', 'W2_0'), bits) if on)
            for entry, owned in product(('solve', 'group'), ((), ('H0', 'Z0'))):
                options = dict(OPTIONS, external=external, written=owned, entry=entry)
                expected = curve(graph, **options)
                for config in CONFIGS:
                    self.assertEqual(kernel(graph, **options, **config), expected)

    def test_real_transport_and_json_roundtrip(self):
        graph = twins()
        kernel, registry = make_kernel(unit=True, reductions=True, frames=True, composition='numeric')
        points = kernel(graph, witness=True, canonical_remainders=True, **OPTIONS)
        self.assertGreater(sum(n[0] == 'exact' and len(n) == 5 for _, _, ns in points for n in ns), 0)
        snapshot = dict(registry)
        for c, q, notes in points:
            restored = expand(graph, json.loads(json.dumps(notes)), registry, {})
            actual = simulate(graph, restored, scalar_leaf='v2')
            self.assertTrue(actual['valid'])
            self.assertEqual((actual['peak'], actual['traffic']), (c, q))
        self.assertEqual(registry, snapshot)

    def test_two_nested_maps_preserve_original_registry_namespace(self):
        graph = twins(3)
        kernel, registry = make_kernel(unit=True, reductions=True, frames=True, composition='numeric')
        points = kernel(graph, witness=True, **OPTIONS)
        note = next(n for _, _, ns in points for n in ns
                    if n[0] == 'exact' and registry[n[1]][0] == ('E0',) and not registry[n[1]][3])
        def mapping(a, b):
            return ({f'E{a}': f'E{b}'}, {f'{t}{a}': f'{t}{b}' for t in ('X', 'W', 'Y')},
                    {f'D{a}': f'D{b}', f'F{a}': f'F{b}', 'M': 'M'})
        m01, m12 = mapping(0, 1), mapping(1, 2)
        ns = kernel.__globals__
        transported = ns['flatten']((ns['_RENAME'], (ns['_RENAME'], (note,), m01), m12))
        self.assertEqual(transported[0][:4], note)
        original = native(graph, registry[note[1]], note[2], note[3], {})
        expected = flatten((_RENAME, flatten((_RENAME, original, m01)), m12))
        actual = expand(graph, transported, registry, {})
        self.assertEqual(actual, expected)
        _, names, ext, _, _, _ = registry[note[1]]
        sizes = dict(zip(names, ext))
        # This is a conditional child, so replay its mapped tile extents, not
        # the original root bounds (the enclosing F loop has already tiled it).
        sizes.update({m12[2].get(m01[2].get(v, v), m01[2].get(v, v)): sizes[v]
                      for v in ('M', 'D0', 'F0')})
        target = Graph(sizes, [('E2', graph.access['E2'])])
        report = simulate(target, actual, scalar_leaf='v2')
        compulsory = sum(target.size(t, ()) for t in target.tensors(target.ops))
        self.assertTrue(report['valid'])
        self.assertEqual((report['peak'], report['traffic']), (note[2], note[3] + compulsory))
        bad = (('exact', note[1], note[2], note[3], ({}, m01[1], m01[2])),)
        with self.assertRaises(KeyError):
            expand(graph, bad, registry, {})

    def test_both_tile_domains_and_nonbinary_sizes(self):
        graph = ffn_stack(1, m=2, d=3, f=2)
        for domain in ('halving', 'divisors'):
            kernel, registry = make_kernel(unit=True, reductions=True, frames=True, composition='numeric')
            options = dict(OPTIONS, tile_domain=domain, prune_infeasible_groups=True,
                           independent_ops=True, canonical_remainders=True)
            points = kernel(graph, witness=True, **options)
            self.assertEqual(tuple(p[:2] for p in points), curve(graph, **OPTIONS, tile_domain=domain))
            for c, q, notes in points:
                actual = simulate(graph, expand(graph, notes, registry, {}), scalar_leaf='v2')
                self.assertTrue(actual['valid'])
                self.assertEqual((actual['peak'], actual['traffic']), (c, q))

    def test_certificate_and_unit_session_all_orders(self):
        graph = graph_for('fork_join_tiny')
        orders, _, _ = select_orders(graph, False)
        for config in CONFIGS:
            session = RegionSession(graph, unit=True, certificate=True, reductions=True)
            for order in orders:
                ordered = resized(graph, graph.sizes, order)
                points = session.query(order, **config)
                self.assertEqual(tuple(p[:2] for p in points), curve(ordered, **OPTIONS))
                for c, q, notes in points:
                    actual = simulate(ordered, session.recover(notes), scalar_leaf='v2')
                    self.assertTrue(actual['valid'])
                    self.assertEqual((actual['peak'], actual['traffic']), (c, q))

    def test_scope_guards_and_legacy_interface(self):
        graph = twins()
        kernel, _ = make_kernel(unit=True, reductions=True)
        for change in (dict(spill_cost=1), dict(write_through=False), dict(split_shared=False),
                       dict(max_capacity=5), dict(scalar_leaf='v1'), dict(whole_span_cuts=()),
                       dict(root_groups=(graph.ops,))):
            with self.assertRaises(ValueError):
                kernel(graph, **(OPTIONS | change))
        with self.assertRaises(ValueError):
            RegionSession(graph, unit=True, shared=True, reductions=True)
        old = RegionSession(graph, unit=True)
        with self.assertRaises(ValueError):
            old.query(canonical_remainders=True)


if __name__ == '__main__':
    unittest.main()
