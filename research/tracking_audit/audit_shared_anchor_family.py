"""Post-hoc finite-family FFM cost certificates from one shared Join.

The full shared Join is intentionally executed before membership is verified;
no groups are pruned and no end-to-end speedup is claimed. This is not a
continuous-family proof or an independent per-target FFM optimality proof.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import time

from research.tracking_audit import common
from research.tracking_audit.audit_anchor_family import fraction_cost, search_target, serialize
from research.tracking_audit.shape_capacity_audit import build, validate_pick


def run(output):
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    case=common.Case('matmuls','nvdla',(2,4,8)); shape=(4,8)
    capacities=list(range(68,129)); caps_mib=[c/2**20 for c in capacities]
    anchor,_,anchor_time=search_target(case,shape,68)
    row=common.best_row(anchor.data)
    if row is None: raise ValueError('anchor has no mapping')
    start=time.perf_counter();validation=validate_pick(case,shape,68,row); validation_s=time.perf_counter()-start
    if not validation['ok']: raise ValueError('anchor did not validate')
    identity=common.mapping_identity(row['Total<SEP>mapping']())
    summaries=[]
    spec=build(case,shape,128,common.RU)
    env=common.capacity_fractions_env(caps_mib)
    env.update({'AF_TARGET_ENUMERATION':'events','AF_CAPACITY_MEMBERSHIP':'bitset',
                'AF_GENERATION_VARIABLE_RESOURCES':'GlobalBuffer'})
    try:
        common.clear_switches(); os.environ.update(env)
        start=time.perf_counter()
        pm=common.make_pmappings(spec,print_number_of_pmappings=False)
        generated=time.perf_counter()
        common.clear_switches();os.environ.update({'AF_VARIABLE_RESOURCES':'GlobalBuffer',
                                                    'AF_CAPACITY_MEMBERSHIP':'bitset'})
        joined=common.join_pmappings(pm,_terminal_branch_observer=summaries.append)
        finished=time.perf_counter()
    finally:
        common.clear_switches()
    candidates=[]
    for cap,mib in zip(capacities,caps_mib):
        target=common.rows_for_capacity(joined.data,mib,caps_mib[-1])
        selected=[target.iloc[i] for i in range(len(target))
                  if common.mapping_identity(target.iloc[i]['Total<SEP>mapping']())==identity]
        best=common.best_row(target)
        anchor_cost=min((fraction_cost(r) for r in selected),default=None)
        candidates.append(dict(capacity_bytes=cap,anchor_present=bool(selected),
             anchor_reported_edp=str(anchor_cost) if anchor_cost is not None else None,
             best_reported_edp=str(fraction_cost(best)) if best is not None else None,
             frontier_rows=len(target)))
    if not all(c['anchor_present'] for c in candidates):
        upper=None
    else:
        # Include the physically re-evaluated anchor, not just the slightly
        # different rounded FFM-reported value. This remains a post-hoc,
        # fixed-cost-family assumption, not an independent 61-target proof.
        reconstructed=(Fraction.from_float(validation['energy'])*
                       Fraction.from_float(validation['latency']))
        upper=max([reconstructed]+[Fraction(c['anchor_reported_edp']) for c in candidates])
    branches=[]
    for summary in summaries:
        b=serialize(summary)
        b['posthoc_target_union_excluded']=(summary.edp_lower > upper
                                            if upper is not None and summary.edp_lower is not None else None)
        b['working_set_extra']='unknown'
        branches.append(b)
    # Independent FFM references were run by audit_anchor_family.py, separately
    # from this shared run. Only their sampled points are compared here.
    reference_path=Path(__file__).parent/'results/anchor_family/audit.json'
    reference=json.loads(reference_path.read_text())
    if not reference['complete'] or reference['anchor']['mapping_id']!=identity:
        raise ValueError('reference anchor differs or audit is incomplete')
    for name,digest in reference['source_sha256'].items():
        if hashlib.sha256((common.ROOT/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('reference source changed: '+name)
    sampled=[]
    for item in reference['targets']:
        current=candidates[item['capacity_bytes']-68]
        sampled.append(dict(capacity_bytes=item['capacity_bytes'],
            shared_best=current['best_reported_edp'],independent_best=item['reference_best_reported_edp'],
            exactly_equal=current['best_reported_edp']==item['reference_best_reported_edp']))
    paths=[Path(__file__),Path(__file__).with_name('audit_anchor_family.py'),reference_path,
           common.ROOT/'accelforge/mapper/FFM/_join_pmappings/branch_summary.py',
           common.ROOT/'accelforge/mapper/FFM/_join_pmappings/join_pmappings.py',
           common.ROOT/'accelforge/mapper/FFM/main.py']
    report=dict(scope='post-hoc finite target union, incumbent checked after full shared Join; no work skipped',
        anchor_bytes=68,anchor_mapping_id=identity,anchor_search=anchor_time,anchor_validation_s=validation_s,
        shared_search_s=finished-start,shared_make_s=generated-start,shared_join_s=finished-generated,
        shared_frontier_rows=len(joined.data),target_count=len(capacities),targets=candidates,
        upper_if_all_target_membership_witnessed=str(upper) if upper is not None else None,
        branch_summaries=branches,posthoc_excluded_groups=sum(b['posthoc_target_union_excluded'] is True for b in branches),
        actual_pruned_groups=0,working_set_certificate='unknown',sampled_independent_comparisons=sampled,
        source_sha256={str(p.relative_to(common.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(targets=len(candidates),anchor_present=sum(c['anchor_present'] for c in candidates),
        groups=len(branches),posthoc_excluded_groups=report['posthoc_excluded_groups'],
        sampled_all_equal=all(x['exactly_equal'] for x in sampled))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output)
