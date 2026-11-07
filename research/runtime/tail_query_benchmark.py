"""Compare a physical ordering with grouped TPE on the same tail-query domain."""

import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from math import prod
from pathlib import Path
import random
import sys

from research.joint_physical import replay as codec
from research.runtime.summarize_joint_trials import checkout_hashes
from research.runtime.tail_tiles import branches, rank_trace
from research.tracking_audit import common, shape_capacity_audit as physical


@dataclass(frozen=True)
class Design:
    point: int
    mask: int
    shape: tuple
    sram: int
    priority: float


def read(path):
    raw = path.read_bytes()
    return json.loads(raw), raw


def prepare(seed_path, tail_path, ledger_path):
    seeds, seed_bytes = read(seed_path)
    tails, tail_bytes = read(tail_path)
    ports, port_bytes = read(ledger_path)
    if (tails["reference_sha256"] not in checkout_hashes(seed_bytes) or
        ports["report_sha256"] not in checkout_hashes(tail_bytes)):
        raise ValueError("report lineage mismatch")
    case = common.Case(seeds["case"]["workload"],seeds["case"]["arch"],tuple(seeds["case"]["params"]))
    if case.workload!="matmuls" or case.params[0]!=3:
        raise ValueError("benchmark scope is the registered 3mm tail domain")
    designs = []
    oracle = {}
    for i,(base,entry,ledger) in enumerate(zip(seeds["points"],tails["entries"],ports["points"],strict=True)):
        h = entry["architecture"]
        if h!=base["architecture"] or h!=ledger["architecture"]:
            raise ValueError("candidate domain changed")
        if not entry["candidates"]:
            continue
        shape, sram = (h["px"],h["py"]),h["capacity_bytes"]
        spec = physical.build(case,shape,sram,common.RU)
        evaluated = {}
        def component(name, key):
            if name not in evaluated:
                evaluated[name] = spec.calculate_component_area_energy_latency_leak(einsum_name=name,area=False)
            return evaluated[name].arch.find(key)
        mapping = codec.decode(base["witness"]["mapping"],component)
        paths = dict(branches(mapping.nodes))
        dims = common.get_rank_variable_bounds_for_all_einsums(spec)
        hits = {x["candidate_index"]:x["edp"] for x in ledger["candidates"]}
        # Only the perfect seed's physical counts and the public loop edits
        # are used to order calls. Actual tail outcomes stay in the oracle.
        for index, item in enumerate(entry["candidates"]):
            changed = {name:{} for name in paths}
            for name,ordinal,tile in item["changes"]:
                changed[name][ordinal] = tile
            estimate = 0.0
            for name,path in paths.items():
                new = []
                for j,node in enumerate(path):
                    if j in changed[name]:
                        node = node.model_copy(deep=True)
                        node.tile_shape = changed[name][j]
                    new.append(node)
                variables = evaluated[name].workload.einsums[name].rank_variables
                cycles = prod(rank_trace(int(dims[rank]),[n for n in new if n.rank_variable==rank])[1]
                              for rank in variables)
                estimate += max(cycles*1e-9,ledger["perfect"]["ledger"][name]["memory_latency_s"])
            key = (i,index)
            designs.append(Design(i,index,shape,sram,estimate*base["witness"]["energy"]))
            oracle[key] = hits.get(index)
    initial = [s["witness"]["edp"] for s in seeds["budget_selections"]]
    budgets = [s["budget"]["max_sram_bytes"] for s in seeds["budget_selections"]]
    return designs,oracle,initial,budgets,hashlib.sha256(port_bytes).hexdigest()


