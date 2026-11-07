"""Counterexample search against native spatial minimum-usage preferences.

Only a mapper preference changes; physical fanouts, memories and action costs are
identical. Reevaluate selected witnesses on the original physical specification.
This searches a broader policy and must not claim original-policy equivalence.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
from unittest.mock import patch

from research.joint_search import validation
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import validate_pick
from .search import problem


def run(workload,output,reference_path):
    case,domain,budgets = problem(workload,'original12')
    original_build = validation.build
    def relaxed_build(*args,**kwargs):
        spec = original_build(*args,**kwargs)
        for dim in spec.arch.find('ArrayFanout').spatial:
            dim.min_usage = 0
        return spec
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    started = time.perf_counter()
    with patch.object(validation,'build',relaxed_build):
        outputs,details,cache = validation.capacity_events(case,domain)
    elapsed = time.perf_counter()-started
    reference = json.loads(reference_path.read_text(encoding='utf-8'))
    if reference['domain'] != [asdict(p) for p in domain.points]:
        raise ValueError('same physical hardware domain required')
    records = []
    for point,ref in zip(domain.points,reference['points']):
        row = common.best_row(outputs[point])
        witness = validate_pick(case,(point.px,point.py),point.capacity_bytes,row)
        ref_edp = min(v['Total<SEP>energy']*v[common.LATENCY] for v in ref['vectors'])
        records.append(dict(architecture=asdict(point),witness=witness,
            reported_edp=float(row['Total<SEP>energy'])*float(row[common.LATENCY]),
            original_policy_edp=ref_edp,original_physical_spec_reconstruction=True,
            vectors=validation.frontier(outputs[point]).to_dict('records')))
    report = dict(status='complete',case=asdict(case),policy='minimum spatial usage zero',
        policy_space='broader than original native ordered fallback policy',physical_costs_unchanged=True,
        search_s=elapsed,domain=[asdict(p) for p in domain.points],points=records,details=details,cache=cache,
        global_selections=[dict(budget=asdict(b),winner=min(
            (r for p,r in zip(domain.points,records) if b.admits(p)),key=lambda r:r['reported_edp'])) for b in budgets],
        external_sota_acceptance=False)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(search_s=elapsed,gains=[r['original_policy_edp']/r['reported_edp'] for r in records])),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workload',choices=('3mm','attention','attention256','attention512'),default='attention')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True)
    args = parser.parse_args()
    run(args.workload,args.output,args.reference)


if __name__=='__main__':
    main()
