"""Frozen P21d: topology-only cut audit and isolated exact curve jobs.

--prepare prints all held-out inputs and candidate reasons without solving.
--case N --arm structural|unrestricted --output FILE runs one bounded job.
Search completion is checkpointed before independent witness execution.
"""
import argparse
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import time

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import residual
from research.index_coupling.graph.structural_cuts import structural_cuts
from research.index_coupling.simulate_nest import simulate

CASES = tuple(product(((8,2,4),(4,8,2)), (4,6,12), (False,True)))


def audit(index):
    shape, depth, reads_x = CASES[index]
    graph = residual(*shape, depth, reads_x)
    return dict(case=index, shape=shape, depth=depth, reads_x=reads_x,
                n_ops=len(graph.ops), cut_rule=structural_cuts(graph))


def save(path, record):
    data = json.dumps(record, allow_nan=False)+'\n'
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(data)
    tmp.replace(path)


def limit(_signum, _frame):
    raise TimeoutError('frozen 600-second curve/replay limit')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--case',type=int,choices=range(len(CASES)))
    parser.add_argument('--arm',choices=('structural','unrestricted'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.prepare:
        print(json.dumps(dict(cases=[audit(i) for i in range(len(CASES))]),indent=2))
        return 0
    if args.case is None or args.arm is None or args.output is None:
        parser.error('--case, --arm and --output are required for a curve job')
    resource.setrlimit(resource.RLIMIT_AS,(8*2**30,8*2**30))
    signal.signal(signal.SIGALRM,limit)
    start=time.monotonic()
    spec=audit(args.case)
    revision=os.environ.get('P21D_SOURCE_REVISION') or subprocess.check_output(
        ['git','rev-parse','HEAD'],text=True).strip()
    record=dict(**spec,arm=args.arm,source_revision=revision,python=platform.python_version(),
                protocol_sha256=hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest(),
                status='running',stage='search',hash_seed=os.environ.get('PYTHONHASHSEED'),
                wall_limit_seconds=600,address_space_limit_gib=8)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    save(args.output,record)
    signal.alarm(600)
    try:
        graph=residual(*spec['shape'],spec['depth'],spec['reads_x'])
        options={'whole_span_cuts':spec['cut_rule']['positions']} if args.arm=='structural' else {}
        points=curve(graph,witness=True,**options)
        record.update(stage='replay',search_seconds=time.monotonic()-start,
                      points=points,replays=[])
        save(args.output,record)
        for c,q,w in points:
            actual=simulate(graph,w)
            exact=actual['valid'] and (actual['peak'],actual['traffic'])==(c,q)
            record['replays'].append(dict(capacity=c,traffic=q,exact=exact,actual=actual))
        record.update(status='complete' if all(x['exact'] for x in record['replays']) else 'invalid',stage='done')
    except Exception as exc:
        record.update(status='incomplete',error=f'{type(exc).__name__}: {exc}')
    signal.alarm(0)
    record.update(seconds=time.monotonic()-start,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    save(args.output,record)
    print(json.dumps({k:record[k] for k in ('case','arm','status','stage','seconds','peak_rss_kib')}),flush=True)
    return 0 if record['status']=='complete' else 1


if __name__=='__main__':
    raise SystemExit(main())
