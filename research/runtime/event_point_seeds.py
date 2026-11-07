"""Export one native Event winner per physical point for matched tail refinement."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse
from research.fusion_envelope.search import PolicyOracle, digest, problem
from research.joint_budget.analytic_bounds import lower_bound
from research.joint_budget.protocol import Hardware
from research.joint_physical.replay import encode
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import validate_pick


def run(workload, output):
    case, domain, budgets = problem(workload,"factors96")
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    source = digest()
    started = time.perf_counter()
    oracle = PolicyOracle(case,"relaxed")
    shapes = sorted({(p.px,p.py) for p in domain.points},key=lambda s:(
        lower_bound(case,Hardware(*s,1)).latency,max(s)/min(s),s))
    points = {}
    with EnumerationReuse() as cache:
        for shape in shapes:
            targets = [p for p in domain.points if (p.px,p.py)==shape]
            oracle.solve(shape,targets,cache)
            for p in targets:
                row = common.best_row(oracle.outputs.pop(p))
                witness = validate_pick(case,shape,p.capacity_bytes,row)
                if not witness["feasible"] or not witness["ok"]:
                    raise ValueError(f"point {p} has no validated mapping")
                witness["mapping"] = encode(row["Total<SEP>mapping"]())
                points[p] = dict(architecture=asdict(p),witness=witness)
            print(json.dumps(dict(shape=shape,points=len(points),elapsed_s=time.perf_counter()-started)),flush=True)
    selected = [dict(budget=asdict(b),**min((x for p,x in points.items() if b.admits(p)),
                                          key=lambda x:x["witness"]["edp"])) for b in budgets]
    after = digest()
    if after!=source:
        raise ValueError("search source changed during the experiment")
    result = dict(status="complete",method="complete native Event per point",
                  case=dict(workload=case.workload,arch=case.arch,params=list(case.params)),
                  domain=[asdict(p) for p in domain.points],points=[points[p] for p in domain.points],
                  budget_selections=selected,policy="relaxed",workers=1,
                  reference_read_before_search=False,source_before=source,source_after=after,
                  oracle_details=oracle.details,search_s=time.perf_counter()-started,
                  external_sota_acceptance=False)
    output.write_text(json.dumps(result,separators=(",",":"),allow_nan=False)+"\n",encoding="utf-8",newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload",choices=("3mm",),default="3mm")
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    run(args.workload,args.output)


if __name__=="__main__":
    main()
