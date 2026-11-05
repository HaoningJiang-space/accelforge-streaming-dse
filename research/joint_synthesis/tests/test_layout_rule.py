from dataclasses import replace

import pytest

from research.joint_synthesis.graph_ir import TwoMM, CostModel
from research.joint_synthesis.physical_plan import Property
from research.joint_synthesis.requirements import PhysicalRequirements
from research.joint_synthesis.schedule_rules import generate
from research.joint_synthesis.resource_demand import summarize
from research.joint_synthesis.composition import compose
from research.joint_synthesis.graph_dp import solve
from research.joint_synthesis.exhaustive_oracle import trace_complete
from research.joint_synthesis.tests.test_enforcers import fixed_kernel_demands


@pytest.mark.parametrize('model',[CostModel(),CostModel(3,2,7,5),CostModel(0,0,0,0)])
def test_each_removed_sram_conversion_has_an_executable_identity_witness(model):
    witnesses=[];root,stats=solve(TwoMM(),model,layout_witnesses=witnesses)
    baseline,control=solve(TwoMM(),model,layout_pruning=False)
    assert {d.vector for d in root}=={d.vector for d in baseline}
    assert witnesses and stats['materialized_complete_pairs']<control['materialized_complete_pairs']
    for w in witnesses:
        better=compose(w.replacement_prefix,w.consumer,model,'direct')
        assert w.replacement_prefix.plan.delivered==w.consumer.plan.required
        assert trace_complete(better.plan,model).vector==better.vector
        for route in w.removed_enforcers:
            worse=compose(w.original_prefix,w.consumer,model,route)
            assert all(a<=b for a,b in zip(better.vector,worse.vector))
            assert trace_complete(worse.plan,model).vector==worse.vector


def test_predicted_third_fixed_kernel_plan_executes_at_104_bytes_with_lower_cost():
    direct,spill=fixed_kernel_demands()
    p=direct.plan.producer;q=direct.plan.consumer
    matched=replace(p,delivered=q.required)
    identity=compose(summarize(matched,CostModel()),summarize(q,CostModel()),CostModel())
    assert identity.vector==(1,1,104,3740,252,304)
    assert trace_complete(identity.plan,CostModel()).vector==identity.vector
    assert all(a<=b for a,b in zip(identity.vector,spill.vector))
    assert all(a<=b for a,b in zip(identity.vector,direct.vector))


def test_fixed_producer_interface_keeps_the_conversion_domain_complete():
    graph=TwoMM();tensor=graph.operators[0].output
    req=PhysicalRequirements(frozenset([Property(tensor,'row','sram')]),
                             frozenset([Property(tensor,'col','sram')]))
    root,stats=solve(graph,CostModel(),requirements=req)
    control,_=solve(graph,CostModel(),requirements=req,layout_pruning=False)
    assert root and {d.vector for d in root}=={d.vector for d in control}
    assert stats['layout_pairs_skipped']==stats['layout_alternatives_skipped']==0
    assert all(d.plan.producer.delivered in req.producer_delivered for d in root)
    # An empty explicit requirement means no allowed property, never "unknown".
    empty,_=solve(graph,CostModel(),requirements=PhysicalRequirements(frozenset()))
    assert not empty
    with pytest.raises(ValueError):generate(graph,PhysicalRequirements(frozenset([Property(
        graph.operators[0].left,'row','sram')])))
