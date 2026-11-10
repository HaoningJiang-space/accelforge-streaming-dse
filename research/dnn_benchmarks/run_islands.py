"""Bounded first-pass DNN-island study, not whole-DNN mapping or speed claims.

Prepare immutable inputs locally; run serialized resource IR on a CPU server.
Each child has its own wall-time and address-space bound. Profiled one-shot
times describe this screening experiment, not a controlled speedup benchmark.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time

from research.index_coupling.graph.model import Graph
from research.index_coupling.graph.curve import curve
from .c2 import make_c2_kernel
from .frontends import lower_island
from .replay import replay

ARMS={
    'v1_dp':dict(scalar_leaf='v1'),
    'v1_reuse':dict(scalar_leaf='v1',canonical_remainders=True,prune_infeasible_groups=True),
    'v2_dp':dict(scalar_leaf='v2'),
    'v2_reuse':dict(scalar_leaf='v2',canonical_remainders=True,prune_infeasible_groups=True),
    'v2_c2':dict(scalar_leaf='v2',c2=True),
    'v2_joint':dict(scalar_leaf='v2',canonical_remainders=True,prune_infeasible_groups=True,c2=True),
    'v2_oracle':dict(scalar_leaf='v2',partitions='enumerate'),
}


def write(path,obj):
    path=Path(path);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.replace(path)


def sources():
    root=Path(__file__).resolve().parents[1]
    names=['dnn_benchmarks/'+n for n in ('frontends.py','replay.py','c2.py','run_islands.py')]
    names+=['index_coupling/'+n for n in ('graph/curve.py','graph/remainder.py','graph/model.py','graph/span_names.py','simulate_nest.py')]
    return {n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}


def prepare(path):
    if path.exists():raise FileExistsError(path)
    base=Path(__file__).parent/'results/fx_inventory'
    inventories={m:json.loads((base/f'{m}.json').read_text()) for m in ('resnet50','vit_b_16','unet2015')}
    cases={}
    res=inventories['resnet50'];long=max(res['islands'],key=len)
    cases['resnet_short_reduced']=lower_island(res,long[:3],2)
    cases['resnet_long_reduced']=lower_island(res,long,2)
    for model,label in (('vit_b_16','vit_mlp'),('unet2015','unet_head')):
        inv=inventories[model];names=max(inv['islands'],key=len)
        for cap in (2,None):
            cases[label+('_reduced' if cap else '_original')]=lower_island(inv,names,cap)
    write(path,dict(schema='dnn-island-study.v1',cases=cases,
        inventory_sha256={m:hashlib.sha256((base/f'{m}.json').read_bytes()).hexdigest() for m in inventories},
        source_sha256=sources(),selection='first longest island; ResNet short uses its first 3 FX nodes',
        arms=ARMS,seconds=30,mem_gib=2,replay_step_limit=200000,
        contract='fixed order; exact halving grammar; no whole-model or timing-speedup claim'))


def worker(args,manifest):
    ir=manifest['cases'][args.case]
    options=dict(partitions='dp',**ARMS[args.arm]) if args.arm!='v2_oracle' else dict(ARMS[args.arm])
    c2=options.pop('c2',False);ledger={};stats={}
    setup=time.perf_counter();kernel=make_c2_kernel() if c2 else curve
    setup=time.perf_counter()-setup
    g=Graph(ir['sizes'],[(o,{t:tuple(ds) for t,ds in acc.items()}) for o,acc in ir['ops']])
    out=dict(case=args.case,arm=args.arm,options=options,c2=c2,stats=stats,c2_stats=ledger,
             status='running',phase='search',n_ops=len(g.ops),scalar_steps=ir['scalar_steps'],
             extent_cap=ir['extent_cap'],source_sha256=sources(),python=platform.python_version(),
             kernel_setup_seconds=setup)
    write(args.out,out)
    cap=int(manifest['mem_gib']*2**30)
    if sys.platform=='linux':resource.setrlimit(resource.RLIMIT_AS,(cap,cap))
    def timeout(*_):raise TimeoutError()
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,manifest['seconds'])
    begin=time.perf_counter()
    try:
        extra=dict(c2_stats=ledger) if c2 else {}
        points=kernel(g,witness=True,stats=stats,**options,**extra)
        out.update(search_seconds=time.perf_counter()-begin,phase='replay',points=[p[:2] for p in points],
                   byte_points=[(4*c,4*q) for c,q,_ in points],witnesses=points,replays=[])
        write(args.out,out)
        if ir['scalar_steps']>manifest['replay_step_limit']:
            out.update(status='search_complete_unreplayed',replay_reason='scalar execution exceeds declared step limit')
        else:
            for c,q,w in points:
                actual=replay(g,ir['semantics'],w,options['scalar_leaf'])
                out['replays'].append(dict(expected=[c,q],actual=actual,exact=actual['valid'] and (actual['peak'],actual['traffic'])==(c,q)))
            out['status']='complete' if all(x['exact'] for x in out['replays']) else 'invalid'
        out['phase']='finished'
    except TimeoutError:out['status']='timeout'
    except MemoryError:out['status']='memory'
    except Exception as e:out.update(status='error',error=f'{type(e).__name__}: {e}')
    finally:signal.setitimer(signal.ITIMER_REAL,0)
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out.update(seconds=time.perf_counter()-begin,peak_rss_bytes=rss if sys.platform=='darwin' else rss*1024)
    write(args.out,out)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--prepare',action='store_true')
    p.add_argument('--out',type=Path)
    p.add_argument('--worker',action='store_true')
    p.add_argument('--case');p.add_argument('--arm',choices=ARMS)
    args=p.parse_args()
    if args.prepare:prepare(args.manifest);return
    manifest=json.loads(args.manifest.read_text())
    if manifest['source_sha256']!=sources():raise ValueError('source changed after preparation')
    if args.worker:worker(args,manifest);return
    args.out.mkdir(parents=True,exist_ok=True)
    runs=[]
    for case,ir in manifest['cases'].items():
        for arm in ARMS:
            if arm=='v2_oracle' and (ir['extent_cap'] is None or len(ir['ops'])>6):continue
            path=args.out/f'{case}__{arm}.json'
            if not path.exists():
                command=[sys.executable,'-u','-m',__spec__.name,'--manifest',str(args.manifest),'--out',str(path),'--worker','--case',case,'--arm',arm]
                try:
                    child=subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                        env=dict(os.environ,PYTHONHASHSEED='0'),timeout=manifest['seconds']+10,text=True)
                    failed=dict(status='crashed',exitcode=child.returncode,stderr=child.stderr[-2000:])
                except subprocess.TimeoutExpired:failed=dict(status='hard_timeout')
                out=json.loads(path.read_text()) if path.exists() else dict(case=case,arm=arm)
                if out.get('status') in (None,'running'):out.update(failed);write(path,out)
            out=json.loads(path.read_text());runs.append(out)
            print(json.dumps({k:out.get(k) for k in ('case','arm','status','search_seconds','peak_rss_bytes')}),flush=True)
    write(args.out/'statuses.json',{f"{d['case']}__{d['arm']}":d['status'] for d in runs})
    if any(d['status'] in ('error','invalid','crashed') for d in runs):sys.exit(1)


if __name__=='__main__':main()
