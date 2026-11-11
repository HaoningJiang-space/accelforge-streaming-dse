"""Exact prefix interfaces, enumeration controls, and native witness replay."""
from itertools import product
import unittest

from .graph.curve import curve
from .graph.model import Graph, fork, residual
from .graph.stacks import ffn_stack
from .response.prefix import make_kernel
from .response.substitution import expand
from .simulate_nest import simulate
from .unified_search import mixed_branch_graph


OPTIONS = dict(partitions='dp', scalar_leaf='v2')


class PrefixSharingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kernels = [make_kernel(False)[0], make_kernel(True)[0]]

    def compare(self, g, **options):
        expected = curve(g, scalar_leaf='v2', partitions='enumerate', **options)
        self.assertEqual(curve(g, **OPTIONS, **options), expected)
        for fn in self.kernels:
            self.assertEqual(fn(g, **OPTIONS, **options), expected)

    def test_small_independent_enumeration_and_native_witnesses(self):
        graphs = [ffn_stack(1), fork(2,2,2,2,'ki'),
                  residual(2,1,2,2,False), residual(1,2,1,2,True),
                  mixed_branch_graph((1,2,1,2))]
        for g in graphs:
            for domain,entry in product(('halving','divisors'),('solve','group')):
                with self.subTest(ops=g.ops,domain=domain,entry=entry):
                    self.compare(g,tile_domain=domain,entry=entry)
                    if entry=='solve':
                        for fn in self.kernels:
                            for c,q,w in fn(g,witness=True,tile_domain=domain,**OPTIONS):
                                r=simulate(g,w,scalar_leaf='v2')
                                self.assertTrue(r['valid'])
                                self.assertEqual((r['peak'],r['traffic']),(c,q))

    def test_residency_ownership_and_boundary_flags(self):
        g=ffn_stack(1,m=2,d=1,f=2)
        tensors=('W1_0','W2_0','H0','Z0')
        for bits in product((False,True),repeat=len(tensors)):
            external=frozenset(t for t,b in zip(tensors,bits) if b)
            for owned in (frozenset(),frozenset({'H0','Z0'})):
                for entry in ('solve','group'):
                    self.compare(g,external=external,written=owned,entry=entry)

    def test_nonbinary_tiles_and_capacity_limit(self):
        g=Graph(dict(M=6,D=2,F=3),[('E',{'X':('M','D'),'W':('D','F'),'Y':('M','F')})])
        for domain,cap in product(('halving','divisors'),(3,9,float('inf'))):
            self.compare(g,tile_domain=domain,max_capacity=cap)

    def test_shared_gap_and_spill_options(self):
        g=Graph(dict(I=2,J=2),[
            ('P',{'A':('I','J'),'X':('I',)}),
            ('Q',{'B':('I',),'C':('I',),'Z':('I',)}),
            ('R',{'X':('I',),'Z':('I',),'Y':('I',)})])
        for spill,split,through in product((1,2),(False,True),(False,True)):
            self.compare(g,spill_cost=spill,split_shared=split,write_through=through)

    def test_unit_form_composition_and_projection_reuse(self):
        g=ffn_stack(1,m=4,d=2,f=2)
        base={};off={};on={}
        expected=curve(g,stats=base,**OPTIONS)
        for fn,stats in zip(self.kernels,(off,on)):
            self.assertEqual(fn(g,stats=stats,**OPTIONS),expected)
        self.assertEqual(off['dp_transitions'],base['dp_transitions'])
        self.assertLess(on['dp_transitions'],off['dp_transitions'])
        self.assertLess(on['prefix_cache']['misses'],off['prefix_cache']['misses'])
        fn,registry=make_kernel(True,unit=True);cache={}
        actual=fn(g,witness=True,**OPTIONS)
        self.assertEqual(tuple(p[:2] for p in actual),expected)
        for c,q,w in actual:
            w=expand(g,w,registry,cache)
            r=simulate(g,w,scalar_leaf='v2')
            self.assertTrue(r['valid']);self.assertEqual((r['peak'],r['traffic']),(c,q))

    def test_unproved_modes_are_rejected(self):
        fn=self.kernels[1];g=ffn_stack(1)
        for change in (dict(scalar_leaf='v1'),dict(grid=2),dict(canonical_spans=True),
                       dict(whole_span_cuts=()),dict(root_groups=(g.ops,))):
            with self.assertRaises(ValueError):fn(g,**(OPTIONS|change))


if __name__=='__main__':unittest.main()
