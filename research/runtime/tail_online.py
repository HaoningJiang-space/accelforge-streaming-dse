"""Run the physical tail proposal order without reading a precomputed tail score."""

import argparse
import hashlib
from itertools import combinations
import json
from math import isclose, prod
from pathlib import Path
import sys
import time

from research.joint_physical import replay as codec
from research.runtime.audit_tail_ports import price
from research.runtime.summarize_joint_trials import checkout_hashes
from research.runtime.tail_query_benchmark import Design, run as query_run
from research.runtime.tail_tiles import branches, exact_tail_evaluation, numeric, proposals, rank_trace
from research.tracking_audit import common, shape_capacity_audit as physical


def register(case, points):
    designs, edits = [], {}
    for i,seed in enumerate(points):
        h = seed["architecture"]
        shape = (h["px"],h["py"])
        capacity = h["capacity_bytes"]
        spec = physical.build(case,shape,capacity,common.RU)
        evaluated = {}
        def component(name,key):
            if name not in evaluated:
                evaluated[name] = spec.calculate_component_area_energy_latency_leak(einsum_name=name,area=False)
            return evaluated[name].arch.find(key)
        original = codec.decode(seed["witness"]["mapping"],component)
        paths = dict(branches(original.nodes))
        full = common.get_rank_variable_bounds_for_all_einsums(spec)
        possible = list(proposals(paths,full,h))
        if not possible:
            continue
        if len(possible)>8:
            raise ValueError("outside the bounded neighborhood")
        dims = {}
        for name in paths:
            component(name,"MAC")
            dims[name] = evaluated[name].workload.einsums[name].rank_variables
        def trace(changes):
            changed = {(op,ordinal):tile for op,ordinal,tile in changes}
            output = {}
            for name,path in paths.items():
                loops = []
                for j,n in enumerate(path):
                    if (name,j) in changed:
                        n = n.model_copy(deep=True)
                        n.tile_shape = changed[name,j]
                    loops.append(n)
                cycles = prod(rank_trace(int(full[r]),[n for n in loops if n.rank_variable==r])[1] for r in dims[name])
                output[name] = dict(compute_cycles=int(cycles),actions=int(prod(full[r] for r in dims[name])))
            return output
        old = price(seed["witness"],trace(()))
        if not isclose(old["edp"],seed["witness"]["edp"],rel_tol=1e-12,abs_tol=0):
            raise ValueError("perfect seed disagrees with the port ledger")
        for width in range(1,len(possible)+1):
            for moves in combinations(possible,width):
                latency = sum(max(t["compute_cycles"]*1e-9,old["ledger"][name]["memory_latency_s"])
                              for name,t in trace(moves).items())
                choice = Design(i,len(designs),shape,capacity,latency*old["energy"])
                designs.append(choice)
                edits[choice.point,choice.mask] = moves
    return designs,edits


