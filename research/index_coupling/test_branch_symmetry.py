"""Whole-branch automorphisms, decorated continuations and negative controls."""
from dataclasses import replace
import unittest

from .fork_order_oracle import replay_private_boundary
from .graph.analysis import traffic_at
from .graph.branch_symmetry import (BranchOrderOracle, branch_graph, branch_permutation,
    branch_automorphisms, is_automorphism, continuation_ops, continuation_states,
    induced, topological_orders)


class BranchSymmetryTests(unittest.TestCase):
    def test_entire_incidence_is_checked(self):
        for join in (False,True):
            g=branch_graph(join=join);swap=branch_permutation(g,(1,0))
            self.assertTrue(is_automorphism(g,swap))
            partial=replace(swap,ops=dict(swap.ops,H0='H0',H1='H1'))
            self.assertFalse(is_automorphism(g,partial))
            self.assertEqual(len(branch_automorphisms(g,2)),2)
        g=branch_graph(tails=(True,False))
        self.assertFalse(is_automorphism(g,branch_permutation(g,(1,0))))
        self.assertEqual(len(branch_automorphisms(g,2)),1)

    def test_topological_orders_and_certified_orbits(self):
        for m,total,orbits in ((2,6,3),(3,90,15)):
            for join in (False,True):
                g=branch_graph(branches=m,join=join);group=branch_automorphisms(g,m)
                orders=list(topological_orders(g));self.assertEqual(len(orders),total)
                self.assertEqual(len({min(tuple(p.ops[o] for o in order) for p in group) for order in orders}),orbits)

    def test_ready_input_profile_counts(self):
        for m,join,total,orbits in ((2,False,81,45),(2,True,100,55),(3,False,729,165),(3,True,1000,220)):
            g=branch_graph(branches=m,join=join);solver=BranchOrderOracle(g,m)
            states=list(continuation_states(g,m));self.assertEqual(len(states),total)
            self.assertEqual(len({solver.canonical(s['ops'],s['external'])[0] for s in states}),orbits)
            for s in states:
                sub=induced(g,s['ops'])
                self.assertTrue(set(s['external']) <= sub.consumed()-sub.produced())

    def test_root_oracle_and_restored_witnesses(self):
        for join in (False,True):
            g=branch_graph(join=join)
            a=BranchOrderOracle(g,2);b=BranchOrderOracle(g,2,quotient=False)
            for resident in ((),('C0','D0'),('C1','D1')):
                pa=a.query(external=resident);pb=b.query(external=resident)
                self.assertEqual(tuple(p[:2] for p in pa),tuple(p[:2] for p in pb))
                for c,q,p in pa:self.assertTrue(replay_private_boundary(g,resident,c,q,p)['exact'])
            self.assertEqual(a.stats['misses'],2)

    def test_progress_and_residency_must_be_joint(self):
        g=branch_graph();s=BranchOrderOracle(g,2)
        ops=continuation_ops(g,(1,0));other=continuation_ops(g,(0,1))
        ready=s.query(ops,external={'D0'});misses=s.stats['misses']
        moved=s.query(other,external={'D1'})
        self.assertEqual(s.stats['misses'],misses)
        self.assertEqual(tuple(p[:2] for p in ready),tuple(p[:2] for p in moved))
        future=s.query(ops,external={'D1'})
        self.assertEqual((traffic_at(3,ready),traffic_at(3,future)),(44,48))
        for selected,resident,points in ((ops,{'D0'},ready),(other,{'D1'},moved),(ops,{'D1'},future)):
            for c,q,p in points:self.assertTrue(replay_private_boundary(induced(g,selected),resident,c,q,p)['exact'])

    def test_cross_operator_pairing_and_ownership_are_not_erased(self):
        g=branch_graph();s=BranchOrderOracle(g,2)
        same=s.query(external={'C0','D0'});split=s.query(external={'C0','D1'})
        self.assertEqual((traffic_at(3,same),traffic_at(3,split)),(64,76))
        a=s.canonical(g.ops,{'C0'},{'U0'})[0]
        self.assertNotEqual(a,s.canonical(g.ops,{'C0'},{'U1'})[0])
        self.assertNotEqual(a,s.canonical(g.ops,{'C0'},())[0])
        self.assertNotEqual(a,s.canonical(g.ops,{'C0'},{'U0'},'group')[0])


if __name__=='__main__':unittest.main()
