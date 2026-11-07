"""Check full/tail port phases independently of whole-layer latency aggregation."""

import argparse
from collections import defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
from unittest.mock import patch

from research.joint_physical import replay as codec
from research.runtime.tail_tiles import branches, exact_tail_evaluation, model
from research.tracking_audit import common, shape_capacity_audit as physical


def account(actions, cycles):
    total = defaultdict(int)
    for key,value in actions.items():
        _,_,component,_,op = key.split("<SEP>")
        if value<0 or int(value)!=value:
            raise ValueError("noninteger phase action count")
        total[component,op] += int(value)
    dram = F(total["MainMemory","read"]+total["MainMemory","write"],307_200_000_000)
    read = F(total["GlobalBuffer","read"],4_096_000_000_000)
    write = F(total["GlobalBuffer","write"],1_024_000_000_000)
    compute = F(cycles,1_000_000_000)
    return max(dram,read,write,compute),dram+read+write+compute


def phases(case, point, candidate):
    witness = candidate["witness"]
    metrics = common.RU|common.af.Metrics.ACTIONS
    shape = (point["px"],point["py"])
    capacity = point["capacity_bytes"]
    spec = physical.build(case,shape,capacity,metrics)
    evaluated = {}
    def component(name,key):
        if name not in evaluated:
            evaluated[name] = spec.calculate_component_area_energy_latency_leak(einsum_name=name,area=False)
        return evaluated[name].arch.find(key)
    spec.mapping = codec.decode(witness["mapping"],component)
    paths = dict(branches(spec.mapping.nodes))
    changed = defaultdict(list)
    for name,ordinal,tile in candidate["changes"]:
        changed[name].append((paths[name][ordinal].rank_variable,tile))
    if any(len(value)!=1 for value in changed.values()):
        raise ValueError("at most one full/tail site per operator")
    get_shape = model.get_stride_and_tile_shape
    total_latency = F()
    serialized_latency = F()
    records = {}
    for name,trace in candidate["independent_trace"].items():
        whole = {k:int(v) for k,v in witness["actions"].items() if k.startswith(name+"<SEP>")}
        if name not in changed:
            delay,serial = account(whole,trace["compute_cycles"])
            total_latency += delay
            serialized_latency += serial
            records[name] = dict(phase_count=1,phase_latency_s=float(delay))
            continue
        rank,tile = changed[name][0]
        aggregate = defaultdict(int)
        all_cycles = 0
        per_phase = []
        for part in (0,1):
            occurrences = 0
            def select(node,current_shape,n,info):
                nonlocal occurrences
                result = get_shape(node,current_shape,n,info)
                if (info.mapping[-1].einsum==name and node.rank_variable==rank and node.tile_shape==tile
                    and not node._assume_perfect_factor):
                    if not isinstance(result.shape,model.SequenceOfRepatedvalues) or len(result.shape.sequence)!=2:
                        raise ValueError("expected one full phase and one remainder phase")
                    occurrences += 1
                    return model.StrideAndShape(result.stride,result.shape.sequence[part])
                return result
            with patch.object(model,"get_stride_and_tile_shape",select):
                data = common.evaluate_mapping(spec).data.iloc[0]
            if occurrences<1:
                raise ValueError("no explicit tail phase was evaluated")
            phase_actions = {k:float(data[k]) for k in data.index if k.startswith(name+"<SEP>action<SEP>")}
            for k,v in phase_actions.items():
                if int(v)!=v:
                    raise ValueError("fractional action in isolated phase")
                aggregate[k] += int(v)
            cycles = float(data[f"{name}<SEP>latency<SEP>MAC"])*1e9
            if abs(cycles-round(cycles))>1e-8:
                raise ValueError("noninteger MAC cycles in isolated phase")
            cycles = round(cycles)
            all_cycles += cycles
            delay,serial = account(phase_actions,cycles)
            total_latency += delay
            serialized_latency += serial
            per_phase.append(dict(kind=("full","remainder")[part],mac_cycles=cycles,
                                  latency_s=float(delay),bit_actions=phase_actions))
        differences = {k:aggregate.get(k,0)-whole.get(k,0) for k in sorted(whole.keys()|aggregate.keys())
                       if whole.get(k,0)!=aggregate.get(k,0)}
        if all_cycles!=trace["compute_cycles"] or differences:
            raise ValueError(f"isolated phases do not reconstruct full native actions for {name}: {differences}")
        records[name] = dict(phase_count=2,phases=per_phase)
    return dict(phase_latency_s=float(total_latency),serialized_port_s=float(serialized_latency),
                phase_edp=witness["energy"]*float(total_latency),
                fully_serialized_edp=witness["energy"]*float(serialized_latency),operators=records)


def run(tail, ledger, output, search_validated):
    report = json.loads(tail.read_bytes())
    repriced = json.loads(ledger.read_bytes())
    case = common.Case(report["case"]["workload"],report["case"]["arch"],tuple(report["case"]["params"]))
    common.af.set_n_parallel_jobs(1)
    done = []
    by_point = {tuple(e["architecture"].values()):e for e in report["entries"]}
    checked = {}
    with exact_tail_evaluation():
        for selection in repriced["budget_selections"]:
            budget = selection["budget"]
            if search_validated:
                ranked = sorted([(score["edp"],e["architecture"],score["candidate_index"])
                          for e in repriced["points"] for score in e["candidates"]
                          if e["architecture"]["capacity_bytes"]<=budget["max_sram_bytes"]
                          and e["architecture"]["px"]*e["architecture"]["py"]<=budget["max_pes"]],
                          key=lambda e:e[0])
            else:
                ranked = [(selection["winner"]["edp"],selection["architecture"],
                           selection["winner"]["candidate_index"])]
            best = selection["perfect_edp"]
            winner = None
            attempted = []
            for aggregate,point,index in ranked:
                if search_validated and aggregate>=best:
                    break
                key = (tuple(point.values()),index)
                if key not in checked:
                    item = by_point[key[0]]["candidates"][index]
                    row = dict(architecture=point,aggregate_edp=aggregate,changes=item["changes"],candidate_index=index)
                    try:
                        row.update(status="verified",**phases(case,point,item))
                        if row["phase_edp"]<aggregate*(1-1e-12):
                            raise AssertionError("phase score below sum-of-port workload bound")
                    except ValueError as error:
                        row.update(status="rejected",reason=str(error))
                    checked[key] = row
                row = checked[key]
                attempted.append(row)
                if row["status"]=="verified" and row["phase_edp"]<best:
                    winner,best = row,row["phase_edp"]
            done.append(dict(budget=budget,perfect_edp=selection["perfect_edp"],phase_edp=best,
                             reduction=1-best/selection["perfect_edp"],winner=winner,
                             candidate_checks=attempted))
            print(json.dumps({k:v for k,v in done[-1].items() if k not in ("winner","candidate_checks")}
                             | dict(candidate_checks=len(attempted))),flush=True)
    result = dict(status="complete",scope="native action counts; throughput within each isolated full/tail phase",
                  searched_supported_candidates=search_validated,distinct_candidates_checked=len(checked),
                  external_sota_acceptance=False,selections=done)
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tail",type=Path,required=True)
    parser.add_argument("--ledger",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--search-validated",action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    run(args.tail,args.ledger,args.output,args.search_validated)


if __name__=="__main__":
    main()
