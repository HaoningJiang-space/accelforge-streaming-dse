import unittest
from research.index_coupling.graph.model import Graph, attention, ffn, fork, residual
from research.index_coupling.graph.stacks import attention_stack, ffn_stack
from research.index_coupling.graph.widths import widths
from research.index_coupling.graph.curve import curve
from research.index_coupling.simulate_nest import simulate


class WidthTests(unittest.TestCase):
    def test_known_motifs_and_stack_growth_without_search(self):
        for n in (2, 4, 6):
            w = widths(fork(2, 2, 2, 2, 'k' * n))
            self.assertEqual(w['w_cut'], 1)
            self.assertEqual(w['w_obl_conditional_upper'], n + 1)
        for depth in (4, 12, 24):
            w = widths(residual(2, 2, 2, depth, True))
            self.assertEqual((w['w_cut'], w['w_obl_conditional_upper']), (2, 2))
        for layers in (1, 2, 4, 8):
            for g in (ffn_stack(layers), attention_stack(layers)):
                w = widths(g)
                self.assertEqual(w['w_cut'], 1)
                self.assertEqual(len(w['root_legal_obligations']['M']), 2 * layers)
            w = widths(ffn_stack(layers, training=True))
            self.assertEqual(w['w_cut'], 5 * layers)
            self.assertEqual(len(w['root_legal_obligations']['M']), 4 * layers)

    def test_single_layers_match_existing_models(self):
        original = ffn(2, 2, 2)
        forward = Graph(original.sizes, [(op, original.access[op]) for op in original.ops[:3]])
        for a, b in ((ffn_stack(1), forward), (ffn_stack(1, training=True), original),
                     (attention_stack(1), attention(2, 2, 2, 2))):
            self.assertEqual(curve(a, partitions='dp'), curve(b, partitions='dp'))

    def test_training_order_and_execution(self):
        g = ffn_stack(2, m=1, d=1, f=1)
        seen, produced = set(), g.produced()
        for op in g.ops:
            inputs = set(g.access[op]) - {g.output(op)}
            self.assertLessEqual(inputs & produced, seen)
            seen.add(g.output(op))
        for c, q, w in curve(g, witness=True, partitions='dp'):
            actual = simulate(g, w)
            self.assertTrue(actual['valid'])
            self.assertEqual((actual['peak'], actual['traffic']), (c, q))


if __name__ == '__main__':
    unittest.main()
