"""Probe exact nondivisible temporal tiles feeding an existing spatial fanout."""

import argparse
from contextlib import contextmanager
import hashlib
from itertools import combinations
import json
from math import isclose, prod
from numbers import Integral
from pathlib import Path
from unittest.mock import patch

import sympy

from accelforge.frontend import mapping as ir
from accelforge.model._looptree.reuse.symbolic import symbolic as model
from research.joint_physical import replay as codec
from research.tracking_audit import common, shape_capacity_audit as physical


@contextmanager
def exact_tail_evaluation():
    if model.IMPERFECT:
        raise ValueError("the padding mode is outside the exact-tail contract")
    native_repeat = model.BuffetStats.repeat_temporal

    def repeat(stats, *args, **kwargs):
        value = native_repeat(stats, *args, **kwargs)
        # Each full or tail child crosses this temporal loop before merging.
        value.n_loops_above = stats.n_loops_above + 1
        return value

    def divides(divisor, extent):
        ints = (Integral, sympy.Integer)
        return isinstance(divisor, ints) and isinstance(extent, ints) and divisor > 0 and extent % divisor == 0

    with patch.object(model.BuffetStats, "repeat_temporal", repeat), patch.object(model, "known_perfect_factor", divides):
        yield


def branches(nodes, outer=()):
    active = list(outer)
    for position, node in enumerate(nodes):
        if isinstance(node, ir.Sequential):
            if position != len(nodes)-1:
                raise ValueError("continuation after a sequential split is outside this gate")
            for branch in node.nodes:
                yield from branches(branch.nodes if isinstance(branch, ir.Nested) else [branch], active)
            return
        if isinstance(node, ir.Split):
            raise ValueError("only sequential splits are supported")
        if isinstance(node, ir.Nested):
            yield from branches([*node.nodes,*nodes[position+1:]], active)
            return
        if isinstance(node, ir.Loop):
            active.append(node)
        if isinstance(node, ir.Compute):
            yield node.einsum, tuple(active)


def rank_trace(extent, loops, offset=0):
    if not loops:
        return list(range(offset, offset+extent)), extent
    loop, *remaining = loops
    if loop.initial_tile_shape is not None or int(loop.tile_shape)!=loop.tile_shape or loop.tile_shape<1:
        raise ValueError("unsupported noninteger or nonuniform tile")
    step = int(loop.tile_shape)
    sub = [rank_trace(min(step,extent-i),remaining,offset+i) for i in range(0,extent,step)]
    points = [point for covered,_ in sub for point in covered]
    cycles = (max if isinstance(loop, ir.Spatial) else sum)(cycles for _,cycles in sub)
    return points,cycles


def check_work(mapping, bounds_by_operator, data):
    result = {}
    for name,path in branches(mapping.nodes):
        dims = bounds_by_operator[name]
        counts = {}
        for rank, extent in dims.items():
            values, cycles = rank_trace(int(extent),[loop for loop in path if loop.rank_variable==rank])
            if values!=list(range(int(extent))):
                raise ValueError("iteration coverage failure")
            counts[rank] = cycles
        cycles = prod(counts.values())
        actions = prod(dims.values())
        actual_work = float(data[f"{name}<SEP>action<SEP>MAC<SEP>None<SEP>compute"])
        actual_latency = float(data[f"{name}<SEP>latency<SEP>MAC"])
        if actual_work!=actions or not isclose(actual_latency,cycles*1e-9,rel_tol=1e-10,abs_tol=0):
            raise ValueError(f"independent loop trace mismatch for {name}: {(actions,cycles)} vs {(actual_work,actual_latency)}")
        result[name] = dict(actions=int(actions),compute_cycles=int(cycles))
    return result


def numeric(case, point, record, change=()):
    shape = point["px"], point["py"]
    capacity = point["capacity_bytes"]
    metrics = common.RU | common.af.Metrics.ACTIONS
    spec = physical.build(case,shape,capacity,metrics)
    per_op = {}

    def component(name, key):
        if name not in per_op:
            per_op[name] = spec.calculate_component_area_energy_latency_leak(einsum_name=name,area=False)
        return per_op[name].arch.find(key)

    mapping = codec.decode(record,component)
    paths = dict(branches(mapping.nodes))
    for operator,ordinal,tile in change:
        loop = paths[operator][ordinal]
        loop.tile_shape = tile
        loop._assume_perfect_factor = False
        loop.tile_pattern = loop.tile_pattern.update(calculated_n_iterations=None)
    spec.mapping = mapping
    native = common.evaluate_mapping(spec).data.iloc[0]
    full_bounds = common.get_rank_variable_bounds_for_all_einsums(spec)
    # Each native einsum's affine variables (including reduction variables).
    for name in paths:
        component(name,"MAC")  # A scalar operator has no Spatial node to populate this cache.
    dims = {name:{r:full_bounds[r] for r in per_op[name].workload.einsums[name].rank_variables}
            for name in paths}
    independent = check_work(mapping,dims,native)
    row = {"Total<SEP>mapping":lambda:mapping,"Total<SEP>energy":native["Total<SEP>energy"],
           "Total<SEP>latency":native["Total<SEP>latency"]}
    witness = physical.validate_pick(case,shape,capacity,row,capture_actions=True)
    witness["mapping"] = codec.encode(mapping)
    return witness,independent,paths,full_bounds


