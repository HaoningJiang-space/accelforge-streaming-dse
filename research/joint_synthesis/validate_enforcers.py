"""Independent full-grammar and budget checks for physical enforcer alternatives."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .graph_ir import TwoMM, CostModel
from .physical_plan import Property, Schedule, KernelPlan
from .resource_demand import summarize
from .composition import compose
from .exhaustive_oracle import trace_complete
from .hardware_ir import GridAxis, HardwareEnvelope, NormalizedPrices
from .architecture_synth import synthesize
from .validate import audit
from .validate_oracle import review_cases
from .validate_architecture import validate_configuration


def fixed_interface_case():
    """An externally fixed interface/kernel request, not free whole-graph search."""
    graph=TwoMM(2,1,25,1);model=CostModel();a,b=graph.operators
    source,target=Property(a.output,'row','sram'),Property(a.output,'col','sram')
    p=KernelPlan(a,Schedule(1,1,1,'ijk'),Property(a.left,'row','dram'),source)
    q=KernelPlan(b,Schedule(1,1,1,'ijk'),target,Property(b.output,'row','dram'))
    demands=[compose(summarize(p,model),summarize(q,model),model,route)
             for route in ('direct','spill_reload')]
    observations={trace_complete(d.plan,model).vector:d.plan for d in demands}
    if set(observations)!={d.vector for d in demands}:raise AssertionError('fixed plan demands disagree')
    grid=HardwareEnvelope(GridAxis(1,1),GridAxis(1,1),GridAxis(1,220),GridAxis(1,16))
    prices=NormalizedPrices()
    result=validate_configuration(demands,observations,model,grid,prices,400)
    family,_=synthesize(demands,grid,prices,400)
    winners=[]
    for budget,expected in ((150,'spill_reload'),(400,'direct')):
        winner=family.best_edp(budget)
        if winner is None or winner.demand.plan.enforcer!=expected:
            raise AssertionError('fixed-interface budget failed to switch the selected enforcer')
        winners.append(dict(budget=budget,enforcer=winner.demand.plan.enforcer,
            hardware=asdict(winner.hardware),resource_cost=winner.resource_cost,
            energy=winner.energy,latency=str(winner.latency),edp=str(winner.edp)))
    result.update(graph=asdict(graph),model=asdict(model),sources=[dict(source_id=i,
        demand_vector=d.vector,plan=asdict(d.plan))for i,d in enumerate(demands)],budget_witnesses=winners,
        consumer_and_producer_choices_fixed=True,unconstrained_graph_quality_claim=False)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    report=dict(status='in_progress',enforcer_grammar='direct_and_spill_reload',cases=[])
    cases=[('square',TwoMM(),CostModel(),None),('rectangle',TwoMM(2,2,4,2),CostModel(),None),*review_cases()]
    for name,graph,model,seed in cases:
        try:r=audit(graph,model)
        except Exception as exc:
            report.update(status='failed',failure_case=name,error=str(exc))
            args.output.write_text(json.dumps(report,indent=2)+'\n');raise
        r.update(name=name,cost_seed=seed);report['cases'].append(r)
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(dict(name=name,complete_executions=r['exhaustive']['complete_plans_by_enforcer'],
            root_states_by_enforcer=r['dp']['root_states_by_enforcer'],
            queries=r['architecture_queries_checked'],
            changed_et_queries=r['enforcer_expansion']['queries_with_changed_et_frontier'])),flush=True)
    try:report['fixed_interface']=fixed_interface_case()
    except Exception as exc:
        report.update(status='failed',failure_case='fixed_interface',error=str(exc))
        args.output.write_text(json.dumps(report,indent=2)+'\n');raise
    report.update(status='complete',speedup_claim=False,ffm_quality_comparison=False)
    report['source_sha256']={str(f):hashlib.sha256(f.read_bytes()).hexdigest()
        for f in Path(__file__).parent.glob('*.py')}
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
