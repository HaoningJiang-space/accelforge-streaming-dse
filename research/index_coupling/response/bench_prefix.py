"""Frozen full-root prefix-sharing experiment; fresh processes, native witnesses.

python -m research.index_coupling.response.bench_prefix run NEW_DIRECTORY
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time

from ..census_tools import graph_of
from ..graph.curve import curve
from ..simulate_nest import simulate
from .prefix import make_kernel
from .substitution import make_exact_kernel, expand, frontier_of

CASES=('ffn_forward_l1_m8','ffn_forward_l2_m8','ffn_forward_l4','fork_kki')
ARMS=('native','prefix_raw','prefix_shared','unit','unit_prefix')
OPTIONS=dict(partitions='dp',scalar_leaf='v2',witness=True)


def worker(case, arm, instrumented, graph=None):
    if sys.platform.startswith('linux'):
        resource.setrlimit(resource.RLIMIT_AS,(6*2**30,6*2**30))
    g=graph_of(case) if graph is None else graph
    start=time.perf_counter()
    if arm=='native':fn,registry=curve,{}
    elif arm=='unit':fn,registry=make_exact_kernel()
    else:fn,registry=make_kernel(projection=arm!='prefix_raw',unit=arm in ('unit_prefix','unit_frames'),
                                 frames=arm in ('prefix_frames','unit_frames'))
    installation=time.perf_counter()-start
    stats={} if instrumented else None
    start=time.perf_counter()
    points=fn(g,stats=stats,**OPTIONS)
    search=time.perf_counter()-start
    start=time.perf_counter();cache={}
    if arm in ('unit','unit_prefix','unit_frames'):
        points=tuple((c,q,expand(g,w,registry,cache)) for c,q,w in points)
    recovery=time.perf_counter()-start
    # RSS is sampled before replay, which expands numerical tensor cells.
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform=='darwin':rss/=1024
    start=time.perf_counter();replays=0
    for c,q,w in points:
        if any(note[0] not in ('groups','loop','hold') for note in w):
            raise AssertionError('unexpanded witness')
        actual=simulate(g,w,scalar_leaf='v2')
        if not actual['valid'] or (actual['peak'],actual['traffic'])!=(c,q):
            raise AssertionError((case,arm,c,q,actual))
        replays+=1
    return dict(case=case,arm=arm,instrumented=instrumented,status='complete',
                installation_seconds=installation,search_with_notes_seconds=search,
                recovery_seconds=recovery,generation_seconds=search+recovery,
                including_installation_seconds=installation+search+recovery,
                replay_seconds=time.perf_counter()-start,replayed_points=replays,
                points=[list(p[:2]) for p in points],peak_rss_kib=rss,
                witness_notes=sum(len(p[2]) for p in points),recovery_states=len(cache),
                stats=stats,unit_curve_cache=frontier_of.cache_info()._asdict())


def run(out,revision,*,cases=CASES,arms=ARMS,protocol_commit='e116c2a3',
        worker_module=None,extra_sources=()):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parent.parent
    files=[root/p for p in ('graph/curve.py','graph/model.py','graph/stacks.py',
          'response/prefix.py','response/bench_prefix.py','response/substitution.py',
          'response/chains.py','response/forms.py','simulate_nest.py','census_tools.py')]
    files.extend(root/p for p in extra_sources)
    manifest=dict(protocol_commit=protocol_commit,revision=revision,cases=cases,arms=arms,rounds=5,
                  timeout_seconds=60,memory_gib=6,python=platform.python_version(),
                  platform=platform.system(),hash_seed=0,
                  source_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                  scope='complete root generation; installation and replay separately reported; work runs instrumented')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for instrumented,rounds in ((False,range(5)),(True,range(1))):
        for round_id in rounds:
            for case in cases:
                for arm in (arms if round_id%2==0 else tuple(reversed(arms))):
                    name=f'{case}_{arm}_{"work" if instrumented else round_id}.json'
                    cmd=[sys.executable,'-m',worker_module or __spec__.name,'worker',case,arm]
                    if instrumented:cmd.append('--instrumented')
                    try:
                        proc=subprocess.run(cmd,env=dict(os.environ,PYTHONHASHSEED='0'),
                                            capture_output=True,text=True,timeout=60)
                        row=json.loads(proc.stdout) if proc.returncode==0 else dict(
                            status='error',case=case,arm=arm,error=proc.stderr[-3000:])
                    except subprocess.TimeoutExpired:
                        row=dict(status='timeout',case=case,arm=arm)
                    row.update(round=round_id,instrumented=instrumented)
                    (out/name).write_text(json.dumps(row,indent=2)+'\n')
                    print(name,row['status'],round(row.get('generation_seconds',0),4),flush=True)
    summary=summarize(out,cases=cases,arms=arms)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if not summary['all_equal_and_replayed']:raise SystemExit(1)


def summarize(out,*,cases=CASES,arms=ARMS):
    rows=[json.loads(p.read_text()) for p in Path(out).glob('*.json') if p.name not in ('manifest.json','summary.json')]
    result=dict(all_equal_and_replayed=True,total_replays=0,cases={})
    for case in cases:
        cr=[r for r in rows if r['case']==case]
        references=[r['points'] for r in cr if r['arm']=='native' and r['status']=='complete']
        if not references:
            result['all_equal_and_replayed']=False
            result['cases'][case]=dict(equal_and_replayed=False,error='no completed native reference')
            continue
        reference=references[0]
        okay=(len(cr)==len(arms)*6 and all(r['status']=='complete' and r['points']==reference
                   and r['replayed_points']==len(reference) for r in cr))
        result['all_equal_and_replayed'] &= okay
        result['total_replays']+=sum(r.get('replayed_points',0) for r in cr)
        report=dict(equal_and_replayed=okay,points=len(reference),arms={})
        for arm in arms:
            timed=[r for r in cr if r['arm']==arm and not r['instrumented'] and r['status']=='complete']
            work=[r for r in cr if r['arm']==arm and r['instrumented'] and r['status']=='complete']
            if not timed:continue
            report['arms'][arm]={k:statistics.median(r[k] for r in timed) for k in (
                'generation_seconds','search_with_notes_seconds','recovery_seconds','installation_seconds',
                'including_installation_seconds','replay_seconds','peak_rss_kib')}
            report['arms'][arm].update(rounds=len(timed),
                generation_range=[min(r['generation_seconds'] for r in timed),max(r['generation_seconds'] for r in timed)],
                work=work[0]['stats'] if work else None)
        native=report['arms']['native']['generation_seconds']
        for arm,arm_report in report['arms'].items():
            arm_report['speedup_vs_native']=native/arm_report['generation_seconds']
        result['cases'][case]=report
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('run');r.add_argument('out');r.add_argument('--revision',required=True)
    w=sub.add_parser('worker');w.add_argument('case',choices=CASES);w.add_argument('arm',choices=ARMS)
    w.add_argument('--instrumented',action='store_true')
    a=p.parse_args()
    if a.command=='run':run(a.out,a.revision)
    else:print(json.dumps(worker(a.case,a.arm,a.instrumented)))


if __name__=='__main__':main()
