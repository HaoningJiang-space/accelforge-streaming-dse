"""Checks for grammar v2 (GRAMMAR_V2.md). Each test runs in seconds.

python -m unittest research.index_coupling.test_scalar_leaf_v2
"""
from itertools import combinations
import unittest

from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph, fork, residual
from research.index_coupling.graph.stacks import ffn_stack
from research.index_coupling.simulate_nest import simulate


def extra(graph, external, **options):
    """Internal response: curve traffic minus the compulsory transfers it adds."""
    inputs = graph.consumed() - graph.produced()
    outputs = graph.produced() - graph.consumed()
    compulsory = sum(graph.size(t, graph.sizes) for t in (inputs | outputs) - external)
    return [(c, q - compulsory) for c, q in curve(graph, partitions='dp', external=external, **options)]


def violations(graph, leaf, limit=2):
    """Pairs (R, W) with Q_{R+W}(C) > Q_R(C) at some capacity, over small R."""
    tensors = sorted(graph.tensors(graph.ops))
    found = []
    for k in range(limit + 1):
        for resident in combinations(tensors, k):
            base = extra(graph, frozenset(resident), scalar_leaf=leaf)
            for w in tensors:
                if w in resident:
                    continue
                more = extra(graph, frozenset(resident) | {w}, scalar_leaf=leaf)
                top = max(c for c, _ in base + more)
                if any(traffic_at(c, base) is not None and
                       (traffic_at(c, more) is None or traffic_at(c, more) > traffic_at(c, base))
                       for c in range(top + 1)):
                    found.append((resident, w))
    return found


def chain():
    # Census counterexample: residual EH1..EH3 at extents I=1, K=2, L=2.
    g = residual(1, 2, 2, 4, False)
    return Graph(g.sizes, [(o, g.access[o]) for o in ('EH1', 'EH2', 'EH3')])


class ScalarLeafV2(unittest.TestCase):
    def test_counterexample_is_monotone_only_in_v2(self):
        g = chain()
        self.assertTrue(violations(g, 'v1'))
        self.assertEqual(violations(g, 'v2'), [])

    def test_small_graphs_monotone_in_v2(self):
        for g in (fork(1, 2, 2, 1, 'kk'), residual(1, 2, 2, 3, True), ffn_stack(1, m=1)):
            self.assertEqual(violations(g, 'v2', limit=1), [])

    def test_v2_never_worse_and_replays(self):
        for g in (fork(2, 2, 2, 2, 'kk'), residual(2, 2, 2, 4, False), ffn_stack(1)):
            v1 = curve(g, partitions='dp')
            v2 = curve(g, witness=True, partitions='dp', scalar_leaf='v2')
            for c in range(max(p[0] for p in v1) + 1):
                if traffic_at(c, v1) is not None:
                    self.assertLessEqual(traffic_at(c, [p[:2] for p in v2]), traffic_at(c, v1))
            for c, q, w in v2:
                run = simulate(g, w, scalar_leaf='v2')
                self.assertTrue(run['valid'])
                self.assertEqual((run['peak'], run['traffic']), (c, q))

    def test_zero_traffic_point_is_maxlive(self):
        # All extents one: every live tensor is scalar (Lemma B).
        for g in (fork(1, 1, 1, 1, 'kki'), residual(1, 1, 1, 5, True), ffn_stack(2, m=1, d=1, f=1)):
            ops = g.ops
            uses = {t: [i for i, o in enumerate(ops) if t in g.access[o]] for t in g.tensors(ops)}
            maxlive = max(len(g.access[o]) + sum(1 for t, u in uses.items()
                                                  if u[0] < i < u[-1] and t not in g.access[o])
                          for i, o in enumerate(ops))
            points = extra(g, frozenset(), scalar_leaf='v2')
            self.assertEqual(min(c for c, q in points if q == 0), maxlive)
            self.assertEqual(extra(g, frozenset())[0], (len(g.tensors(ops)), 0))

    def test_default_is_v1(self):
        g = residual(2, 2, 2, 4, False)
        self.assertEqual(curve(g, partitions='dp'), curve(g, partitions='dp', scalar_leaf='v1'))
        with self.assertRaises(ValueError):
            curve(g, scalar_leaf='v3')


if __name__ == '__main__':
    unittest.main()
