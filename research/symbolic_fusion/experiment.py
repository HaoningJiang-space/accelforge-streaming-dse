"""Reproduce the bounded symbolic Fusion study, including independent checks."""
import argparse
from dataclasses import asdict
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
from .model import Family, State, combine
from .eliminate import flat, eliminate
from .oracle import execute

ROOT = Path(__file__).resolve().parents[2]


def json_default(value):
    if isinstance(value,Fraction):
        return dict(numerator=value.numerator,denominator=value.denominator)
    raise TypeError(type(value).__name__)


def independent_frontier(records, capacity=None):
    # No call to the search's frontier/dominance/composition implementation.
    vectors=set((r['peak'],r['energy'],r['latency']) for r in records
                if capacity is None or r['peak']<=capacity)
    return {a for a in vectors if not any(b!=a and b[0]<=a[0] and b[1]<=a[1] and b[2]<=a[2] for b in vectors)}


def result_vectors(result):
    return {s.vector for s,_ in result}


def run_path(name):
    begin=time.perf_counter(); f=Family(); built=time.perf_counter()
    if name=='flat':
        result,stats=flat(f)
    elif name=='cached_flat':
        result,stats=flat(f,cache_factors=True)
    elif name=='eliminated':
        result,stats=eliminate(f)
    elif name=='budget128':
        result,stats=eliminate(f,128*1024)
    else:
        raise ValueError(name)
    end=time.perf_counter()
    return result,stats,dict(construction_s=built-begin,search_s=end-built,total_s=end-begin)


def benchmark():
    # Warm library code only. Every measured invocation rebuilds the symbolic
    # family and starts with an empty per-search factor cache.
    names=['flat','cached_flat','eliminated','budget128']
    for name in names:
        run_path(name)
    rng=random.Random(20261105); samples={n:[] for n in names}; stats={}
    for _ in range(9):
        order=names[:];rng.shuffle(order)
        for name in order:
            _,stats[name],timing=run_path(name);samples[name].append(timing)
    memory={}
    for name in names:
        tracemalloc.start()
        result,_,_=run_path(name)
        _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        memory[name]=peak
        del result
    return dict(protocol='one process; 9 shuffled paired trials; warm Python/Sympy; empty factor cache; construction included; memory in separate untimed pass',
        samples=samples, medians={n:{k:statistics.median(s[k]for s in samples[n])for k in samples[n][0]}for n in names},
        statistics=stats,python_traced_peak_bytes=memory,
        interpreter=sys.version,platform=platform.platform())


