from itertools import product
import unittest

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import fork,residual
from research.index_coupling.graph.stacks import ffn_stack,attention_stack
from research.index_coupling.simulate_nest import simulate
from .c2 import make_c2_kernel,lower_dominated


class C2Tests(unittest.TestCase):
    def test_whole_lower_frontier_and_capacity_shift(self):
        self.assertTrue(lower_dominated([(3,8),(5,2)],[(1,3),(3,0)],2,2,2))
        self.assertFalse(lower_dominated([(3,8),(5,2)],[(1,2),(3,0)],2,2,2))
        self.assertFalse(lower_dominated([(4,0)],[(1,0)],2,0,1))

    def test_v2_four_arms_both_partition_solvers_and_replay(self):
        kernel=make_c2_kernel()
        pruned=0
        for graph in (fork(2,2,2,2,'kki'),residual(2,2,3,3,True),ffn_stack(2),attention_stack(2)):
            reference=curve(graph,partitions='enumerate',scalar_leaf='v2')
            for mode in ('enumerate','dp'):
                for remainder,empty in product((False,True),repeat=2):
                    stats={}
                    points=kernel(graph,partitions=mode,scalar_leaf='v2',witness=True,c2_stats=stats,
                        canonical_remainders=remainder,prune_infeasible_groups=empty)
                    self.assertEqual(tuple(p[:2] for p in points),reference)
                    pruned+=stats['choices_pruned']
                    for c,q,w in points:
                        actual=simulate(graph,w,scalar_leaf='v2')
                        self.assertTrue(actual['valid'])
                        self.assertEqual((actual['peak'],actual['traffic']),(c,q))
        self.assertGreater(pruned,0)

    def test_conditional_entries_and_v1_rejection(self):
        graph=fork(2,3,2,2,'ki')
        kernel=make_c2_kernel()
        private=sorted(graph.tensors(graph.ops)-{'X'})
        for bits in product((False,True),repeat=len(private)):
            resident=frozenset(t for t,b in zip(private,bits) if b)
            for entry in ('solve','group'):
                options=dict(scalar_leaf='v2',partitions='dp',external=resident,entry=entry)
                self.assertEqual(kernel(graph,**options),curve(graph,**options))
        with self.assertRaises(ValueError):kernel(graph,scalar_leaf='v1')
        with self.assertRaises(ValueError):kernel(graph,scalar_leaf='v2',grid=1.1)


if __name__=='__main__':unittest.main()