def proposals(paths, bounds, point):
    names = {"reuse_input":"px","reuse_output":"py"}
    for operator,path in paths.items():
        previous = {r:(int(v),None) for r,v in bounds.items()}
        for index, loop in enumerate(path):
            rank = loop.rank_variable
            _, previous_idx = previous[rank]
            previous[rank] = int(loop.tile_shape), index
            if not isinstance(loop,ir.Spatial) or loop.tile_shape!=1 or previous_idx is None:
                continue
            outer = path[previous_idx]
            if not isinstance(outer,ir.Temporal) or outer._fused or outer.initial_tile_shape is not None:
                continue
            if sum(any(n is outer for n in other) for other in paths.values())!=1:
                continue
            parent = next((int(n.tile_shape) for n in reversed(path[:previous_idx]) if n.rank_variable==rank),
                          int(bounds[rank]))
            next_extent = min(parent,point[names[loop.name]])
            if int(outer.tile_shape)<next_extent<parent and parent%next_extent:
                yield operator,previous_idx,next_extent


def run(reference, output, all_points=False):
    raw = reference.read_bytes()
    reference = json.loads(raw)
    case = common.Case(reference["case"]["workload"],reference["case"]["arch"],tuple(reference["case"]["params"]))
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    entries = []
    source = reference["points"] if all_points else reference["budget_selections"]
    with exact_tail_evaluation():
        for selected in source:
            if not selected.get("witness",{}).get("feasible"):
                raise ValueError("each search seed must carry a physical mapping")
            point,witness = selected["architecture"],selected["witness"]
            original = witness["mapping"]
            baseline,trace,paths,bounds = numeric(case,point,original)
            if not isclose(baseline["edp"],witness["edp"],rel_tol=1e-12):
                raise ValueError("scoped model changed the perfect reference")
            candidates = list(proposals(paths,bounds,point))
            if len(candidates)>8:
                raise ValueError("too many changed loop sites for bounded tail refinement")
            record = dict(architecture=point,baseline=baseline["edp"],baseline_trace=trace,
                          candidates=[],proposals=candidates)
            for size in range(1,len(candidates)+1):
                for changes in combinations(candidates,size):
                    item = dict(changes=changes)
                    try:
                        new,trace,_,_ = numeric(case,point,original,changes)
                        item.update(status="verified",witness=new,independent_trace=trace)
                    except ValueError as error:
                        item.update(status="rejected",reason=str(error))
                    record["candidates"].append(item)
            record["best_edp"] = min([baseline["edp"]]+[x["witness"]["edp"] for x in record["candidates"]
                                                       if x["status"]=="verified"])
            entries.append(record)
            print(json.dumps(dict(architecture=point,candidates=len(candidates),
                                  baseline=record["baseline"],best_edp=record["best_edp"])),flush=True)
    report = dict(status="complete",scope="retile existing budget witnesses; independent trace; no full grammar search",
                  reference_sha256=hashlib.sha256(raw).hexdigest(),
                  case=reference["case"],entries=entries,external_sota_acceptance=False)
    if all_points:
        report["scope"] = "retile one independently generated physical witness at every hardware point"
        report["budget_best"] = []
        for selection in reference["budget_selections"]:
            budget = selection["budget"]
            eligible = [e for e in entries if e["architecture"]["capacity_bytes"]<=budget["max_sram_bytes"]
                        and e["architecture"]["px"]*e["architecture"]["py"]<=budget["max_pes"]]
            best = min(eligible,key=lambda e:e["best_edp"])
            report["budget_best"].append(dict(budget=budget,architecture=best["architecture"],
                                             edp=best["best_edp"],perfect_edp=selection["witness"]["edp"]))
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")


def verify(path,output):
    raw = path.read_bytes()
    report = json.loads(raw)
    case = common.Case(report["case"]["workload"],report["case"]["arch"],tuple(report["case"]["params"]))
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    replayed = 0
    with exact_tail_evaluation():
        for entry in report["entries"]:
            accepted = [entry["baseline"]]
            for candidate in entry["candidates"]:
                if candidate["status"]!="verified":
                    continue
                expected = candidate["witness"]
                actual,trace,_,_ = numeric(case,entry["architecture"],expected["mapping"])
                if trace!=candidate["independent_trace"]:
                    raise ValueError("independent iteration trace changed after reconstruction")
                for field in ("edp","energy","latency","gb_bytes","actions","reservation_bits","mapping"):
                    if actual[field]!=expected[field]:
                        raise ValueError(f"independent tail witness changed {field}")
                accepted.append(actual["edp"])
                replayed += 1
            if min(accepted)!=entry["best_edp"]:
                raise ValueError("reported best EDP differs from the checked candidates")
    for selection in report.get("budget_best",()):
        budget = selection["budget"]
        eligible = [e for e in report["entries"] if e["architecture"]["capacity_bytes"]<=budget["max_sram_bytes"]
                    and e["architecture"]["px"]*e["architecture"]["py"]<=budget["max_pes"]]
        best = min(eligible,key=lambda e:e["best_edp"])
        if best["best_edp"]!=selection["edp"] or best["architecture"]!=selection["architecture"]:
            raise ValueError("reported budget winner differs from the checked candidates")
    reductions = ([1-e["edp"]/e["perfect_edp"] for e in report["budget_best"]] if "budget_best" in report
                  else [1-e["best_edp"]/e["baseline"] for e in report["entries"]])
    result = dict(status="verified",physical_witnesses=replayed,report_sha256=hashlib.sha256(raw).hexdigest(),
                  edp_reduction=reductions,
                  same_native_action_costs=True,external_sota_acceptance=False)
    output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(result),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--reference",type=Path)
    group.add_argument("--replay",type=Path)
    parser.add_argument("--all-point-witnesses",action="store_true")
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.replay:
        verify(args.replay,args.output)
    else:
        run(args.reference,args.output,args.all_point_witnesses)


if __name__=="__main__":
    main()
