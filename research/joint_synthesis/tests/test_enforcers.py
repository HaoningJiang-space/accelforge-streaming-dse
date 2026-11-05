"""Explicit alternatives with competing resource/traffic requirements."""
from dataclasses import asdict
from itertools import product
import json

import pytest

from research.joint_synthesis.graph_ir import CostModel, Tensor, TwoMM
from research.joint_synthesis.physical_plan import Property, Schedule, CompletePlan, restore_plan
from research.joint_synthesis.schedule_rules import generate
from research.joint_synthesis.composition import conversion, enforcer_choices, compose
from research.joint_synthesis.resource_demand import summarize
from research.joint_synthesis.exhaustive_oracle import Runtime, convert, matrix, trace_complete, enumerate_plans, enumerate_complete
from research.joint_synthesis.hardware_ir import GridAxis, HardwareEnvelope, NormalizedPrices
from research.joint_synthesis.architecture_synth import synthesize
from research.joint_synthesis.conditional_frontier import frontier


def test_100_byte_conversion_tradeoff_executes_correct_release_order():
    tensor=Tensor('X',2,25);model=CostModel()
    source,target=Property(tensor,'row','sram'),Property(tensor,'col','sram')
    observed={}
    for route in enforcer_choices(source,target):
        r=Runtime(model);values=matrix(2,25,3)
        old=r.alloc(2,25,'sram','row',values,tensor=tensor)
        out=convert(r,old,source,target,route)
        expected=conversion(source,target,model,route)
        assert (r.peak,*r.vector[3:])==(expected.peak,expected.energy,expected.cycles,expected.traffic)
        assert r.logical(out)==values and r.current==100
        assert old not in r.copies and len(r.copies)==1
        observed[route]=expected
    assert (observed['direct'].peak,observed['direct'].traffic)==(200,0)
    assert (observed['spill_reload'].peak,observed['spill_reload'].traffic)==(100,200)
    assert observed['direct'].energy<observed['spill_reload'].energy
    assert observed['direct'].cycles<observed['spill_reload'].cycles
    # A 150-byte capacity permits just one of these conversions.
    assert {k for k,v in observed.items() if v.peak<=150}=={'spill_reload'}


@pytest.mark.parametrize('rows,cols',[(1,4),(4,1),(2,3),(2,25)])
@pytest.mark.parametrize('layout',['row','col'])
def test_both_enforcers_match_independent_execution_across_layouts_and_shapes(rows,cols,layout):
    tensor=Tensor('X',rows,cols);model=CostModel(5,3,7,11)
    source=Property(tensor,layout,'sram')
    target=Property(tensor,'col' if layout=='row' else 'row','sram')
    for route in ('direct','spill_reload'):
        r=Runtime(model);data=matrix(rows,cols,1)
        old=r.alloc(rows,cols,'sram',layout,data,tensor=tensor)
        out=convert(r,old,source,target,route)
        d=conversion(source,target,model,route)
        assert (r.peak,*r.vector[3:])==(d.peak,d.energy,d.cycles,d.traffic)
        assert r.logical(out)==data and r.current==tensor.nbytes


def fixed_kernel_demands():
    first,second=generate(TwoMM(2,1,25,1));schedule=Schedule(1,1,1,'ijk')
    p=next(p for p in first if p.schedule==schedule and p.delivered==Property(p.op.output,'row','sram'))
    q=next(q for q in second if q.schedule==schedule and q.required==Property(q.op.left,'col','sram'))
    return tuple(compose(summarize(p,CostModel()),summarize(q,CostModel()),CostModel(),route)
                 for route in ('direct','spill_reload'))


def test_fixed_interface_full_plans_and_budget_synthesis_choose_different_enforcers():
    demands=fixed_kernel_demands()
    assert {d.plan.enforcer:d.peak for d in demands}=={'direct':200,'spill_reload':104}
    assert len(frontier(demands))==2
    for d in demands:
        restored=restore_plan(json.loads(json.dumps(asdict(d.plan))))
        assert restored==d.plan and trace_complete(restored,CostModel()).vector==d.vector
    grid=HardwareEnvelope(GridAxis(1,1),GridAxis(1,1),GridAxis(1,220),GridAxis(1,16))
    family,_=synthesize(demands,grid,NormalizedPrices(),400)
    assert family.best_edp(150).demand.plan.enforcer=='spill_reload'
    assert family.best_edp(400).demand.plan.enforcer=='direct'
    assert family.best_edp(150).hardware.sram_bytes<family.best_edp(400).hardware.sram_bytes


def test_independent_and_production_enforcer_grammar_agree_for_all_small_pairs():
    first,second=enumerate_plans(TwoMM(1,1,1,1))
    actual={CompletePlan(a,b,route) for a,b in product(first,second)
            for route in enforcer_choices(a.delivered,b.required)}
    expected=set(enumerate_complete(first,second))
    assert actual==expected and len(actual)==162
    assert sum(p.enforcer=='spill_reload' for p in actual)==18
    old_payload=asdict(CompletePlan(first[0],second[0]))
    del old_payload['enforcer']
    assert restore_plan(old_payload)==CompletePlan(first[0],second[0],'direct')


def test_invalid_routes_are_rejected_before_conversion_actions():
    tensor=Tensor('X',1,2);model=CostModel()
    for source,target in product((Property(tensor,l,s)for l,s in product(('row','col'),('sram','dram'))),repeat=2):
        if source.location==target.location=='sram' and source.layout!=target.layout:continue
        r=Runtime(model);old=r.alloc(1,2,source.location,source.layout,[[1,2]],tensor=tensor)
        before=r.vector
        with pytest.raises(ValueError):convert(r,old,source,target,'spill_reload')
        with pytest.raises(ValueError):conversion(source,target,model,'spill_reload')
        assert r.vector==before and r.logical(old)==[[1,2]]
    first,second=generate(TwoMM())
    with pytest.raises(ValueError):CompletePlan(first[0],second[0],'unknown')
    with pytest.raises(ValueError):CompletePlan(first[0],second[0],'spill_reload')
    source=Property(tensor,'row','sram');target=Property(tensor,'col','sram')
    r=Runtime(model);old=r.alloc(1,2,'sram','row',[[1,2]],tensor=tensor);before=r.vector
    with pytest.raises(ValueError):convert(r,old,source,target,'unknown')
    with pytest.raises(ValueError):conversion(source,target,model,'unknown')
    assert r.vector==before and r.logical(old)==[[1,2]]
