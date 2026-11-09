"""Frozen held-out quality/cost validation; no constructor changes."""
import argparse
from collections import Counter
import hashlib
import json
from multiprocessing import Pool
from pathlib import Path
import resource
import signal
import statistics
import subprocess
from time import perf_counter

from .constructive_fork import Plan, execute as execute_strip
from .tiled_fork import TiledPlan, execute as execute_tile
from .run_tiled_fork import build, at, needed
from .nest_model import coupling, ffn

MODES = ('strips', 'tiles_dual_retention', 'tiles_scoped_retention')
FRESH = ((2,2,8,4),(8,2,2,16),(16,2,16,8),(32,2,32,4),
         (64,2,64,8),(8,2,32,16),(32,2,8,16),(16,2,64,4))
ROOT = Path(__file__).parent


def emit(record):
    print(json.dumps(record, allow_nan=False), flush=True)


def score(ref, actual):
    lo, hi = ref[0][0], ref[-1][0]
    caps = sorted({lo, hi} | {c for c,q in ref+actual if lo <= c <= hi})
    counts, intervals, rows = Counter(), Counter(), []
    worst = (0, lo)
    for idx, c in enumerate(caps):
        r, v = at(ref,c), at(actual,c)
        width = (caps[idx+1] if idx+1<len(caps) else hi+1)-c
        status = 'uncovered' if v is None else 'equal' if v==r else 'better' if v<r else 'worse'
        counts[status] += 1; intervals[status] += width
        if v is not None:
            loss = v/r-1
            if loss <= .05+1e-12: intervals['within5'] += width
            if loss <= .10+1e-12: intervals['within10'] += width
            worst = max(worst, (loss,c))
        rows.append([c,r,v,width])
    targets=sorted({q for c,q in ref+actual})
    inverse=[]
    for q in targets:
        r,v=needed(ref,q),needed(actual,q)
        if r is not None: inverse.append([q,r,v])
    return dict(knot_counts=dict(counts),integer_counts=dict(intervals),
                integer_budgets=hi-lo+1,comparisons=rows,inverse=inverse,
                worst_traffic_excess=worst[0],worst_capacity=worst[1])


def cap_worker():
    resource.setrlimit(resource.RLIMIT_AS, (12*1024**3,12*1024**3))
    def timeout(signum, frame):
        raise TimeoutError("600-second task CPU limit")
    signal.signal(signal.SIGXCPU, timeout)
    # CPU limits are set per fresh task below (cumulative process CPU).


def evaluate(item):
    source, shape, cross, reference = item
    try:
        used=resource.getrusage(resource.RUSAGE_SELF)
        soft=int(used.ru_utime+used.ru_stime)+600
        resource.setrlimit(resource.RLIMIT_CPU,(soft,resource.RLIM_INFINITY))
        ref_samples=[]
        if reference is None:
            from .curve_model import curve
            for _ in range(3):
                t=perf_counter(); points=curve(coupling(*shape,cross)); ref_samples.append(perf_counter()-t)
                result=[[c,q] for c,q,*_ in points]
                if reference is not None: assert reference==result
                reference=result
        timings={m:[] for m in MODES}; plans={}; frontiers={}; counts={}
        for repeat in range(7):
            for mode in MODES[repeat%3:]+MODES[:repeat%3]:
                p, pts, count, elapsed=build(shape,cross,False,mode)
                pts=[list(x) for x in pts]
                if mode in frontiers: assert frontiers[mode]==pts
                plans[mode],frontiers[mode],counts[mode]=p,pts,count
                timings[mode].append(elapsed)
        scores={m:score(reference,frontiers[m]) for m in MODES}
        selected={}
        if source=='fresh':
            for m in MODES[1:]:
                c=scores[m]['worst_capacity']
                eligible=[p for p in plans[m] if p.metrics()['peak']<=c]
                witnesses=[plans[m][0],plans[m][-1]]
                if eligible: witnesses.append(min(eligible,key=lambda p:p.metrics()['traffic']))
                for p in witnesses:
                    key=json.dumps(p.record(),sort_keys=True)
                    selected.setdefault(key,dict(plan=p.record(),reasons=[]))['reasons'].append(m)
        return dict(kind='case',source=source,shape=shape,cross=cross,
                    reference=reference,reference_samples=ref_samples,
                    samples=timings,medians={m:statistics.median(t) for m,t in timings.items()},
                    candidates=counts,frontiers=frontiers,scores=scores,
                    selected=list(selected.values()))
    except Exception as exc:
        return dict(kind='error',source=source,shape=shape,cross=cross,error=repr(exc))


