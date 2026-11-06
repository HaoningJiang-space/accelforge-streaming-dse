"""Same-grammar test of ordinary grounded DP against universal effects."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import time
import tracemalloc
from .model import Family
from .eliminate import flat,eliminate
from .oracle import execute
from .experiment import independent_frontier,json_default,result_vectors


def path(mode):
    start=time.perf_counter();f=Family();built=time.perf_counter()
    result,stats=(flat(f,cache_factors=True) if mode=='cached_flat' else
                  eliminate(f,grounded=mode=='grounded'))
    compiled=time.perf_counter()
    # Every method precompiles its full numeric frontier once and reuses it.
    queries=[]
    for capacity in (90*1024,100*1024,116*1024,128*1024,132*1024):
        queries.append({s.vector for s,_ in result if s.peak<=capacity})
    end=time.perf_counter()
    return result,queries,stats,dict(construction_s=built-start,compile_s=compiled-built,
        query_s=end-compiled,total_s=end-start)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    modes=('cached_flat','grounded','universal');timings={m:[]for m in modes};stats={};memory={}
    for mode in modes:path(mode)
    rng=random.Random(20261106)
    for _ in range(9):
        order=list(modes);rng.shuffle(order)
        for mode in order:
            _,_,stats[mode],timing=path(mode);timings[mode].append(timing)
    for mode in modes:
        tracemalloc.start();path(mode);_,memory[mode]=tracemalloc.get_traced_memory();tracemalloc.stop()
    family=Family();records=[]
    for p in family.plans():records.append(dict(plan=asdict(p),**execute(family.n,p.stripe,p.tiles)))
    capacities={None,128*1024,132*1024}
    for r in records:capacities.update((r['peak']-1,r['peak'],r['peak']+1))
    for capacity in capacities:
        expected=independent_frontier(records,capacity)
        for mode in modes:
            result,_,_,_=path(mode)
            assert {s.vector for s,_ in result if capacity is None or s.peak<=capacity}==expected
        a,_=eliminate(family,capacity,grounded=True)
        b,_=eliminate(family,capacity,grounded=True,reverse=True)
        assert result_vectors(a)==result_vectors(b)==expected
    report=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        scope='A: original 192-plan GB grammar; no change to costs or generation; same factor cache and precompiled query reuse',
        modes=stats,timings=timings,medians={m:{k:statistics.median(t[k]for t in timings[m])for k in timings[m][0]}for m in modes},
        python_traced_peak_bytes=memory,oracle_plans=len(records),capacity_checks=len(capacities),all_frontiers_equal=True,
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in
                      [Path(__file__),Path(__file__).with_name('eliminate.py'),Path(__file__).with_name('model.py'),Path(__file__).with_name('oracle.py')]})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,default=json_default,indent=2)+'\n')
    print(json.dumps(dict(statistics=stats,medians=report['medians'])))


if __name__=='__main__':main()
