"""Cross-shape full-grammar checks and actual capacity/bandwidth boundaries."""
import pytest

from research.joint_synthesis.graph_ir import CostModel, Tensor, TwoMM
from research.joint_synthesis.physical_plan import Property
from research.joint_synthesis.composition import conversion
from research.joint_synthesis.exhaustive_oracle import Runtime, convert, trace_complete
from research.joint_synthesis.graph_dp import solve
from research.joint_synthesis.hardware_ir import HardwareEnvelope, GridAxis, NormalizedPrices
from research.joint_synthesis.architecture_synth import synthesize
from research.joint_synthesis.architecture_oracle import enumerate_hardware
from research.joint_synthesis.validate import audit
from research.joint_synthesis.validate_oracle import review_cases


@pytest.mark.parametrize('name,graph,model,seed',list(review_cases()),ids=lambda x:x if isinstance(x,str)else None)
def test_cross_shape_complete_front_and_all_capacity_edges(name,graph,model,seed):
    result=audit(graph,model)
    assert result['exact_demand_frontier_equal']
    assert result['composition_summaries_checked']>0
    assert result['architecture_queries_checked']>0 # Includes every observed P-1/P/P+1.
    assert all(v>0 for v in model.__dict__.values())
    assert model!=CostModel()


@pytest.mark.parametrize('rows,cols',[(1,4),(4,1),(1,1)])
def test_equal_degenerate_packing_does_not_make_declared_conversion_free(rows,cols):
    model=CostModel(2,3,5,7);tensor=Tensor('X',rows,cols)
    values=[[i*cols+j for j in range(cols)]for i in range(rows)]
    for location in ('sram','dram'):
        r=Runtime(model)
        a=r.alloc(rows,cols,location,'row',values)
        b=r.alloc(rows,cols,location,'col',values)
        assert r.copies[a].data==r.copies[b].data
        r.free(b)
        source,target=Property(tensor,'row',location),Property(tensor,'col',location)
        converted=convert(r,a,source,target)
        expected=conversion(source,target,model)
        assert (r.peak,*r.vector[3:])==(expected.peak,expected.energy,expected.cycles,expected.traffic)
        assert r.vector[3]>0 and r.logical(converted)==values


def test_actual_trace_peak_is_feasible_at_exact_capacity_but_not_one_byte_less():
    root,_=solve(TwoMM(),CostModel())
    demand=min(root,key=lambda d:d.peak)
    measured=trace_complete(demand.plan,CostModel()).vector
    envelope=HardwareEnvelope(GridAxis(demand.pe_x,demand.pe_x),GridAxis(demand.pe_y,demand.pe_y),
        GridAxis(measured[2]-1,measured[2]),GridAxis(1,1))
    actual,_=synthesize([demand],envelope,NormalizedPrices(),1000)
    observed,_=enumerate_hardware({measured:demand.plan},envelope,NormalizedPrices(),1000)
    assert actual.designs and observed
    assert {d.hardware.sram_bytes for d in actual.designs}=={measured[2]}
    assert {d.hardware.sram_bytes for d in observed}=={measured[2]}


def test_real_plan_edp_winner_changes_with_bandwidth_at_fixed_pe_and_sram():
    root,_=solve(TwoMM(),CostModel())
    feasible=[d for d in root if d.pe_x<=1 and d.pe_y<=2 and d.peak<=12]
    slow=min(feasible,key=lambda d:d.energy*d.latency(1))
    fast=min(feasible,key=lambda d:d.energy*d.latency(1024))
    assert slow.vector!=fast.vector
    assert slow.energy*slow.latency(1)<fast.energy*fast.latency(1)
    assert fast.energy*fast.latency(1024)<slow.energy*slow.latency(1024)
    assert slow.traffic<fast.traffic and slow.cycles>fast.cycles
    for plan in (slow,fast):assert trace_complete(plan.plan,CostModel()).vector==plan.vector