def native_actions(phase):
    values=dict(dram_read=0,dram_write=0,gb_read=0,gb_write=0,reg_read=0,reg_write=0,mac=0)
    for key,value in phase['actions'].items():
        _,component,_,action=key.split('<SEP>')
        if component in ('MainMemory','GlobalBuffer'):
            assert int(value)==value and int(value)%8==0
            values[('dram_' if component=='MainMemory' else 'gb_')+action]+=int(value)//8
        elif component=='Register':
            assert int(value)==value and int(value)%8==0
            values['reg_'+action]+=int(value)//8
        elif component=='MAC':
            assert int(value)==value
            values['mac']+=int(value)
    return values


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--native',action='store_true',help='validate every fixed full-size plan with native model')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    report=dict(status='in_progress',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        grammar=dict(n=256,stripes=[64,128,256],tiles=[32,64],configured_array=[64,96],precision_bits=8,
                     objectives=['GB bytes','energy fJ','latency ns']),native_search_calls=0)
    def save():
        (args.output/'summary.json').write_text(json.dumps(report,default=json_default,indent=2,allow_nan=False)+'\n')
    # The timing phase deliberately happens before exhaustive validation and
    # native imports, so neither measured search can consume oracle records.
    report['timing']=benchmark();save()
    family=Family();report['formulas']=family.formulas()
    assert family.factor_calls==0
    records=[]; started=time.perf_counter()
    for plan in family.plans():
        observed=execute(family.n,plan.stripe,plan.tiles)
        predicted=State(0,0,Fraction(0),())
        for i,tile in enumerate(plan.tiles):
            factor=family.factor(i,plan.stripe,*tile)
            expected_counts=family._functions[i](family.n,plan.stripe,*tile)[:6]
            assert tuple(observed['phases'][i][name]for name in family.names)==tuple(expected_counts)
            predicted=combine(predicted,factor)
        assert predicted.vector==(observed['peak'],observed['energy'],observed['latency'])
        assert asdict(predicted.effect)==observed['effect']
        records.append(dict(plan=asdict(plan),**observed))
    report['full_event_execution']=dict(plans=len(records),events=sum(r['events']for r in records),
        seconds=time.perf_counter()-started,scalar_arithmetic=False)
    # Separate small scalar exhaustive validation: every dense MAC and write.
    small=[]
    for n in (4,8):
        f=Family(n,(n//2,n),(n//4,n//2));count=0
        for plan in f.plans():
            execute(n,plan.stripe,plan.tiles,numeric=True);count+=1
        small.append(dict(n=n,plans=count,scalar_arithmetic=True))
    report['small_scalar_execution']=small
    report['frontier_checks']=[]
    compiled,_=eliminate(family)
    conditional,_=eliminate(family,conditional=True)
    all_effects={(r['effect']['base'],r['effect']['carried'],r['energy'],r['latency']) for r in records}
    effect_front={a for a in all_effects if not any(b!=a and all(x<=y for x,y in zip(b,a))for b in all_effects)}
    predicted_effect_front={(s.effect.base,s.effect.carried,s.energy,s.latency)for s,_ in conditional}
    assert predicted_effect_front==effect_front
    report['conditional_frontier']=[dict(plan=asdict(p),effect=asdict(s.effect),energy=s.energy,latency=s.latency)for s,p in conditional]
    report['all_external_reservations_frontier_equal']=True
    # Every integer capacity around each attainable peak, not just two budgets.
    capacities={None,128*1024,132*1024}
    for r in records:
        capacities.update((r['peak']-1,r['peak'],r['peak']+1))
    for capacity in sorted(capacities,key=lambda v:-1 if v is None else v):
        a,_=flat(family,capacity);b,_=eliminate(family,capacity)
        c,_=flat(family,capacity,cache_factors=True);d,_=eliminate(family,capacity,reverse=True)
        expected=independent_frontier(records,capacity)
        reused={s.vector for s,_ in compiled if capacity is None or s.peak<=capacity}
        assert result_vectors(a)==result_vectors(b)==result_vectors(c)==result_vectors(d)==reused==expected
        report['frontier_checks'].append(dict(capacity_bytes=capacity,frontier_size=len(expected),equal=True))
    report['complete_frontier']=[dict(plan=asdict(p),peak=s.peak,energy=s.energy,latency=s.latency)for s,p in compiled]
    with gzip.open(args.output/'event_records.json.gz','wt')as file:
        json.dump(records,file,default=json_default,allow_nan=False)
    save()
    if args.native:
        from .native_check import check
        started=time.perf_counter(); native=[]
        for idx,r in enumerate(records,1):
            from .model import Plan
            plan=Plan(r['plan']['stripe'],tuple(tuple(t)for t in r['plan']['tiles']))
            observed=check(plan)
            assert observed['feasible'] and len(observed['phases'])==3
            assert observed['globalbuffer_peak_bits']==r['peak']*8
            assert math.isclose(observed['energy_j'],r['energy']*1e-15,rel_tol=1e-12)
            assert math.isclose(observed['latency_s'],float(r['latency'])*1e-9,rel_tol=1e-12)
            actions=[]
            for phase,reference in zip(observed['phases'],r['phases']):
                actual=native_actions(phase)
                assert actual=={k:reference[k]for k in actual}
                actions.append(actual)
            native.append(dict(plan=r['plan'],mapping_id=observed['mapping_id'],peak_bytes=observed['globalbuffer_peak_bits']//8,
                energy_j=observed['energy_j'],latency_s=observed['latency_s'],phase_actions=actions,
                phase_energy_j=[p['energy_j']for p in observed['phases']],
                phase_latency_s=[p['latency_s']for p in observed['phases']]))
            if idx%32==0:
                print(json.dumps(dict(native_validated=idx,total=len(records))),flush=True)
        report['native_fixed_validation']=dict(plans=len(native),numeric_phase_models=sum(len(r['phase_actions'])for r in native),
            seconds=time.perf_counter()-started,all_actions_peaks_costs_match=True,
            timing_scope='fixed evaluation plus observation, conversion, and assertions; not an uninstrumented FFM search benchmark')
        with gzip.open(args.output/'native_records.json.gz','wt')as file:
            json.dump(native,file,allow_nan=False)
    report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path(__file__).parent.glob('*.py'))}
    for path in ('research/symbolic_fusion/CONTRACT.md','examples/arches/nvdla.yaml',
                 'accelforge/model/_looptree/reuse/symbolic/symbolic.py'):
        report['source_sha256'][path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    report['status']='complete';save()
    print(json.dumps(dict(status='complete',full_plans=len(records),frontier=len(compiled),capacity_queries=len(capacities),native=args.native)))


if __name__=='__main__':
    main()
