"""Frozen parent-frame quotient continuation, WORK_ATTRIBUTION.md section 6."""
import argparse
import json

from ..census_tools import graph_of
from ..graph.stacks import ffn_stack
from .bench_prefix import run, worker

CASES=('ffn_forward_l1_m8','ffn_forward_l2_m8','ffn_forward_l4','fork_kki',
       'ffn_forward_l2_m16','ffn_forward_l3_m8')
ARMS=('native','prefix_shared','prefix_frames','unit','unit_frames')


def graph(case):
    if case=='ffn_forward_l2_m16':return ffn_stack(2,m=16,d=4,f=8)
    if case=='ffn_forward_l3_m8':return ffn_stack(3,m=8,d=4,f=8)
    return graph_of(case)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('run');r.add_argument('out');r.add_argument('--revision',required=True)
    w=sub.add_parser('worker');w.add_argument('case',choices=CASES);w.add_argument('arm',choices=ARMS)
    w.add_argument('--instrumented',action='store_true')
    a=p.parse_args()
    if a.command=='run':
        run(a.out,a.revision,cases=CASES,arms=ARMS,protocol_commit='10e5b381',
            worker_module=__spec__.name,extra_sources=('response/bench_prefix_frames.py',))
    else:print(json.dumps(worker(a.case,a.arm,a.instrumented,graph(a.case))))


if __name__=='__main__':main()
