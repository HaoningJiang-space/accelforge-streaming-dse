"""Bounded local symmetry recovery after asymmetric predecessors complete."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import sys
import time

from .fork_order_oracle import replay_private_boundary
from .graph.branch_symmetry import BranchOrderOracle, unequal_prefix_graph, induced


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--revision',required=True);args=p.parse_args()
    if args.out.exists():p.error('preserve the existing attempt')
    if sys.platform!='linux':p.error('Linux worker required')
    resource.setrlimit(resource.RLIMIT_AS,(2**30,2**30))
    def timeout(*_):raise TimeoutError('search plus replay limit')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(60)
    here=Path(__file__).parent
    record=dict(revision=args.revision,source_sha256={n:hashlib.sha256((here/n).read_bytes()).hexdigest() for n in (
        'probe_recovered_symmetry.py','graph/branch_symmetry.py','graph/curve.py','graph/model.py',
        'graph/span_names.py','graph/fork_quotient.py','fork_order_oracle.py','simulate_nest.py')},
        python=platform.python_version(),hash_seed=os.environ.get('PYTHONHASHSEED'),
        budgets=dict(seconds=60,mem_gib=1),status='running',queries=[])
    start=time.monotonic()
    try:
        graph=unequal_prefix_graph();sub=induced(graph,('H0','H1'))
        whole=BranchOrderOracle(graph,2);local=BranchOrderOracle(sub,2)
        record.update(original_graph={o:graph.access[o] for o in graph.ops},remaining_ops=sub.ops,
                      global_automorphisms=len(whole.automorphisms),local_automorphisms=len(local.automorphisms))
        for external in (('D0',),('D1',)):
            a=whole.query(sub.ops,external=external);b=local.query(external=external)
            record['queries'].append(dict(external=external,points=[list(p[:2]) for p in b],
                reference_points=[list(p[:2]) for p in a],equal=tuple(p[:2] for p in a)==tuple(p[:2] for p in b),
                witnesses=[asdict(p) for _,_,p in b],
                replays=[replay_private_boundary(sub,external,c,q,p) for c,q,p in b]))
        record.update(global_stats=whole.stats,local_stats=local.stats)
        valid=(len(whole.automorphisms)==1 and len(local.automorphisms)==2 and
               whole.stats['misses']==2 and local.stats['misses']==1 and
               record['queries'][0]['points']==record['queries'][1]['points'] and
               all(q['equal'] and all(r['exact'] for r in q['replays']) for q in record['queries']))
        record['status']='complete' if valid else 'invalid'
    except Exception as exc:
        record.update(status='timeout' if isinstance(exc,TimeoutError) else 'error',error=f'{type(exc).__name__}: {exc}')
    finally:signal.alarm(0)
    record.update(seconds=time.monotonic()-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    args.out.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:record.get(k) for k in ('status','global_automorphisms','local_automorphisms','global_stats','local_stats','seconds')}))
    return int(record['status']!='complete')


if __name__=='__main__':raise SystemExit(main())