def run(designs, answer, initial, budgets, max_queries, method, seed, optuna):
    rng = random.Random(seed)
    if method.startswith("tpe"):
        studies = [optuna.create_study(direction="minimize",
                    sampler=optuna.samplers.TPESampler(seed=seed*31+i,multivariate=True,group=True,
                                                       constant_liar=True))
                   for i in range(len(budgets))]
    indexed = []
    for cap in budgets:
        geometries = defaultdict(lambda:defaultdict(list))
        for d in designs:
            if d.sram<=cap:
                geometries[d.shape[0]][d.sram].append(d)
        indexed.append(geometries)
    def parameters(d,groups):
        px,capacity = d.shape[0],d.sram
        cap_key,mask_key = f"sram_for_{px}",f"mask_for_{px}_{capacity}"
        choices = groups[px][capacity]
        return ({"array_x":px,cap_key:capacity,mask_key:choices.index(d)},
                {"array_x":optuna.distributions.CategoricalDistribution(sorted(groups)),
                 cap_key:optuna.distributions.CategoricalDistribution(sorted(groups[px])),
                 mask_key:optuna.distributions.IntDistribution(0,len(choices)-1)})
    if method=="tpe-warm":
        for i,(cap,groups) in enumerate(zip(budgets,indexed)):
            ranked = sorted((d for d in designs if d.sram<=cap),key=lambda d:(d.priority,d.point,d.mask))
            for d in ranked[:3]:
                studies[i].enqueue_trial(parameters(d,groups)[0])
    history = []
    observed = {}
    best = list(initial)
    repeat_draws = random_fallbacks = 0
    for n in range(max_queries):
        i = n%len(budgets)
        eligible = [d for d in designs if d.sram<=budgets[i] and (d.point,d.mask) not in observed]
        if not eligible:
            raise ValueError("query budget exceeds the common finite domain")
        trial = None
        pending_duplicates = []
        if method=="physical":
            d = min(eligible,key=lambda d:(d.priority,d.point,d.mask))
        else:
            for _ in range(16):
                trial = studies[i].ask()
                groups = indexed[i]
                px = trial.suggest_categorical("array_x",sorted(groups))
                capacity = trial.suggest_categorical(f"sram_for_{px}",sorted(groups[px]))
                choices = groups[px][capacity]
                pos = trial.suggest_int(f"mask_for_{px}_{capacity}",0,len(choices)-1)
                d = choices[pos]
                key = d.point,d.mask
                if key not in observed:
                    break
                repeat_draws += 1
                # The constant liar sees pending repeats while drawing again.
                # A duplicate supplies no new training observation.
                pending_duplicates.append(trial)
            else:
                d = rng.choice(eligible)
                trial = None
                random_fallbacks += 1
        key = d.point,d.mask
        value = observed[key] = answer(key)
        if method.startswith("tpe"):
            for duplicate in pending_duplicates:
                studies[i].tell(duplicate,state=optuna.trial.TrialState.FAIL)
            objective = value if value is not None else 100*max(initial)
            for j,(cap,groups) in enumerate(zip(budgets,indexed)):
                if d.sram>cap:
                    continue
                if j==i and trial is not None:
                    studies[j].tell(trial,objective)
                else:
                    params, distributions = parameters(d,groups)
                    studies[j].add_trial(optuna.trial.create_trial(params=params,
                        distributions=distributions,value=objective))
        if value is not None:
            best = [min(old,value) if d.sram<=cap else old for cap,old in zip(budgets,best)]
        history.append(dict(point=d.point,mask=d.mask,edp=value,best_by_budget=best))
    return dict(method=method,seed=seed,history=history,repeat_draws=repeat_draws,random_fallbacks=random_fallbacks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-report",type=Path,required=True)
    parser.add_argument("--tail-report",type=Path,required=True)
    parser.add_argument("--ledger",type=Path,required=True)
    parser.add_argument("--optuna-path",type=Path,default=Path("libraries/tail_optuna"))
    parser.add_argument("--queries",type=int,default=96)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    sys.path.append(str(args.optuna_path.resolve()))
    import optuna
    optuna.logging.set_verbosity(optuna.logging.ERROR)
    common.af.set_n_parallel_jobs(1)
    designs,values,initial,budgets,proof = prepare(args.seed_report,args.tail_report,args.ledger)
    def query(key):
        return values[key]
    runs = [run(designs,query,initial,budgets,args.queries,"physical",0,optuna)]
    for method in ("tpe","tpe-warm"):
        runs.extend(run(designs,query,initial,budgets,args.queries,method,seed,optuna) for seed in range(5))
    targets = [min([baseline]+[values[d.point,d.mask] for d in designs if d.sram<=cap
                                              and values[d.point,d.mask] is not None])
               for baseline,cap in zip(initial,budgets)]
    report = dict(status="complete",scope="paired query-budget comparison over a fixed native tail neighborhood",
                  identical_physically_evaluated_seeds=True,warm_tpe_uses_three_prior_designs_per_budget=True,
                  tpe_shares_observations_with_all_admitting_budget_studies=True,
                  candidate_outcomes_hidden_until_query=True,elapsed_time_comparison=False,
                  candidate_count=len(designs),budgets=budgets,initial_edp=initial,full_neighborhood_edp=targets,
                  optuna_version=optuna.__version__,oracle_ledger_sha256=proof,runs=runs,
                  external_sota_acceptance=False)
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")


if __name__=="__main__":
    main()
