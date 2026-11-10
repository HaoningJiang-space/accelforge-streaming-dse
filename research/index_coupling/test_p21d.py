"""Implementation checks on previously seen tiny graphs; no held-out curves."""
import unittest
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph, residual
from research.index_coupling.graph.structural_cuts import structural_cuts
from research.index_coupling.simulate_nest import simulate


class StructuralCutTests(unittest.TestCase):
    def test_incidence_only_and_local_inputs_do_not_select_cut_one(self):
        g = residual(2,2,2,2,False)
        rule = structural_cuts(g)
        self.assertEqual(rule['positions'], [2,3])
        self.assertEqual(rule['excluded'], [1])
        larger = residual(64,32,16,2,False)  # topology only, no solver call
        self.assertEqual(rule, structural_cuts(larger))
        renamed = Graph(g.sizes, [(f'n{i}', {f't_{t}':d for t,d in g.access[op].items()})
                                 for i,op in enumerate(g.ops)])
        self.assertEqual(rule['positions'], structural_cuts(renamed)['positions'])
        events = rule['reasons'][2]['events']
        self.assertTrue(any(e['kind']=='last_crossing_use' and e['tensor']=='H0' for e in events))

    def test_all_cuts_default_and_seen_archives(self):
        import json
        from pathlib import Path
        for reads_x in (False,True):
            g = residual(2,2,2,2,reads_x)
            expected = json.loads((Path(__file__).parent/'results/p21'/
                                   f'case_{int(reads_x):02d}.json').read_text())['result']['interfaces'][0]['curves']['unrestricted']
            original = curve(g)
            self.assertEqual([list(p) for p in original], expected)
            self.assertEqual(curve(g,whole_span_cuts=range(1,len(g.ops))), original)
            self.assertEqual(curve(g,whole_span_cuts=()), ())
            restricted = curve(g,whole_span_cuts=structural_cuts(g)['positions'],witness=True)
            for c,q,w in restricted:
                self.assertGreaterEqual(q,traffic_at(c,original))
                actual=simulate(g,w)
                self.assertTrue(actual['valid'])
                self.assertEqual((actual['peak'],actual['traffic']),(c,q))

    def test_bad_interfaces(self):
        g=residual(2,2,2,2,False)
        for kwargs in (dict(whole_span_cuts={0}),dict(whole_span_cuts={4}),
                       dict(whole_span_cuts={1.5}),dict(whole_span_cuts={1},entry='group'),
                       dict(whole_span_cuts={1},root_groups=(g.ops,))):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                curve(g,**kwargs)


if __name__=='__main__':
    unittest.main()
