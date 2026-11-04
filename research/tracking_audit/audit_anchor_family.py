"""One real anchor, capacity-specific physical re-evaluation and FFM audit.

Terminal summaries are collected through FFM's opt-in read-only observer. This
is not yet a family pruning engine: target reference searches are explicitly
separate, membership outside sampled points is unknown, and no rows are skipped.
"""
import argparse
import copy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import time

from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, validate_pick


def fraction_cost(row):
    return Fraction.from_float(float(row['Total<SEP>energy'])) * Fraction.from_float(float(row[common.LATENCY]))


def serialize(summary):
    return dict(left_rows=summary.left_rows,right_rows=summary.right_rows,
                shared_tensors=summary.shared_tensors,matched_pairs=summary.matched_pairs,
                energy_lower=str(summary.energy_lower) if summary.energy_lower is not None else None,
                latency_lower=str(summary.latency_lower) if summary.latency_lower is not None else None,
                edp_lower=str(summary.edp_lower) if summary.edp_lower is not None else None,
                working_set_lower_bits=summary.working_set_lower_bits,
                unsupported_reason=summary.unsupported_reason)


def search_target(case,shape,capacity):
    spec = build(case,shape,capacity,common.RU)
    summaries = []
    common.clear_switches()
    start=time.perf_counter()
    pmappings=common.make_pmappings(spec,print_number_of_pmappings=False)
    generated=time.perf_counter()
    result=common.join_pmappings(pmappings,_terminal_branch_observer=summaries.append)
    finished=time.perf_counter()
    return result,summaries,dict(total_s=finished-start,make_s=generated-start,join_s=finished-generated)


def physical_check(case,shape,capacity,mapping,anchor_energy,anchor_latency):
    spec = build(case,shape,capacity,common.RU)
    spec.model.metrics=common.RU
    spec.mapping=copy.deepcopy(mapping)
    data = common.evaluate_mapping(spec).data
    if len(data)!=1:
        raise ValueError('expected one re-evaluated mapping')
    row=data.iloc[0]
    resources={}
    for col in data.columns:
        if col.startswith('reservation_bits<SEP>'):
            ref='capacity_reference_bits<SEP>'+col.split('<SEP>')[1]
            bits=int(row[col]); capacity_bits=int(row[ref])
            if bits != row[col] or bits<0 or capacity_bits<0:
                raise ValueError('invalid exact reservation')
            resources[col]={'bits':bits,'capacity_bits':capacity_bits,'fits':bits<=capacity_bits}
    if 'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right' not in resources:
        raise ValueError('missing exact GlobalBuffer peak')
    energy,latency=float(row['Total<SEP>energy']),float(row[common.LATENCY])
    if not all(math.isfinite(x) and x>=0 for x in (energy,latency)):
        raise ValueError('invalid re-evaluated objective')
    return dict(resources=resources,resource_fits=all(x['fits'] for x in resources.values()),
                energy=energy,latency=latency,
                costs_exactly_equal_to_anchor=(energy==anchor_energy and latency==anchor_latency))


def run(output,anchor,capacities):
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    case=common.Case('matmuls','nvdla',(2,4,8));shape=(4,8)
    report=dict(scope='anchor diagnostics and sampled FFM references; no family certificate or pruning',
                case=str(case),shape=shape,anchor_bytes=anchor,capacities_bytes=capacities,
                anchor=None,targets=[],complete=False)
    paths=[Path(__file__),common.ROOT/'accelforge/mapper/FFM/_join_pmappings/branch_summary.py',
           common.ROOT/'accelforge/mapper/FFM/_join_pmappings/join_pmappings.py',
           common.ROOT/'accelforge/mapper/FFM/main.py',
           common.ROOT/'examples/workloads/matmuls.yaml',common.ROOT/'examples/arches/nvdla.yaml']
    report['source_sha256']={str(p.relative_to(common.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    output.parent.mkdir(parents=True,exist_ok=True)
    def save(): output.write_text(json.dumps(report,indent=2)+'\n')
    result,summaries,search_time=search_target(case,shape,anchor)
    row=common.best_row(result.data)
    if row is None: raise ValueError('anchor produced no mapping')
    start=time.perf_counter(); validation=validate_pick(case,shape,anchor,row); validation_s=time.perf_counter()-start
    if not validation['ok']: raise ValueError('anchor mapping failed validation')
    mapping=row['Total<SEP>mapping'](); identity=common.mapping_identity(mapping)
    report['anchor']=dict(search_time=search_time,validation_s=validation_s,validation=validation,
                          mapping_id=identity,summaries=[serialize(x) for x in summaries])
    save()
    anchor_energy,anchor_latency=validation['energy'],validation['latency']
    for cap in capacities:
        start=time.perf_counter()
        try:
            physical=physical_check(case,shape,cap,mapping,anchor_energy,anchor_latency)
        except Exception as error:
            # Re-evaluation errors are unknown, not evidence of infeasibility.
            physical=dict(resource_fits=None,error=f'{type(error).__name__}: {error}')
        physical_s=time.perf_counter()-start
        # The following complete target search is an oracle for this audit only;
        # it is not included in a claim of architecture-family reuse.
        target,branches,reference_time=search_target(case,shape,cap)
        matches=[target.data.iloc[i] for i in range(len(target.data))
                 if common.mapping_identity(target.data.iloc[i]['Total<SEP>mapping']())==identity]
        target_witness = validate_pick(case,shape,cap,matches[0]) if matches else None
        if matches and (not target_witness['ok'] or physical['resource_fits'] is False):
            raise ValueError('frontier witness failed physical validation')
        incumbent = min((fraction_cost(r) for r in matches),default=None) if physical['resource_fits'] is True else None
        best=common.best_row(target.data)
        if best is None: raise ValueError('no target frontier')
        best_validation=validate_pick(case,shape,cap,best)
        if not best_validation['ok']: raise ValueError('target best mapping failed validation')
        bound_records=[serialize(s) for s in branches]
        for b in bound_records:
            b['posthoc_cost_bound_excludes_group']=(Fraction(b['edp_lower'])>incumbent
                if incumbent is not None and b['edp_lower'] is not None else None)
        report['targets'].append(dict(capacity_bytes=cap,physical=physical,physical_check_s=physical_s,
            reference_search=reference_time,reference_frontier_rows=len(target.data),
            # Absence from the final frontier does not prove absence before Pareto.
            anchor_in_final_frontier=bool(matches),policy_membership=('witnessed_in_frontier' if matches else 'unknown'),
            target_witness_validation=target_witness,
            posthoc_incumbent_reported_edp=str(incumbent) if incumbent is not None else None,
            reference_best_reported_edp=str(fraction_cost(best)),reference_best_validation=best_validation,
            branches=bound_records,working_set_certificate='unknown',
            claimed_family_certificate=False,actual_pruned_groups=0))
        save()
        print(json.dumps(dict(capacity_bytes=cap,physical=physical['resource_fits'],
                              anchor_on_frontier=bool(matches),groups=len(branches))),flush=True)
    report['complete']=True
    save()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--anchor',type=int,default=68)
    p.add_argument('--capacities',nargs='+',type=int,default=[68,72,80,96,128])
    a=p.parse_args()
    if a.anchor<=0 or not a.capacities or any(x<=0 for x in a.capacities):
        p.error('anchor and capacities must be positive integer bytes')
    run(a.output,a.anchor,a.capacities)
