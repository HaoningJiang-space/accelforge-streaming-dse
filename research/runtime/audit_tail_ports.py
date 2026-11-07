"""Reprice exact-tail 3mm witnesses with one physical port ledger per memory."""

import argparse
from collections import defaultdict
from fractions import Fraction as F
import hashlib
import json
from math import isclose
from pathlib import Path

from research.joint_budget.analytic_bounds import check_frozen_inputs
from research.runtime.summarize_joint_trials import checkout_hashes
from research.runtime.tail_tiles import exact_tail_evaluation, numeric
from research.tracking_audit import common


def price(witness, trace):
    """Same NVDLA action rates; count every reported action at the shared port.

    The symbolic temporal reducer takes max over per-unit counts for distinct
    full/tail cases, which undercounts time on a single shared memory port.
    Aggregate total bit actions separately before applying each port's rate.
    """
    counts = defaultdict(int)
    for key, value in witness["actions"].items():
        name, kind, component, tensor, action = key.split("<SEP>")
        if kind!="action" or value<0 or int(value)!=value:
            raise ValueError("action counts must be exact nonnegative integers")
        counts[name,component,action] += int(value)
    energy = F()
    latency = F()
    details = {}
    for name, traced in trace.items():
        dr,dw = (counts[name,"MainMemory",op] for op in ("read","write"))
        gr,gw = (counts[name,"GlobalBuffer",op] for op in ("read","write"))
        operations = counts[name,"MAC","compute"]
        if operations!=traced["actions"]:
            raise ValueError("MAC ledger does not match independent iteration count")
        e = (dr+dw)*F("7.03e-12")+gr*F("0.249e-12")+gw*F("0.293e-12")+operations*F("0.084e-12")
        dram = F(dr+dw,307_200_000_000)
        sram = max(F(gr,4_096_000_000_000),F(gw,1_024_000_000_000))
        mac = F(traced["compute_cycles"],1_000_000_000)
        t = max(dram,sram,mac)
        energy += e
        latency += t
        details[name] = dict(dram_bits=[dr,dw],sram_bits=[gr,gw],mac_cycles=traced["compute_cycles"],
                             memory_latency_s=float(max(dram,sram)),latency_s=float(t))
    if not isclose(float(energy),witness["energy"],rel_tol=1e-12,abs_tol=0):
        raise ValueError("independent per-bit energy differs from the native action price")
    return dict(energy=float(energy),latency=float(latency),edp=float(energy*latency),
                native_symbolic_latency=witness["latency"],ledger=details)


def run(candidates, seeds, output):
    raw = candidates.read_bytes()
    report = json.loads(raw)
    source_bytes = seeds.read_bytes()
    source = json.loads(source_bytes)
    source_digest = hashlib.sha256(source_bytes).hexdigest()
    if report["reference_sha256"] not in checkout_hashes(source_bytes) or report["case"]!=source["case"]:
        raise ValueError("seed source mismatch")
    check_frozen_inputs()
    case = common.Case(report["case"]["workload"],report["case"]["arch"],tuple(report["case"]["params"]))
    if case.workload!="matmuls" or case.arch!="nvdla":
        raise ValueError("the port ledger is frozen to native NVDLA 3mm")
    common.af.set_n_parallel_jobs(1)
    seed_points = source["points"] if "budget_best" in report else source["budget_selections"]
    def point_key(point):
        return tuple(point[k] for k in ("px","py","capacity_bytes"))
    seed_by_point = {point_key(x["architecture"]):x["witness"] for x in seed_points}
    records = []
    with exact_tail_evaluation():
        for entry in report["entries"]:
            point = entry["architecture"]
            seed = seed_by_point[point_key(point)]
            baseline,trace,_,_ = numeric(case,point,seed["mapping"])
            old = price(baseline,trace)
            if not isclose(old["edp"],entry["baseline"],rel_tol=1e-12):
                raise ValueError("port ledger changes the perfect-tile baseline")
            valid = []
            for i, item in enumerate(entry["candidates"]):
                if item["status"]=="verified":
                    score = price(item["witness"],item["independent_trace"])
                    valid.append(dict(candidate_index=i,changes=item["changes"],**score))
            winner = min([dict(candidate_index=None,**old)]+valid,key=lambda x:x["edp"])
            records.append(dict(architecture=point,perfect=old,candidates=valid,best=winner))
    selections = []
    for best in source["budget_selections"]:
        budget = best["budget"]
        allowed = [e for e in records if e["architecture"]["capacity_bytes"]<=budget["max_sram_bytes"]
                   and e["architecture"]["px"]*e["architecture"]["py"]<=budget["max_pes"]]
        chosen = min(allowed,key=lambda e:e["best"]["edp"])
        baseline = best["witness"]["edp"]
        selections.append(dict(budget=budget,architecture=chosen["architecture"],winner=chosen["best"],
                               perfect_edp=baseline,edp_reduction=1-chosen["best"]["edp"]/baseline))
    result = dict(status="complete",report_sha256=hashlib.sha256(raw).hexdigest(),seed_sha256=source_digest,
                  case=report["case"],native_action_count_source=True,independent_port_accounting=True,
                  external_sota_acceptance=False,points=records,budget_selections=selections)
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps([dict(architecture=e["architecture"],edp=e["winner"]["edp"],
                           reduction=e["edp_reduction"]) for e in selections]),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates",type=Path,required=True)
    parser.add_argument("--seeds",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    run(args.candidates,args.seeds,args.output)


if __name__=="__main__":
    main()
