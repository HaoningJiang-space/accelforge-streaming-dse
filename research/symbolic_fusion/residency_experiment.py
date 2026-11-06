"""Fair B study: cached flat vs grounded contexts vs shared conditional DP."""
import argparse
from dataclasses import asdict
from fractions import Fraction
import gzip
import hashlib
from itertools import product
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import time
import tracemalloc
from .model import Plan
from .residency_search import Factors,CONTEXTS,compile_search,queries,weak,add
from .residency_oracle import execute
from .experiment import json_default,native_actions


def independent_front(rows):
    values=set((r['peak'],r['energy'],r['latency'])for r in rows)
    return {a for a in values if not any(b!=a and all(x<=y for x,y in zip(b,a))for b in values)}


def legal(plan,shape):
    return all(j<=shape[0] and k<=shape[1]for k,j in plan.tiles)


def path(mode):
    start=time.perf_counter();f=Factors();built=time.perf_counter()
    result,stats=compile_search(f,mode);compiled=time.perf_counter()
    answer=queries(result,f);end=time.perf_counter()
    return f,result,answer,stats,dict(construction_s=built-start,compile_s=compiled-built,query_s=end-compiled,total_s=end-start)


def benchmark():
    modes=('cached_flat','grounded','conditional');samples={m:[]for m in modes};stats={};memory={}
    for mode in modes:path(mode)
    rng=random.Random(20261107)
    for _ in range(9):
        order=list(modes);rng.shuffle(order)
        for mode in order:
            *_,stats[mode],timing=path(mode);samples[mode].append(timing)
    for mode in modes:
        tracemalloc.start();path(mode);_,memory[mode]=tracemalloc.get_traced_memory();tracemalloc.stop()
    return dict(samples=samples,statistics=stats,python_traced_peak_bytes=memory,
        medians={m:{k:statistics.median(r[k]for r in samples[m])for k in samples[m][0]}for m in modes},
        protocol='9 shuffled paired trials; warm Python/Sympy; common constructor, empty shared factor cache per path, complete precompiled frontiers for all environments, same four joint queries; memory separate')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--native',action='store_true');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    report=dict(status='in_progress',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                native_mapping_search_calls=0)
    def save():
        (args.output/'summary.json').write_text(json.dumps(report,default=json_default,indent=2)+'\n')
    # Measurement cannot see exhaustive/native results or use their provenance.
    report['timing']=benchmark();save()
    f=Factors();records=[];start=time.perf_counter()
    for plan in f.base.plans():
        for ci,context in enumerate(CONTEXTS):
            out=execute(f.n,plan.stripe,plan.tiles,context=context)
            factors=[f.get(i,plan.stripe,t)[ci]for i,t in enumerate(plan.tiles)]
            pred=(0,0,Fraction(0))
            for factor in factors:pred=add(pred,factor)
            assert pred==(out['peak'],out['energy'],out['latency'])
            assert add(*factors[:2])==out['prefix']
            if context=='dram':
                for i in range(3):
                    raw=f.dram[i](f.n,plan.stripe,*plan.tiles[i])[:6]
                    assert tuple(out['phases'][i][name]for name in f.base.names)==tuple(raw)
            records.append(dict(plan=asdict(plan),context=context,**out))
    report['oracle']=dict(physical_programs=len(records),events=sum(r['events']for r in records),seconds=time.perf_counter()-start,
                         scalar_arithmetic_full_size=False)
    small=[]
    for n in (4,8):
        count=0;g=Factors(n,(n//2,n),(n//4,n//2))
        for plan in g.base.plans():
            for ci,c in enumerate(CONTEXTS):
                out=execute(n,plan.stripe,plan.tiles,numeric=True,context=c)
                pred=(0,0,Fraction(0))
                for i,t in enumerate(plan.tiles):pred=add(pred,g.get(i,plan.stripe,t)[ci])
                assert pred==(out['peak'],out['energy'],out['latency'])
                count+=1
        small.append(dict(n=n,plans=count,all_scalar_MACs_checked=True))
    report['small_scalar']=small
    by_env={i:[r for r in records if r['context']==c and legal(Plan(r['plan']['stripe'],tuple(map(tuple,r['plan']['tiles']))),shape)]for i,(shape,c)in enumerate(f.envs)}
    capacities={128*1024,132*1024}
    for r in records:capacities.update((r['peak']-1,r['peak'],r['peak']+1))
    report['environment_plan_counts']=[dict(shape=shape,context=c,plans=len(by_env[i]))for i,(shape,c)in enumerate(f.envs)]
    report['capacities']=sorted(capacities)
    report['complete_frontiers']={};report['joint_picks']={}
    for mode in ('cached_flat','grounded','conditional'):
        result,stats=compile_search(Factors(),mode)
        for i,rows in by_env.items():assert {v for v,_ in result[i]}==independent_front(rows)
        for cap in capacities:
            for shape in f.shapes:
                envs=[i for i,(s,c)in enumerate(f.envs)if s==shape]
                expected=independent_front([r for i in envs for r in by_env[i]if r['peak']<=cap])
                actual=queries(result,f,(cap,))[(shape,cap)]
                assert {v for v,_ in actual}==expected
        if mode=='grounded':
            report['complete_frontiers']={str(i):[dict(vector=v,plan=asdict(p))for v,p in rows]for i,rows in result.items()}
            for key,entries in queries(result,f).items():
                best=min(entries,key=lambda row:row[0][1]*row[0][2])if entries else None
                report['joint_picks'][str(key)]=None if best is None else dict(vector=best[0],shape=best[1][0],context=best[1][1],plan=asdict(best[1][2]))
    # Context-flip witnesses come from independent interpreter prefix scores.
    witnesses=[];checks=0
    for shape in f.shapes:
        for stripe in f.stripes:
            groups={c:{}for c in CONTEXTS}
            for r in records:
                p=Plan(r['plan']['stripe'],tuple(map(tuple,r['plan']['tiles'])))
                if p.stripe==stripe and legal(p,shape):groups[r['context']][p.tiles[:2]]=r['prefix']
            fronts={c:independent_front([dict(peak=v[0],energy=v[1],latency=v[2])for v in rows.values()])for c,rows in groups.items()}
            for dropped,kept in (('gb','dram'),('dram','gb')):
                for q,qv in groups[dropped].items():
                    if qv in fronts[dropped] or groups[kept][q] not in fronts[kept]:continue
                    p,pv=next((p,v)for p,v in groups[dropped].items()if v!=qv and weak(v,qv))
                    assert not weak(groups[kept][p],groups[kept][q])
                    for tail in f.options(2,stripe,shape):
                        ci=CONTEXTS.index(dropped);r=f.get(2,stripe,tail)[ci]
                        assert weak(add(pv,r),add(qv,r));checks+=1
                    i=f.envs.index((shape,kept));before=independent_front(by_env[i])
                    remaining=[r for r in by_env[i]if not(r['plan']['stripe']==stripe and tuple(map(tuple,r['plan']['tiles'][:2]))==q)]
                    lost=before-independent_front(remaining)
                    witnesses.append(dict(shape=shape,stripe=stripe,dropped_context=dropped,kept_context=kept,
                        dominator=p,discarded=q,dominator_scores={c:groups[c][p]for c in CONTEXTS},
                        discarded_scores={c:groups[c][q]for c in CONTEXTS},lost_complete_frontier_points=list(lost)))
    report['context_witnesses']=witnesses;report['pruning_continuations_checked']=checks
    report['all_exact_frontiers_equal']=True
    with gzip.open(args.output/'oracle_records.json.gz','wt')as file:json.dump(records,file,default=json_default)
    save()
    if args.native:
        from .residency_native import check
        native=[];start=time.perf_counter()
        for i,(shape,c)in enumerate(f.envs):
            for r in by_env[i]:
                p=Plan(r['plan']['stripe'],tuple(map(tuple,r['plan']['tiles'])))
                out=check(p,c,shape)
                assert out['feasible']and out['globalbuffer_peak_bits']==r['peak']*8
                assert math.isclose(out['energy_j'],r['energy']*1e-15,rel_tol=1e-12)
                assert math.isclose(out['latency_s'],float(r['latency'])*1e-9,rel_tol=1e-12)
                actions=[native_actions(p)for p in out['phases']]
                assert actions==[{k:phase[k]for k in a}for a,phase in zip(actions,r['phases'])]
                native.append(dict(env=i,shape=shape,context=c,plan=r['plan'],mapping_id=out['mapping_id'],
                    peak_bytes=out['globalbuffer_peak_bits']//8,energy_j=out['energy_j'],latency_s=out['latency_s'],phase_actions=actions))
                if len(native)%64==0:print(json.dumps(dict(native_validated=len(native))),flush=True)
        report['native']=dict(evaluations=len(native),phase_models=3*len(native),seconds=time.perf_counter()-start,
            all_actions_resources_costs_match=True,timing_scope='instrumented fixed-map cross-validation, not search performance')
        with gzip.open(args.output/'native_records.json.gz','wt')as file:json.dump(native,file)
    report['source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [
        *Path(__file__).parent.glob('residency*.py'),Path(__file__).with_name('model.py'),Path(__file__).with_name('native_check.py'),
        Path(__file__).with_name('RESIDENCY_CONTRACT.md'),Path('examples/arches/nvdla.yaml')]}
    report['status']='complete';save()
    print(json.dumps(dict(status='complete',physical_programs=len(records),environments=len(by_env),capacity_queries=len(capacities),
        context_flips=len(witnesses),essential_flips=sum(bool(w['lost_complete_frontier_points'])for w in witnesses))))


if __name__=='__main__':main()
