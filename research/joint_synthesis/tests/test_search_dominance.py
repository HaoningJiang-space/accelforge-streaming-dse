"""Every removed local state has a final survivor valid for every continuation."""
from itertools import product

from research.joint_synthesis.graph_ir import TwoMM, CostModel
from research.joint_synthesis.schedule_rules import generate
from research.joint_synthesis.resource_demand import summarize
from research.joint_synthesis.composition import compose, enforcer_choices
from research.joint_synthesis.graph_dp import solve
from research.joint_synthesis.exhaustive_oracle import trace_complete


def test_every_local_prune_has_a_final_dominator_for_all_grammar_continuations():
    graph=TwoMM(1,2,2,1);model=CostModel(3,2,7,5);witnesses={}
    solve(graph,model,witnesses=witnesses)
    first,second=generate(graph)
    assert all(witnesses.values())
    checks=0
    for side,records in witnesses.items():
        for w in records:
            p,q=w.dominator,w.removed
            prop=lambda s:s.plan.delivered if side=='prefix' else s.plan.required
            assert prop(p)==prop(q)
            assert all(a<=b for a,b in zip(p.vector,q.vector))
            for continuation in second if side=='prefix' else first:
                r=summarize(continuation,model)
                left,right=(p,r) if side=='prefix' else (r,p)
                for route in enforcer_choices(left.plan.delivered,right.plan.required):
                    better=compose(left,right,model,route)
                    worse=compose(q,r,model,route) if side=='prefix' else compose(r,q,model,route)
                    assert all(a<=b for a,b in zip(better.vector,worse.vector))
                    assert trace_complete(better.plan,model).vector==better.vector
                    assert trace_complete(worse.plan,model).vector==worse.vector
                    checks+=1
    assert checks>100


def test_witnesses_resolve_transitive_removal_and_equal_vector_sources():
    from dataclasses import dataclass
    from research.joint_synthesis.conditional_frontier import frontier
    @dataclass(frozen=True)
    class State:
        name: str
        vector: tuple
    a,b,c,d=(State('a',(3,3)),State('b',(2,2)),State('c',(1,1)),State('d',(1,1)))
    witnesses=[];kept=frontier([a,b,c,d],witnesses=witnesses)
    assert kept==[c] and {w.removed for w in witnesses}=={a,b,d}
    assert all(w.dominator is c for w in witnesses)
