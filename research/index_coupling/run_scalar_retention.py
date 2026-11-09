"""Frozen proof checks and quality regressions, to run on the experiment server."""
import argparse
from bisect import bisect_right
from collections import Counter
import json
from multiprocessing import Pool
from pathlib import Path
import statistics
import subprocess
from time import perf_counter

from .constructive_fork import Plan,frontier
from .tiled_fork import TiledPlan
from .scalar_retention import (ScalarPlan,candidates,representations,query,
                               compile_frontier,execute,widths)
from .validate_constructive import cap_worker,score,FRESH as OLD_FRESH
from .run_tiled_fork import build

ROOT=Path(__file__).parent
NEW=((4,1,16,2),(16,1,4,8),(32,1,32,2),(64,1,64,4),
     (8,16,32,1),(32,16,8,1),(16,32,64,2),(64,4,16,1))
MODES=('reduced','full','reduced_scalar','full_scalar')


def emit(r): print(json.dumps(r,allow_nan=False),flush=True)


def all_shapes():
    out=set(NEW)|set(OLD_FRESH)
    for f in ('coupling_sweep.jsonl','coupling_sweep_heldout.jsonl'):
        out.update(tuple(json.loads(x)['shape']) for x in (ROOT/'results'/f).read_text().splitlines())
    return sorted(out)


def numeric(plans): return [[p.metrics()['peak'],p.metrics()['traffic']] for p in plans]


def brute(shape,cross,grid):
    return [p for axis,n in (('I',shape[0]),('K',shape[2]))
            for b in widths(n,grid) for p in representations(shape,cross,axis,b)]


def proof_case(shape):
    equality=queries=0; counts=[]
    for cross in (False,True):
        for axis,n in (('I',shape[0]),('K',shape[2])):
            for b in range(1,n+1):
                a,v,s=representations(shape,cross,axis,b)
                ma,mv,ms=a.metrics(),v.metrics(),s.metrics()
                assert all(ma[k]==mv[k]==ms[k] for k in ('traffic','reads','writes'))
                assert ms['peak']==(b+1)*(shape[1]+2*shape[3])+1
                equality+=1
        for grid in (False,True):
            raw=brute(shape,cross,grid); expected=numeric(frontier(raw))
            compiled,count=compile_frontier(shape,cross,grid)
            assert expected==numeric(compiled),(shape,cross,grid,expected,numeric(compiled))
            cs=[x[0] for x in expected]
            for cap in range(expected[-1][0]+2):
                q=query(shape,cross,cap,grid); idx=bisect_right(cs,cap)-1
                if idx<0: assert q is None
                else: assert [q.metrics()['peak'],q.metrics()['traffic']]==expected[idx],(shape,cross,cap,grid,q.record(),expected[idx])
                queries+=1
            counts.append(dict(cross=cross,all_integer=grid,raw=len(raw),compressed=count,frontier=len(compiled)))
    return dict(kind='proof_check',shape=shape,equalities=equality,queries=queries,counts=counts,passed=True)


def validate():
    shapes=((1,1,1,1),(2,3,4,5),(5,3,3,2),(4,4,4,4),(7,2,5,3),(3,5,7,2))
    count=steps=0
    for shape in shapes:
        for cross in (False,True):
            for p in candidates(shape,cross,True):
                actual=execute(p); expected=p.metrics()
                assert all(actual[k]==expected[k] for k in ('peak','traffic','reads','writes')),(p,expected,actual)
                count+=1; steps+=actual['steps']
    invalid=0
    for args in [((2,2,2,2),False,'I',0),((2,2,2,2),False,'I',3),
                 ((2,2,2,2),False,'J',1),((2,0,2,2),False,'I',1),
                 ((2,2,2,2),1,'I',1)]:
        try: ScalarPlan(*args)
        except ValueError: invalid+=1
        else: raise AssertionError('invalid plan accepted')
    original=ScalarPlan.metrics
    try:
        def forbidden(*args): raise AssertionError('executor called formula')
        ScalarPlan.metrics=forbidden
        execute(ScalarPlan((3,2,5,2),True,'K',3))
    finally: ScalarPlan.metrics=original
    emit(dict(kind='independent_validation',plans=count,steps=steps,invalid_rejected=invalid,metrics_poisoned=True,passed=True))
    for shape,axis,b,peak,traffic in (((16,2,64,4),'I',16,171,800),((64,4,64,8),'K',32,661,4352)):
        plan=ScalarPlan(shape,True,axis,b); a=execute(plan)
        assert (a['peak'],a['traffic'])==(peak,traffic)
        emit(dict(kind='calibration_execution',plan=plan.record(),execution=a))
    with Pool(4,initializer=cap_worker) as pool:
        for r in pool.imap_unordered(proof_case,all_shapes()): emit(r)


def family(shape,cross,mode):
    t=perf_counter()
    baseline='tiles_dual_retention' if mode.startswith('reduced') else 'tiles_scoped_retention'
    plans,_,count,_=build(shape,cross,False,baseline)
    if mode.endswith('_scalar'):
        extra=list(candidates(shape,cross)); count+=len(extra)
        plans=frontier(plans+extra)
    return plans,numeric(plans),count,perf_counter()-t


