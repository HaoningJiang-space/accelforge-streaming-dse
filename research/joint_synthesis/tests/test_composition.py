import ast
from dataclasses import replace, asdict
from pathlib import Path
from itertools import product
import subprocess
import sys

import pytest

from research.joint_synthesis.graph_ir import TwoMM, CostModel, Tensor
from research.joint_synthesis.physical_plan import Property, KernelPlan, Schedule, CompletePlan, restore_plan
from research.joint_synthesis.schedule_rules import generate
from research.joint_synthesis.resource_demand import summarize
from research.joint_synthesis.composition import conversion, compose
from research.joint_synthesis.exhaustive_oracle import Runtime, convert, matrix, trace_complete
from research.joint_synthesis.conditional_frontier import frontier
from research.joint_synthesis.validate import audit


def test_production_and_oracle_do_not_import_ffm_or_each_others_cost_rules():
    root=Path(__file__).parents[1]
    forbidden=('accelforge','research.graph_coopt','research.joint_search')
    for path in root.glob('*.py'):
        tree=ast.parse(path.read_text())
        imports=[n.module for n in ast.walk(tree)if isinstance(n,ast.ImportFrom)]
        imports.extend(a.name for n in ast.walk(tree)if isinstance(n,ast.Import)for a in n.names)
        assert not any(name and name.startswith(forbidden)for name in imports),path
        if path.name in ('exhaustive_oracle.py','architecture_oracle.py'):
            assert not any(name in ('resource_demand','graph_dp','conditional_frontier','schedule_rules','composition','architecture_synth')for name in imports)


def test_oracle_executes_without_site_packages_or_production_cost_modules():
    script='''
import sys
class Block:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('accelforge') or fullname in (
            'research.joint_synthesis.resource_demand',
            'research.joint_synthesis.composition',
            'research.joint_synthesis.graph_dp',
            'research.joint_synthesis.conditional_frontier',
            'research.joint_synthesis.architecture_synth',
            'research.joint_synthesis.schedule_rules'):
            raise AssertionError('Oracle imported a blocked search/cost dependency: '+fullname)
sys.meta_path.insert(0,Block())
from research.joint_synthesis.graph_ir import TwoMM, CostModel
from research.joint_synthesis.exhaustive_oracle import exhaustive
observations, stats = exhaustive(TwoMM(1,1,1,1),CostModel())
assert observations and stats['complete_plans_traced']==144
from research.joint_synthesis.hardware_ir import GridAxis, HardwareEnvelope, NormalizedPrices
from research.joint_synthesis.architecture_oracle import enumerate_hardware
envelope=HardwareEnvelope(GridAxis(1,1),GridAxis(1,1),GridAxis(8,16,8),GridAxis(1,2))
designs,hardware_stats=enumerate_hardware(observations,envelope,NormalizedPrices(),100)
assert designs and hardware_stats['hardware_grid_points']==4
'''
    subprocess.run([sys.executable,'-S','-c',script],cwd=Path(__file__).parents[3],
                   capture_output=True,text=True,check=True)


def test_every_explicit_converter_accounts_for_copies_actions_and_values():
    tensor=Tensor('X',2,3)
    properties=[Property(tensor,l,s)for l,s in product(('row','col'),('sram','dram'))]
    model=CostModel(mac_energy=2,sram_byte_energy=3,dram_byte_energy=7,burst_setup_cycles=4)
    for source,target in product(properties,repeat=2):
        runtime=Runtime(model)
        original=matrix(2,3,0)
        x=runtime.alloc(2,3,source.location,source.layout,original)
        y=convert(runtime,x,source,target)
        expected=conversion(source,target,model)
        observed=runtime.vector
        assert (observed[2],*observed[3:])==(expected.peak,expected.energy,expected.cycles,expected.traffic)
        assert runtime.current==target.live_bytes
        assert runtime.logical(y)==original
        assert runtime.copies[y].layout==target.layout


def test_oracle_uses_physically_distinct_packing_not_only_layout_tags():
    runtime=Runtime(CostModel())
    values=[[1,2,3],[4,5,6]]
    row=runtime.alloc(2,3,'dram','row',values)
    col=runtime.alloc(2,3,'dram','col',values)
    assert runtime.copies[row].data==[1,2,3,4,5,6]
    assert runtime.copies[col].data==[1,4,2,5,3,6]
    assert runtime.logical(row)==runtime.logical(col)==values


def test_converter_double_residency_exceeds_both_endpoint_peaks():
    first,second=generate(TwoMM())
    producer=next(p for p in first if p.schedule==Schedule(1,1,1,'ijk') and
                  (p.delivered.layout,p.delivered.location)==('row','sram'))
    consumer=next(p for p in second if p.schedule==Schedule(1,1,1,'ijk') and
                  (p.required.layout,p.required.location)==('col','sram'))
    a,b=summarize(producer,CostModel()),summarize(consumer,CostModel())
    assert max(a.workspace,consumer.required.live_bytes+b.workspace)==12
    combined=compose(a,b,CostModel())
    assert combined.peak==16
    assert trace_complete(combined.plan,CostModel()).vector==combined.vector


def test_scalar_local_edp_winner_is_not_a_safe_summary():
    assert 1*10<4*3
    assert (1+100)*(10+0)>(4+100)*(3+0)


def test_latency_coefficients_must_retain_bandwidth_tradeoffs():
    a,b=generate(TwoMM())
    base=compose(summarize(a[0],CostModel()),summarize(b[0],CostModel()),CostModel())
    low_intercept=replace(base,energy=1,cycles=2,traffic=32)
    low_traffic=replace(base,energy=1,cycles=8,traffic=8)
    assert len(frontier([low_intercept,low_traffic]))==2
    assert low_traffic.latency(1)<low_intercept.latency(1)
    assert low_intercept.latency(64)<low_traffic.latency(64)


def test_unsupported_alias_precision_or_tile_contract_is_rejected():
    a,b=TwoMM().operators
    with pytest.raises(ValueError):
        replace(a,output=a.left)
    with pytest.raises(ValueError):
        replace(a.output,version=1)
    with pytest.raises(ValueError):
        KernelPlan(a,Schedule(3,1,1,'ijk'),Property(a.left,'row','dram'),Property(a.output,'row','dram'))
    first,second=generate(TwoMM())
    with pytest.raises(ValueError):
        CompletePlan(first[0],replace(second[0],op=replace(b,left=Tensor('Other',2,2)),required=Property(Tensor('Other',2,2),'row','dram')))


def test_witness_reconstruction_does_not_ignore_unknown_interface_properties():
    a,b=generate(TwoMM())
    payload=asdict(CompletePlan(a[0],b[0]))
    assert restore_plan(payload)==CompletePlan(a[0],b[0])
    payload['consumer']['required']['unknown_alias']=True
    with pytest.raises(TypeError):restore_plan(payload)


@pytest.mark.parametrize('graph',[TwoMM(),TwoMM(2,2,4,2)])
def test_complete_demand_frontier_matches_independent_execution(graph):
    result=audit(graph)
    assert result['exact_demand_frontier_equal']
    assert result['architecture_queries_checked']>0
    assert result['dp']['architecture_points_supplied']==0
    assert result['dp']['materialized_complete_pairs']<result['dp']['raw_complete_pairs']
    assert not result['streaming_fusion_supported']