def run_cases():
    archived=[json.loads(x) for x in (ROOT/'results/coupling_sweep_heldout.jsonl').read_text().splitlines()]
    items=[('archived',r['shape'],cross,r[('cross' if cross else 'same')+'_wt'])
           for r in archived for cross in (False,True)]
    items += [('fresh',shape,cross,None) for shape in FRESH for cross in (False,True)]
    emit(dict(kind='size',cases=len(items),fresh_shapes=FRESH))
    with Pool(4,initializer=cap_worker,maxtasksperchild=1) as pool:
        for result in pool.imap_unordered(evaluate,items,chunksize=1): emit(result)


def replay(item):
    p=item['plan']; shape=tuple(p['shape'])
    plan=(TiledPlan(shape,p['cross'],p['outer'],p['rows'],p['cols'],tuple(p['kept']))
          if p['kind']=='two_dimensional' else
          Plan(shape,p['cross'],p['kind'],p['tile'],tuple(p['kept']),p['producer_axis']))
    actual=(execute_tile if isinstance(plan,TiledPlan) else execute_strip)(plan)
    assert all(actual[k]==p[k] for k in ('peak','traffic','reads','writes'))
    return dict(kind='execution',**item,execution=actual)


def audit(path):
    chosen={}
    for line in path.read_text().splitlines():
        r=json.loads(line)
        for item in r.get('selected',[]): chosen[json.dumps(item['plan'],sort_keys=True)]=item
    emit(dict(kind='audit_size',plans=len(chosen),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    with Pool(4,initializer=cap_worker) as pool:
        for result in pool.imap_unordered(replay,chosen.values()): emit(result)


def ffn_contract():
    g=ffn(8,4,8); producers={list(g.access[o])[-1]:o for o in g.ops}
    users={t:[o for o in g.ops if t in list(g.access[o])[:-1]] for t in g.tensors(g.ops)}
    def matmul(op):
        if op is None: return False
        ds=list(g.access[op].values())
        return (len(ds)==3 and all(len(d)==2 for d in ds)
                and len(set(ds[0]) & set(ds[1]) - set(ds[2]))==1
                and len(set().union(*map(set,ds)))==3)
    rows=[]
    for t,cs in sorted(users.items()):
        if len(cs)<2: continue
        prod=producers.get(t)
        reasons=[]
        if prod is None: reasons.append('external input, no producer')
        elif not matmul(prod): reasons.append('producer is not a two-input contraction')
        if len(cs)!=2: reasons.append('not exactly two consumers')
        if not all(matmul(c) for c in cs): reasons.append('consumer is not a two-input contraction')
        rows.append(dict(tensor=t,producer=prod,consumers=cs,reasons=reasons,
                         passes_necessary_contract=not reasons))
    emit(dict(kind='ffn_contract',rows=rows,note='Necessary gate only; passing would still require closure/shape matching.'))


def existing_ffn(path):
    parts={}; failures=[]; hashes={}
    for p in sorted(path.glob('part_*.json')):
        data=p.read_bytes(); hashes[p.name]=hashlib.sha256(data).hexdigest()
        if not data:
            err=p.with_suffix('.err')
            txt=err.read_text() if err.exists() else ''
            failures.append(dict(file=p.name,last_error=txt.splitlines()[-1] if txt else 'no log'))
        else:
            r=json.loads(data); parts[r['part']]=r
    baseline=next(json.loads(x)['frontier'] for x in (ROOT/'results/upstream_nodetail.jsonl').read_text().splitlines()
                  if json.loads(x)['case']=='ffn_full_copy')
    ffm={c:min(t for cc,t in baseline if cc==c) for c,t in baseline}
    comparisons=[[c,t,at(parts['graph']['points'],c),at(parts['nowt']['points'],c)] for c,t in sorted(ffm.items())]
    emit(dict(kind='existing_ffn',source_commit='b733c03e',source_dirty_file='accelforge/_version.py',
              hashes=hashes,parts=parts,failures=failures,comparisons=comparisons,
              p12_pass=all(row[3]>=row[1] for row in comparisons),p14_ffn='incomplete'))


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('mode',choices=('run','audit','ffn_contract','existing_ffn'))
    parser.add_argument('--input',type=Path); args=parser.parse_args()
    emit(dict(kind='metadata',mode=args.mode,
              commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              tracked_dirty=bool(subprocess.check_output(['git','diff','--name-only','HEAD'],text=True)),
              server='designated experiment server'))
    if args.mode=='run': run_cases()
    elif args.mode=='audit': audit(args.input)
    elif args.mode=='existing_ffn': existing_ffn(args.input)
    else: ffn_contract()

if __name__=='__main__': main()
