"""Frozen numeric-first / ordered-stream experiment, WORK_ATTRIBUTION section 7."""
import argparse
import json

from .bench_prefix import run, worker
from .bench_prefix_frames import CASES, graph

ARMS = ('native', 'prefix_frames', 'prefix_numeric', 'prefix_ordered')


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('run');r.add_argument('out');r.add_argument('--revision',required=True)
    w=sub.add_parser('worker');w.add_argument('case',choices=CASES);w.add_argument('arm',choices=ARMS)
    w.add_argument('--instrumented',action='store_true')
    a=p.parse_args()
    if a.command=='run':
        run(a.out,a.revision,cases=CASES,arms=ARMS,protocol_commit='56325880',
            worker_module=__spec__.name,rotate=True,
            extra_sources=('response/bench_prefix_frames.py','response/bench_prefix_numeric.py'))
    else:print(json.dumps(worker(a.case,a.arm,a.instrumented,graph(a.case))))


if __name__=='__main__':main()