def measure(item):
    source,shape,cross,ref=item
    import resource
    used=resource.getrusage(resource.RUSAGE_SELF)
    resource.setrlimit(resource.RLIMIT_CPU,(int(used.ru_utime+used.ru_stime)+600,resource.RLIM_INFINITY))
    try:
        ref_times=[]
        if ref is None:
            from .curve_model import curve
            from .nest_model import coupling
            for _ in range(3):
                t=perf_counter(); pts=curve(coupling(*shape,cross)); ref_times.append(perf_counter()-t)
                now=[[c,q] for c,q,*_ in pts]
                if ref is not None: assert ref==now
                ref=now
        times={m:[] for m in MODES}; points={}; kept={}; counts={}
        for repeat in range(7):
            for mode in MODES[repeat%4:]+MODES[:repeat%4]:
                plans,pts,count,elapsed=family(shape,cross,mode)
                if mode in points: assert points[mode]==pts
                points[mode]=pts; kept[mode]=plans; counts[mode]=count; times[mode].append(elapsed)
        selected={}
        if source=='fresh':
            for mode in MODES[2:]:
                for p in kept[mode]:
                    if isinstance(p,ScalarPlan): selected[json.dumps(p.record(),sort_keys=True)]=p.record()
        return dict(kind='case',source=source,shape=shape,cross=cross,reference=ref,reference_samples=ref_times,
                    frontiers=points,candidates=counts,samples=times,medians={m:statistics.median(t) for m,t in times.items()},
                    scores={m:score(ref,points[m]) for m in MODES},selected=list(selected.values()))
    except Exception as exc:
        return dict(kind='error',source=source,shape=shape,cross=cross,error=repr(exc))


def run():
    old=[json.loads(x) for x in (ROOT/'results/constructive_heldout/cases.jsonl').read_text().splitlines()]
    items=[('regression',r['shape'],r['cross'],r['reference']) for r in old if r['kind']=='case']
    items += [('fresh',s,c,None) for s in NEW for c in (False,True)]
    emit(dict(kind='size',cases=len(items),fresh_shapes=NEW))
    with Pool(4,initializer=cap_worker,maxtasksperchild=1) as pool:
        for result in pool.imap_unordered(measure,items,chunksize=1): emit(result)


def replay(r):
    p=ScalarPlan(tuple(r['shape']),r['cross'],r['outer'],r['tile']); a=execute(p)
    assert all(a[k]==r[k] for k in ('peak','traffic','reads','writes'))
    return dict(kind='execution',plan=r,execution=a)


def audit(path):
    records=[json.loads(x) for x in path.read_text().splitlines()]
    chosen={json.dumps(p,sort_keys=True):p for r in records for p in r.get('selected',[])}
    emit(dict(kind='audit_size',plans=len(chosen)))
    with Pool(4,initializer=cap_worker) as pool:
        for r in pool.imap_unordered(replay,chosen.values()): emit(r)


def benchmark():
    # Exact same six-family grammar; cached lookup is allowed for both compilers.
    for shape in ((16,2,64,4),(64,4,64,8),(64,16,64,64),(64,1,64,4)):
        for cross in (False,True):
            nmax=max(shape[0],shape[2]); limit=compile_frontier(shape,cross)[0][-1].metrics()['peak']
            for nq in (1,8,64,512):
                caps=[1+(i+1)*limit//nq for i in range(nq)]
                timings={m:[] for m in ('brute_cached','compressed_cached','direct')}
                results={}
                modes=tuple(timings)
                for rep in range(9):
                    for mode in modes[rep%3:]+modes[:rep%3]:
                        t=perf_counter()
                        if mode=='direct':
                            out=[]
                            for cap in caps:
                                p=query(shape,cross,cap); out.append(None if p is None else (p.metrics()['peak'],p.metrics()['traffic']))
                        else:
                            plans=frontier(brute(shape,cross,True)) if mode=='brute_cached' else compile_frontier(shape,cross)[0]
                            pts=numeric(plans); cs=[x[0] for x in pts]; out=[]
                            for cap in caps:
                                idx=bisect_right(cs,cap)-1; out.append(None if idx<0 else tuple(pts[idx]))
                        timings[mode].append(perf_counter()-t); results[mode]=out
                assert all(x==results['direct'] for x in results.values())
                emit(dict(kind='benchmark',shape=shape,cross=cross,queries=nq,samples=timings,
                          medians={m:statistics.median(t) for m,t in timings.items()},all_equal=True))


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('validate','run','audit','benchmark'));p.add_argument('--input',type=Path)
    args=p.parse_args(); emit(dict(kind='metadata',mode=args.mode,
          commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
          tracked_dirty=bool(subprocess.check_output(['git','diff','--name-only','HEAD'],text=True)),
          server='designated experiment server'))
    if args.mode=='audit': audit(args.input)
    else: globals()[args.mode]()

if __name__=='__main__': main()
