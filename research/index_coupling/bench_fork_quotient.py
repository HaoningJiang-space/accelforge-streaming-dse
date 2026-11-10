"""Isolate symmetry from the new partition recurrence; bounded fresh processes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

from .fork_order_oracle import replay_private_boundary
from .graph.curve import curve
from .graph.fork_quotient import ForkQuotient, Plan
from .run_fork_quotient import hashes, save


def cases():
    out = [dict(name=f'ablation_{r}{m}_{mode}', phase='ablation', m=m, mixed=r=='mixed', mode=mode)
           for m in (4,6) for r in ('same','mixed') for mode in ('quotient','labeled')]
    out += [dict(name=f'timing_{mode}_{i}', phase='timing', m=6, mixed=False, mode=mode)
            for i in range(3) for mode in ('fixed','quotient')]
    return out


def sources():
    return dict(hashes(), **{'bench_fork_quotient.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})


def worker(spec, args):
    if sys.platform!='linux':raise ValueError('Linux required')
    resource.setrlimit(resource.RLIMIT_AS,(6*2**30,6*2**30))
    m=spec['m'];roles='k'*(m//2)+'i'*(m//2) if spec['mixed'] else 'k'*m
    solver=ForkQuotient((2,2,2,2),roles,quotient=spec['mode']!='labeled')
    r=dict(spec=spec,revision=args.revision,source_sha256=sources(),hash_seed=os.environ.get('PYTHONHASHSEED'),
           budgets=dict(seconds=60,mem_gib=6),status='running')
    save(args.out,r)
    def timeout(*_):raise TimeoutError('search plus replay limit')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(60);start=time.monotonic()
    try:
        if spec['mode']=='fixed':
            points=tuple((c,q,Plan(solver.graph.ops,w)) for c,q,w in curve(solver.graph,partitions='dp',witness=True))
        else:points=solver.curve()
        r.update(search_seconds=time.monotonic()-start,points=[list(p[:2]) for p in points],
                 witnesses=[asdict(p) for _,_,p in points])
        r['replays']=[replay_private_boundary(solver.graph,(),c,q,p) for c,q,p in points]
        r['status']='complete' if all(c['exact'] for c in r['replays']) else 'invalid'
    except Exception as exc:
        r.update(status='timeout' if isinstance(exc,TimeoutError) else 'error',error=f'{type(exc).__name__}: {exc}')
    finally:signal.alarm(0)
    if spec['mode']!='fixed':
        solver.stats.update(**{f'{k}_cache':getattr(solver,k).cache_info()._asdict() for k in ('solve','group','sequence')})
        r['stats']=solver.stats
    r.update(seconds=time.monotonic()-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    save(args.out,r)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--revision',required=True);p.add_argument('--worker',type=int);args=p.parse_args();specs=cases()
    if args.worker is not None:worker(specs[args.worker],args);return
    args.out.mkdir(parents=True,exist_ok=False)
    save(args.out/'manifest.json',dict(specs=specs,revision=args.revision,source_sha256=sources(),
         hash_seed='0',ablation_workers=2,timing_workers=1,seconds=60,mem_gib=6))
    def run(i):
        path=args.out/f"{specs[i]['name']}.json"
        cmd=[sys.executable,'-m',__spec__.name,'--out',str(path),'--revision',args.revision,'--worker',str(i)]
        try:
            proc=subprocess.run(cmd,env=dict(os.environ,PYTHONHASHSEED='0'),capture_output=True,text=True,timeout=90)
            failure=dict(status='crash',exitcode=proc.returncode)
        except subprocess.TimeoutExpired:failure=dict(status='hard_timeout')
        r=json.loads(path.read_text()) if path.exists() else dict(spec=specs[i])
        if r.get('status') in (None,'running'):r.update(failure);save(path,r)
        print(json.dumps(dict(case=specs[i]['name'],status=r['status'],seconds=r.get('seconds'))),flush=True)
        return r
    with ThreadPoolExecutor(max_workers=2) as pool:records=list(pool.map(run,range(8)))
    records.extend(run(i) for i in range(8,len(specs)))
    save(args.out/'summary.json',dict(statuses={r['spec']['name']:r['status'] for r in records}))
    return int(any(r['status'] in ('error','invalid','crash') for r in records))


if __name__=='__main__':raise SystemExit(main())
