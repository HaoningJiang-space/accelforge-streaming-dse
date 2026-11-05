import pytest

from research.joint_synthesis.graph_ir import TwoMM, CostModel
from research.joint_synthesis.physical_plan import Schedule
from research.joint_synthesis.schedule_rules import generate
from research.joint_synthesis.resource_demand import summarize
from research.joint_synthesis.composition import compose
from research.joint_synthesis.graph_dp import solve
from research.joint_synthesis.hardware_ir import GridAxis, HardwareEnvelope, NormalizedPrices
from research.joint_synthesis.architecture_synth import synthesize, solve_joint
from research.joint_synthesis.exhaustive_oracle import exhaustive
from research.joint_synthesis.validate_architecture import validate_configuration


def envelope():
    return HardwareEnvelope(GridAxis(1,3),GridAxis(1,5),GridAxis(4,48,4),GridAxis(1,9))


def test_hardware_rounds_demands_up_and_budget_bandwidth_down():
    root,_=solve(TwoMM(),CostModel())
    demand=next(d for d in root if (d.pe_x,d.pe_y,d.peak)==(2,2,24))
    grid=HardwareEnvelope(GridAxis(1,4,2),GridAxis(1,4,2),GridAxis(5,50,5),GridAxis(2,11,3))
    result,_=synthesize([demand],grid,NormalizedPrices(2,1,3),70)
    assert {(d.hardware.px,d.hardware.py,d.hardware.sram_bytes,d.hardware.bandwidth)
            for d in result.designs}=={(3,3,25,b)for b in (2,5,8)}


def test_stages_cannot_choose_two_different_global_array_shapes():
    first,second=generate(TwoMM())
    p=next(p for p in first if p.schedule==Schedule(2,1,1,'ijk') and
           (p.delivered.layout,p.delivered.location)==('row','sram'))
    q=next(p for p in second if p.schedule==Schedule(1,2,1,'ijk') and
           (p.required.layout,p.required.location)==('row','sram'))
    demand=compose(summarize(p,CostModel()),summarize(q,CostModel()),CostModel())
    assert (demand.pe_x,demand.pe_y,demand.peak)==(2,2,16)
    rejected,_=synthesize([demand],envelope(),budget_ceiling=34)
    assert not rejected.designs
    accepted,_=synthesize([demand],envelope(),budget_ceiling=35)
    best=accepted.best_edp(35)
    assert (best.hardware.px,best.hardware.py,best.resource_cost)==(2,2,35)


def test_normalized_budget_changes_the_selected_global_hardware():
    root,_=solve(TwoMM(),CostModel())
    compiled,_=synthesize(root,envelope())
    choices=[compiled.best_edp(b)for b in (16,36,64)]
    assert len({(d.hardware.px,d.hardware.py)for d in choices})==3
    for d,b in zip(choices,(16,36,64)):
        assert d.resource_cost<=b
        for stage in (d.demand.plan.producer,d.demand.plan.consumer):
            assert stage.schedule.ti<=d.hardware.px and stage.schedule.tj<=d.hardware.py


def test_budget_queries_do_not_silently_extrapolate_incomplete_coverage():
    root,_=solve(TwoMM(),CostModel())
    result,_=synthesize(root,envelope(),budget_ceiling=64)
    assert result.best_edp(0) is None
    assert result.best_edp(64) is not None
    for unsupported in (-1,65,1.5,True):
        with pytest.raises(ValueError):result.query_budget(unsupported)
    empty,_=synthesize([],envelope(),budget_ceiling=64)
    assert empty.query_budget(64)==() and empty.best_edp(64) is None


def test_nonmonotone_or_undefined_normalized_prices_are_rejected():
    with pytest.raises(ValueError):NormalizedPrices(0,1,3)
    with pytest.raises(ValueError):NormalizedPrices(1,-1,3)
    with pytest.raises(ValueError):GridAxis(4,3)
    with pytest.raises(ValueError):GridAxis(1,3,0)


def test_joint_graph_entrypoint_and_budget_queries_do_not_search_each_architecture(monkeypatch):
    from research.joint_synthesis import graph_dp
    original=graph_dp.solve
    calls=[]
    def counted(*args,**kwargs):
        calls.append(1)
        return original(*args,**kwargs)
    monkeypatch.setattr(graph_dp,'solve',counted)
    family,stats=solve_joint(TwoMM(),CostModel(),envelope(),budget_ceiling=64)
    for budget in range(65):family.query_budget(budget)
    assert len(calls)==stats['graph_dp_calls']==1
    assert stats['graph_dp']['architecture_points_supplied']==0
    assert stats['hardware_binding']['architecture_mapper_calls']==0


@pytest.mark.parametrize('grid,prices',[
    (HardwareEnvelope(GridAxis(1,3),GridAxis(1,3),GridAxis(4,28,4),GridAxis(1,5)),NormalizedPrices()),
    (HardwareEnvelope(GridAxis(1,4,2),GridAxis(2,5,2),GridAxis(3,30,3),GridAxis(3,8,2)),NormalizedPrices(2,2,1)),
])
def test_complete_joint_frontier_and_all_budgets_equal_full_hardware_oracle(grid,prices):
    root,_=solve(TwoMM(),CostModel())
    observed,_=exhaustive(TwoMM(),CostModel())
    result=validate_configuration(root,observed,CostModel(),grid,prices,64)
    assert result['exact_full_joint_frontier_equal']
    assert result['all_budget_et_frontiers_equal'] and result['all_budget_minimum_edp_equal']
    assert result['budget_queries_checked']==65
    assert result['design_witnesses_checked']>0
    assert result['synthesis']['architecture_mapper_calls']==0
    assert result['same_root_grid_frontier_equal']
    assert result['controlled_same_root_grid']['unique_measured_demands']==len(root)
