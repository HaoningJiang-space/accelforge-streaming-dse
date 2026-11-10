"""Bounded continuation/state-orbit tests beyond terminal Fork consumers."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time

from .fork_order_oracle import replay_private_boundary
from .graph.branch_symmetry import BranchOrderOracle, branch_graph, continuation_states, induced


def specs():
    return [dict(name=f'{kind}_2_{"join" if join else "open"}',kind=kind,branches=2,join=join)
            for kind in ('suffix','root') for join in (False,True)] + [
        dict(name='asymmetric_2',kind='asymmetric',branches=2,join=False),
        dict(name='root_3_open',kind='probe',branches=3,join=False),
        dict(name='root_3_join',kind='probe',branches=3,join=True)]


def sources():
    root=Path(__file__).parent
    return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in (
        'run_branch_symmetry.py','graph/branch_symmetry.py','graph/curve.py','graph/model.py',
        'graph/span_names.py','graph/fork_quotient.py','fork_order_oracle.py','simulate_nest.py')}


def save(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)


def states(graph,spec):
    if spec['kind']=='suffix':return list(continuation_states(graph,spec['branches']))
    if spec['kind']=='probe':return [dict(ops=graph.ops,external=())]
    inputs=sorted((graph.consumed()-graph.produced())-{'A','B','X'})
    return [dict(ops=graph.ops,external=tuple(t for t,bit in zip(inputs,bits) if bit))
            for bits in product((False,True),repeat=len(inputs))]


def worker(spec,args):
    if sys.platform!='linux':raise ValueError('fresh Linux worker required')
    resource.setrlimit(resource.RLIMIT_AS,(6*2**30,6*2**30))
    graph=branch_graph(branches=spec['branches'],join=spec['join'],
                       tails=(True,False) if spec['kind']=='asymmetric' else None)
    solver=BranchOrderOracle(graph,spec['branches'])
    reference=BranchOrderOracle(graph,spec['branches'],quotient=False)
    queries=states(graph,spec)
    expected_orbits=len({solver.canonical(q['ops'],q['external'])[0] for q in queries})
    record=dict(spec=spec,revision=args.revision,source_sha256=sources(),python=platform.python_version(),
                hash_seed=os.environ.get('PYTHONHASHSEED'),budgets=dict(seconds=60,mem_gib=6),
                automorphisms=len(solver.automorphisms),expected_queries=len(queries),
                structural_orbits=expected_orbits,literal_reference=spec['kind']!='probe',
                queries=[],status='running',stage='search',failures=[])
    save(args.out,record)
    def timeout(*_):raise TimeoutError('search plus replay limit')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(60);start=time.monotonic()
    try:
        for query in queries:
            begin=time.monotonic()
            points=solver.query(query['ops'],external=query['external'])
            row=dict(**query,points=[list(p[:2]) for p in points],witnesses=[asdict(p) for _,_,p in points])
            if record['literal_reference']:
                expected=reference.query(query['ops'],external=query['external'])
                row.update(reference_points=[list(p[:2]) for p in expected],
                           equal=tuple(p[:2] for p in expected)==tuple(p[:2] for p in points))
            else:row['equal']=None
            sub=induced(graph,query['ops'])
            row['replays']=[replay_private_boundary(sub,query['external'],c,q,p) for c,q,p in points]
            row['seconds']=time.monotonic()-begin
            record['queries'].append(row)
            if row['equal'] is False or not all(r['exact'] for r in row['replays']):
                record['failures'].append(len(record['queries'])-1)
            # Preserve all completed queries even if a later one reaches the limit.
            save(args.out,record)
        if len(solver.cache)!=expected_orbits:record['failures'].append('orbit count')
        record.update(status='invalid' if record['failures'] else 'complete',stage='done')
    except Exception as exc:
        record.update(status='timeout' if isinstance(exc,TimeoutError) else
                      'memory' if isinstance(exc,MemoryError) else 'error',error=f'{type(exc).__name__}: {exc}')
    finally:signal.alarm(0)
    record.update(stats=solver.stats,reference_stats=reference.stats,cache_entries=len(solver.cache),
                  seconds=time.monotonic()-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    save(args.out,record)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--revision',required=True);p.add_argument('--worker',type=int);args=p.parse_args();cases=specs()
    if args.worker is not None:worker(cases[args.worker],args);return
    args.out.mkdir(parents=True,exist_ok=False)
    save(args.out/'manifest.json',dict(specs=cases,revision=args.revision,source_sha256=sources(),
                                     seconds=60,mem_gib=6,workers=4,hash_seed='0'))
    def run(i):
        path=args.out/f"{cases[i]['name']}.json"
        cmd=[sys.executable,'-m',__spec__.name,'--out',str(path),'--revision',args.revision,'--worker',str(i)]
        try:
            proc=subprocess.run(cmd,env=dict(os.environ,PYTHONHASHSEED='0'),capture_output=True,text=True,timeout=90)
            failure=dict(status='crash',exitcode=proc.returncode)
        except subprocess.TimeoutExpired:failure=dict(status='hard_timeout')
        r=json.loads(path.read_text()) if path.exists() else dict(spec=cases[i])
        if r.get('status') in (None,'running'):r.update(failure);save(path,r)
        return r
    records=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(run,i) for i in range(len(cases))]):
            r=f.result();records.append(r)
            print(json.dumps(dict(case=r['spec']['name'],status=r['status'],queries=len(r.get('queries',[])),seconds=r.get('seconds'))),flush=True)
    save(args.out/'summary.json',dict(statuses={r['spec']['name']:r['status'] for r in records}))
    return int(any(r['status']!='complete' for r in records))


if __name__=='__main__':raise SystemExit(main())
