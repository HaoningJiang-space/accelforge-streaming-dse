"""Independent full-grid checks of normalized global architecture synthesis."""
import argparse
from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time

from .graph_ir import TwoMM, CostModel
from .physical_plan import restore_plan
from .graph_dp import solve
from .exhaustive_oracle import exhaustive, trace_complete
from .hardware_ir import GridAxis, HardwareEnvelope, NormalizedPrices
from .architecture_synth import synthesize
from .architecture_oracle import enumerate_hardware, full_frontier, query_budget


def rational(value):
    return [value.numerator,value.denominator]


def configurations():
    return (
        ('unit_axes',HardwareEnvelope(GridAxis(1,3),GridAxis(1,5),GridAxis(4,48,4),GridAxis(1,9)),NormalizedPrices(),128),
        ('offset_grids',HardwareEnvelope(GridAxis(1,4,2),GridAxis(2,5,2),GridAxis(3,45,3),GridAxis(3,10,2)),NormalizedPrices(2,2,1),96),
    )


def validate_configuration(root,observations,model,envelope,prices,ceiling):
    start=time.perf_counter()
    actual,stats=synthesize(root,envelope,prices,ceiling)
    synthesis_s=time.perf_counter()-start
    start=time.perf_counter()
    unpruned,oracle_stats=enumerate_hardware(observations,envelope,prices,ceiling)
    expected=full_frontier(unpruned)
    expected_vectors={(d.resource_cost,d.energy,d.latency)for d in expected}
    if {d.vector for d in actual.designs}!=expected_vectors:
        raise AssertionError('joint hardware-cost/E/T frontier differs from full-grid Oracle')
    oracle_binding_s=time.perf_counter()-start
    # Controlled baseline: identical complete demands, but enumerate every
    # hardware grid point. This isolates inverse binding from earlier DP pruning.
    controlled_observations={d.vector:observations[d.vector] for d in root}
    controlled,controlled_stats=enumerate_hardware(controlled_observations,envelope,prices,ceiling)
    if {(d.resource_cost,d.energy,d.latency)for d in full_frontier(controlled)}!=expected_vectors:
        raise AssertionError('same-root full-grid baseline differs from complete physical grammar')
    sources={d.plan:i for i,d in enumerate(root)}
    measured={};designs=[]
    for d in actual.designs:
        plan=restore_plan(json.loads(json.dumps(asdict(d.demand.plan))))
        if plan not in measured:measured[plan]=trace_complete(plan,model,seed=7).vector
        v=measured[plan];h=d.hardware
        if v!=d.demand.vector:raise AssertionError('selected plan has different executed resource/cost demand')
        for stage in (plan.producer,plan.consumer):
            if stage.schedule.ti>h.px or stage.schedule.tj>h.py:
                raise AssertionError('local stages require inconsistent global hardware')
        if v[2]>h.sram_bytes:raise AssertionError('physical trace exceeds synthesized SRAM')
        for value,axis in zip((h.px,h.py,h.sram_bytes,h.bandwidth),
                (envelope.px,envelope.py,envelope.sram_bytes,envelope.bandwidth)):
            if not axis.minimum<=value<=axis.maximum or (value-axis.minimum)%axis.step:
                raise AssertionError('hardware is not in its declared grid')
        cost=prices.pe*h.px*h.py+prices.sram_byte*h.sram_bytes+prices.bandwidth*h.bandwidth
        latency=Fraction(v[4]*h.bandwidth+v[5],h.bandwidth)
        if cost!=d.resource_cost or latency!=d.latency or cost>ceiling:
            raise AssertionError('selected hardware price or physical latency disagrees')
        designs.append(dict(hardware=asdict(h),resource_cost=d.resource_cost,energy=d.energy,
            latency=rational(d.latency),edp=rational(d.edp),source_id=sources[d.demand.plan]))
    transitions=[];previous=None;feasible_budgets=0;front_counts=[]
    for budget in range(ceiling+1):
        selected=actual.query_budget(budget)
        a={(d.energy,d.latency)for d in selected};b=query_budget(unpruned,budget)
        if a!=b:raise AssertionError(f'budget {budget} lost an E/T vector')
        best=actual.best_edp(budget)
        expected_edp=min((d.energy*d.latency for d in unpruned if d.resource_cost<=budget),default=None)
        if (None if best is None else best.edp)!=expected_edp:
            raise AssertionError(f'budget {budget} has wrong global minimum EDP')
        feasible_budgets+=bool(best);front_counts.append(len(a))
        if best is not None:
            key=best.hardware,sources[best.demand.plan]
            if key!=previous:
                transitions.append(dict(budget=budget,hardware=asdict(best.hardware),
                    resource_cost=best.resource_cost,source_id=sources[best.demand.plan],
                    energy=best.energy,latency=rational(best.latency),edp=rational(best.edp)))
            previous=key
    return dict(envelope=asdict(envelope),normalized_prices=asdict(prices),budget_ceiling=ceiling,
        exact_full_joint_frontier_equal=True,all_budget_et_frontiers_equal=True,
        all_budget_minimum_edp_equal=True,budget_queries_checked=ceiling+1,
        feasible_budget_queries=feasible_budgets,frontier_size_by_budget=front_counts,
        synthesis=stats,oracle=oracle_stats,design_witnesses_checked=len(designs),
        controlled_same_root_grid=controlled_stats,same_root_grid_frontier_equal=True,
        distinct_selected_source_plans_replayed=len(measured),designs=designs,
        best_design_transitions=transitions,synthesis_diagnostic_s=synthesis_s,
        oracle_binding_diagnostic_s=oracle_binding_s,speedup_claim=False)


def audit(graph,model=CostModel()):
    root,dp_stats=solve(graph,model)
    # Hardware envelopes/queries are not inputs to graph generation or DP.
    observations,trace_stats=exhaustive(graph,model)
    records=[]
    for name,envelope,prices,ceiling in configurations():
        r=validate_configuration(root,observations,model,envelope,prices,ceiling)
        r['name']=name;records.append(r)
    return dict(graph=asdict(graph),model=asdict(model),dp=dp_stats,physical_oracle=trace_stats,
        sources=[dict(source_id=i,demand_vector=d.vector,plan=asdict(d.plan))for i,d in enumerate(root)],
        configurations=records,calibrated_area_model=False,ffm_quality_or_speed_comparison=False,
        streaming_fusion_supported=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    report=dict(status='in_progress',cases=[])
    for graph in (TwoMM(),TwoMM(2,2,4,2)):
        try:r=audit(graph)
        except Exception as e:
            report.update(status='failed',failure=str(e))
            args.output.write_text(json.dumps(report,indent=2)+'\n');raise
        report['cases'].append(r);args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(dict(graph=asdict(graph),configurations=[{
            'name':c['name'],'synthesis':c['synthesis'],'oracle':c['oracle'],
            'budget_queries':c['budget_queries_checked']}for c in r['configurations']])),flush=True)
    report['status']='complete'
    report['source_sha256']={str(f):hashlib.sha256(f.read_bytes()).hexdigest()for f in Path(__file__).parent.glob('*.py')}
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