def run(seed_report, queries, target_report, output, method="physical", seed=0, optuna_path=None):
    start = time.perf_counter()
    optuna = None
    if method.startswith("tpe"):
        sys.path.append(str(optuna_path.resolve()))
        import optuna
        optuna.logging.set_verbosity(optuna.logging.ERROR)
    raw = seed_report.read_bytes()
    seeds = json.loads(raw)
    case = common.Case(seeds["case"]["workload"],seeds["case"]["arch"],tuple(seeds["case"]["params"]))
    if case.workload!="matmuls" or case.params[0]!=3:
        raise ValueError("native 3mm required")
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    designs,edits = register(case,seeds["points"])
    setup_s = time.perf_counter()-start
    budgets = [b["budget"]["max_sram_bytes"] for b in seeds["budget_selections"]]
    initial = [b["witness"]["edp"] for b in seeds["budget_selections"]]
    events = []
    def query(key):
        i,_ = key
        seed = seeds["points"][i]
        point = seed["architecture"]
        record = dict(architecture=point,changes=edits[key])
        try:
            witness,trace,_,_ = numeric(case,point,seed["witness"]["mapping"],edits[key])
            corrected = price(witness,trace)
            record.update(status="verified",witness=witness,independent_trace=trace,corrected=corrected)
        except ValueError as error:
            record.update(status="rejected",reason=str(error))
        record["elapsed_s"] = time.perf_counter()-start
        events.append(record)
        return record["corrected"]["edp"] if record["status"]=="verified" else None
    with exact_tail_evaluation():
        selection = query_run(designs,query,initial,budgets,queries,method,seed,optuna)
    total = time.perf_counter()-start
    result = dict(status="complete",candidate_count=len(designs),online_queries=events,seed_validation_excluded=True,
                  setup_s=setup_s,tail_stage_s=total,history=selection["history"],
                  method=method,seed=seed,seed_sha256=hashlib.sha256(raw).hexdigest(),
                  repeat_draws=selection["repeat_draws"],random_fallbacks=selection["random_fallbacks"],
                  target_read_before_search=False,external_sota_acceptance=False)
    if target_report is not None:
        reference = json.loads(target_report.read_bytes())
        target = [x["winner"]["edp"] for x in reference["budget_selections"]]
        qualifying = [i for i,x in enumerate(selection["history"]) if x["best_by_budget"]==target]
        result.update(target_edp=target,first_all_targets_query=qualifying[0]+1 if qualifying else None,
                      first_all_targets_s=events[qualifying[0]]["elapsed_s"] if qualifying else None)
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("online_queries","history")}),flush=True)


def verify(seed_report, result_path, output):
    raw = seed_report.read_bytes()
    seeds = json.loads(raw)
    report_bytes = result_path.read_bytes()
    report = json.loads(report_bytes)
    if report.get("seed_sha256",hashlib.sha256(raw).hexdigest()) not in checkout_hashes(raw):
        raise ValueError("seed report differs")
    case = common.Case(seeds["case"]["workload"],seeds["case"]["arch"],tuple(seeds["case"]["params"]))
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    budgets = [b["budget"] for b in seeds["budget_selections"]]
    best = [b["witness"]["edp"] for b in seeds["budget_selections"]]
    verified = 0
    with exact_tail_evaluation():
        for event,step in zip(report["online_queries"],report["history"],strict=True):
            point = event["architecture"]
            if point!=seeds["points"][step["point"]]["architecture"]:
                raise ValueError("online query refers to a different physical point")
            if event["status"]=="verified":
                witness,trace,_,_ = numeric(case,point,event["witness"]["mapping"])
                if trace!=event["independent_trace"] or price(witness,trace)!=event["corrected"]:
                    raise ValueError("reconstructed tail result differs")
                for field in ("actions","reservation_bits","mapping"):
                    if witness[field]!=event["witness"][field]:
                        raise ValueError(f"reconstructed {field} differs")
                value = event["corrected"]["edp"]
                if step["edp"]!=value:
                    raise ValueError("online score differs from independent repricing")
                best = [min(old,value) if point["capacity_bytes"]<=budget["max_sram_bytes"]
                       and point["px"]*point["py"]<=budget["max_pes"] else old
                       for old,budget in zip(best,budgets)]
                verified += 1
            elif event["status"]!="rejected" or step["edp"] is not None:
                raise ValueError("invalid rejected query record")
            if step["best_by_budget"]!=best:
                raise ValueError("online budget incumbent history differs")
    result = dict(status="verified",replayed_mappings=verified,total_queries=len(report["history"]),
                  report_sha256=hashlib.sha256(report_bytes).hexdigest(),canonical_edp=best,
                  external_sota_acceptance=False)
    output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(result),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds",type=Path,required=True)
    parser.add_argument("--queries",type=int,default=16)
    parser.add_argument("--method",choices=("physical","tpe","tpe-warm"),default="physical")
    parser.add_argument("--seed",type=int,default=0)
    parser.add_argument("--optuna-path",type=Path,default=Path("libraries/tail_optuna"))
    parser.add_argument("--target",type=Path)
    parser.add_argument("--replay",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.replay:
        verify(args.seeds,args.replay,args.output)
    else:
        run(args.seeds,args.queries,args.target,args.output,args.method,args.seed,args.optuna_path)


if __name__=="__main__":
    main()
