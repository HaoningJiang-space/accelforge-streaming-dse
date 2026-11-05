"""Validate the definition gate; not an FFM/DSE performance benchmark."""
import argparse
from dataclasses import asdict
from fractions import Fraction
import hashlib
from itertools import product
import json
from pathlib import Path
import time

from .graph_ir import TwoMM, CostModel
from .physical_plan import restore_plan
from .graph_dp import solve
from .schedule_rules import generate
from .resource_demand import summarize
from .composition import compose
from .exhaustive_oracle import enumerate_plans, trace_local, trace_complete, exhaustive


def independent_frontier(vectors):
    # Deliberately do not call the production incremental frontier routine.
    return {v for v in vectors if not any(u!=v and all(a<=b for a,b in zip(u,v)) for u in vectors)}


def et_frontier(vectors,px,py,capacity,bandwidth):
    feasible={(v[3],Fraction(v[4])+Fraction(v[5],bandwidth))
              for v in vectors if v[0]<=px and v[1]<=py and v[2]<=capacity}
    return {v for v in feasible if not any(u!=v and u[0]<=v[0] and u[1]<=v[1] for u in feasible)}


def audit(graph,model=CostModel()):
    started=time.perf_counter()
    root,stats=solve(graph,model)  # no Oracle response/hardware points exist yet
    dp_s=time.perf_counter()-started
    production=generate(graph);oracle=enumerate_plans(graph)
    if any(set(p)!=set(o) for p,o in zip(production,oracle)):
        raise AssertionError('independent enumerators disagree about the declared grammar')
    local={}
    for plan in (*production[0],*production[1]):
        summary=summarize(plan,model);measured=trace_local(plan,model)
        vector=list(measured.vector);vector[2]-=plan.required.live_bytes
        if tuple(vector)!=summary.vector:
            raise AssertionError(f'local analytical/trace mismatch: {plan}: {summary.vector} != {vector}')
        if (measured.macs,measured.sram_bytes,measured.bursts)!=(summary.macs,summary.sram_bytes,summary.dram_bursts):
            raise AssertionError('local action counts disagree')
        local[plan]=summary
    start=time.perf_counter()
    def check_composition(plan,measured):
        expected=compose(local[plan.producer],local[plan.consumer],model).vector
        if expected!=measured:
            raise AssertionError(f'composition law/trace mismatch: {expected} != {measured}: {plan}')
    observations,oracle_stats=exhaustive(graph,model,inspect=check_composition)
    if {x.vector for x in root}!=independent_frontier(observations):
        raise AssertionError('root demand frontier differs from exhaustive execution')
    for state in root:
        restored=restore_plan(json.loads(json.dumps(asdict(state.plan))))
        if restored!=state.plan:raise AssertionError('execution witness failed JSON round-trip')
        for seed in (1,2,5):
            if trace_complete(restored,model,seed).vector!=state.vector:
                raise AssertionError('resource summary unexpectedly depends on numeric input')
    oracle_validation_s=time.perf_counter()-start
    # Capacity boundaries and new hardware points are generated AFTER solve().
    capacities=sorted({c for v in observations for c in (v[2]-1,v[2],v[2]+1) if c>0})
    queries=0;feasible=0
    for px,py,c,b in product(range(1,max(v[0]for v in observations)+1),
            range(1,max(v[1]for v in observations)+1),capacities,(1,2,3,5,8)):
        a=et_frontier([s.vector for s in root],px,py,c,b)
        expected=et_frontier(observations,px,py,c,b)
        if a!=expected:raise AssertionError('conditional hardware query lost a Pareto vector')
        queries+=1;feasible+=bool(a)
    return dict(status='complete',graph=asdict(graph),model=asdict(model),dp=stats,
        local_summaries_checked=len(local),composition_summaries_checked=oracle_stats['complete_plans_traced'],
        exhaustive=oracle_stats,exact_demand_frontier_equal=True,
        architecture_queries_checked=queries,queries_with_feasible_plans=feasible,
        query_axes='Px/Py integers; every observed C-1/C/C+1; B=1,2,3,5,8. Created after DP.',
        root_frontier=[dict(vector=s.vector,plan=asdict(s.plan))for s in root],
        source_roundtrip_witnesses_checked=len(root),
        oracle_demand_vectors=sorted(independent_frontier(observations)),
        dp_diagnostic_s=dp_s,oracle_validation_s=oracle_validation_s,
        speedup_claim=False,ffm_grammar_equivalence=False,streaming_fusion_supported=False,
        new_physical_interface_theorem_for_ffm=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    report=dict(status='in_progress',cases=[])
    for graph in (TwoMM(),TwoMM(2,2,4,2)):
        try:result=audit(graph)
        except Exception as exc:
            report.update(status='failed',error=str(exc))
            args.output.write_text(json.dumps(report,indent=2)+'\n')
            raise
        report['cases'].append(result)
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:result[k]for k in ('graph','dp','local_summaries_checked','composition_summaries_checked','architecture_queries_checked')}),flush=True)
    report['source_sha256']={str(f):hashlib.sha256(f.read_bytes()).hexdigest()for f in Path(__file__).parent.glob('*.py')}
    report['status']='complete'
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
