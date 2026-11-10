"""Exact-reuse collision controls, feasibility boundaries, and full replays."""
from itertools import product
import unittest

from .graph.curve import curve
from .graph.model import Graph, fork, residual
from .graph.remainder import InfeasibleGroups, RemainderNames
from .graph.stacks import ffn_stack, attention_stack
from .run_ancestor_width import control
from .simulate_nest import simulate


def renamed_pair():
    return Graph(dict(A=2,B=3,C=4,U=3,V=4,W=2),[
        ('P',{'a':('A','B'),'b':('B','C'),'c':('A','C')}),
        ('Q',{'d':('W','U'),'e':('U','V'),'f':('W','V')})])


class RemainderSearchTests(unittest.TestCase):
    def test_wl_collision_requires_exact_isomorphism(self):
        # Both rank/tensor incidence graphs are 2-regular and WL-equivalent:
        # one cycle of length 12, versus two disjoint cycles of length 6.
        sizes = {f'{p}{i}':2 for p in ('u','v') for i in range(6)}
        a = {f'a{i}':(f'u{i}',f'u{(i+1)%6}') for i in range(6)}
        b = {f'b{i}':(f'v{i}',f'v{(i//3)*3+(i+1)%3}') for i in range(6)}
        graph = Graph(sizes,[('P',dict(a,y=())),('Q',dict(b,z=()))])
        names = sorted(sizes)
        index = RemainderNames(graph,names)
        args = ((2,)*12,frozenset(),frozenset())
        left = index.describe('solve',('P',),*args)
        right = index.describe('solve',('Q',),*args)
        self.assertEqual(left.bucket,right.bucket)
        self.assertIsNone(index.exact_map(left,right))
        index.state('solve',('P',),*args)
        representative,restore = index.state('solve',('Q',),*args)
        self.assertEqual(representative[0],('Q',))
        self.assertIsNone(restore)
        self.assertEqual(index.counts['bucket_nonmatches'],1)

    def test_rank_mapping_and_safe_matching_cutoff(self):
        graph = renamed_pair()
        names = sorted(graph.sizes)
        ext = tuple(graph.sizes[v] for v in names)
        index = RemainderNames(graph,names)
        index.state('solve',('P',),ext,frozenset(),frozenset())
        representative,restore = index.state('solve',('Q',),ext,frozenset(),frozenset())
        self.assertEqual(representative[0],('P',))
        self.assertEqual(restore[2],{'A':'W','B':'U','C':'V'})
        limited = RemainderNames(graph,names,match_budget=0)
        limited.state('solve',('P',),ext,frozenset(),frozenset())
        representative,restore = limited.state('solve',('Q',),ext,frozenset(),frozenset())
        self.assertEqual(representative[0],('Q',))
        self.assertIsNone(restore)
        self.assertEqual(limited.counts['match_cutoffs'],1)

    def test_resident_domains_not_resident_identity_or_multiplicity(self):
        graph = Graph(dict(I=2,K=2),[
            ('P',{'x':('I',),'a':('I',),'y':('I',)}),
            ('Q',{'z':('K',),'w':('K',)})])
        index = RemainderNames(graph,('I','K'))
        index.state('solve',('P',),(2,2),frozenset({'a','y'}),frozenset())
        rep,restore = index.state('solve',('Q',),(2,2),frozenset({'w'}),frozenset())
        self.assertEqual(rep[0],('P',))
        self.assertEqual(restore[1],{'x':'z'})
        graph = Graph(dict(I=2,J=2,K=2),[
            ('P',{'x':('I',),'a':('J',),'y':('I',)}),
            ('Q',{'z':('K',),'w':('K',)})])
        index = RemainderNames(graph,('I','J','K'))
        index.state('solve',('P',),(2,2,2),frozenset({'a','y'}),frozenset())
        rep,restore = index.state('solve',('Q',),(2,2,2),frozenset({'w'}),frozenset())
        self.assertEqual(rep[0],('Q',))
        self.assertIsNone(restore)

    def test_scalar_leaf_and_entry_cannot_be_discarded(self):
        graph = fork(1,2,1,2,'k')
        checker = InfeasibleGroups(graph,('I','J','K','L'))
        empty, resident = frozenset(),frozenset({'A','B','C0','U0'})
        self.assertTrue(checker.empty(graph.ops,(1,2,1,2),empty))
        self.assertFalse(checker.empty(graph.ops,(1,2,1,2),resident))
        index = RemainderNames(graph,('I','J','K','L'))
        index.state('solve',graph.ops,(1,2,1,2),empty,empty)
        _,restore = index.state('group',graph.ops,(1,2,1,2),empty,empty)
        self.assertIsNone(restore)
        for canonical,precheck in product((False,True),repeat=2):
            kwargs = dict(canonical_remainders=canonical,prune_infeasible_groups=precheck)
            self.assertEqual(curve(graph,entry='group',**kwargs),())
            self.assertEqual(curve(graph,entry='group',external=resident,**kwargs),((1,0),))
            self.assertEqual(curve(graph,**kwargs),((3,8),))

    def test_four_arms_complete_curves_and_witnesses(self):
        graphs = (renamed_pair(),fork(2,2,2,2,'kki'),fork(3,2,2,3,'ki'),
                  residual(2,2,2,4,True),ffn_stack(2),attention_stack(2),control(4))
        for graph in graphs:
            expected = curve(graph,partitions='dp')
            for method in ('enumerate','dp'):
                for canonical,precheck in product((False,True),repeat=2):
                    with self.subTest(ops=graph.ops,method=method,canonical=canonical,precheck=precheck):
                        stats = {}
                        points = curve(graph,partitions=method,canonical_remainders=canonical,
                                       prune_infeasible_groups=precheck,witness=True,stats=stats)
                        self.assertEqual(tuple(p[:2] for p in points),expected)
                        for c,q,w in points:
                            actual = simulate(graph,w)
                            self.assertTrue(actual['valid'])
                            self.assertEqual((actual['peak'],actual['traffic']),(c,q))
                        if canonical:
                            self.assertLessEqual(stats['remainder']['aliases']['currsize'],4096)

    def test_conditional_queries_and_supported_options(self):
        graph = fork(2,2,2,2,'ki')
        private = sorted(graph.tensors(graph.ops)-{'X'})
        for bits in product((False,True),repeat=len(private)):
            resident = frozenset(t for t,b in zip(private,bits) if b)
            for entry in ('solve','group'):
                expected = curve(graph,external=resident,entry=entry,partitions='dp')
                self.assertEqual(curve(graph,external=resident,entry=entry,partitions='dp',
                                       canonical_remainders=True,prune_infeasible_groups=True),expected)
        for opts in (dict(spill_cost=1),dict(write_through=False),dict(split_shared=False),
                     dict(legacy_nested_writes=True),dict(ownership_projection=False),
                     dict(independent_ops=True),dict(tile_domain='divisors'),dict(written={'X'})):
            self.assertEqual(curve(graph,canonical_remainders=True,prune_infeasible_groups=True,**opts),
                             curve(graph,**opts))

    def test_unsupported_contracts_are_rejected(self):
        graph = fork(2,2,2,2,'ki')
        for flags in (dict(canonical_remainders=True),dict(prune_infeasible_groups=True)):
            for opts in (dict(grid=1.2),dict(max_capacity=4),dict(whole_span_cuts=()),
                         dict(root_groups=(graph.ops,))):
                with self.assertRaises(ValueError):
                    curve(graph,**flags,**opts)
        with self.assertRaises(ValueError):
            curve(graph,canonical_spans=True,canonical_remainders=True)
        multi = Graph(dict(I=2),[('P',{'A':('I',),'Y':('I',)}),('Q',{'B':('I',),'Y':('I',)})])
        with self.assertRaises(ValueError):
            curve(multi,canonical_remainders=True)


if __name__ == '__main__':
    unittest.main()
