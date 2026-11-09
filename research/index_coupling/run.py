"""Native Snowcat capacity-traffic frontiers for same- versus cross-index consumers of X."""
import argparse
import json
from pathlib import Path

from research.tracking_audit import common
from research.structure_prediction.experiment import METRICS, ROOT as SP_ROOT, envelope, save
from accelforge.mapper.FFM._make_pmappings.make_pmappings import get_per_tensor_size

ROOT=Path(__file__).parent


def build(n,cross,join,dims=None):
    spec=common.af.Spec.from_yaml(SP_ROOT/'snowcat.yaml',ROOT/'coupling.yaml',
                                  jinja_parse_data=dict(N=n,CROSS=cross,JOIN=join,**(dims or {})))
    sizes={str(t):int(v) for t,v in get_per_tensor_size(spec).items()}
    spec.arch.find('GlobalBuffer').size=sum(sizes.values())*8
    spec.mapper.ffm.metrics=spec.model.metrics=METRICS
    return spec,sizes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n',type=int,required=True)
    parser.add_argument('--dims',default='',help='rectangular sizes, e.g. NI=64,NJ=8,NK=8,NL=8')
    parser.add_argument('--cross',action='store_true')
    parser.add_argument('--no-join',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    common.set_jobs(1)
    dims={k:int(v) for k,v in (x.split('=') for x in args.dims.split(',') if x)}
    if set(dims)-{'NI','NJ','NK','NL'}:
        parser.error('dims keys must be NI, NJ, NK, NL')
    spec,sizes=build(args.n,args.cross,not args.no_join,dims)
    report=dict(n=args.n,dims=dims,cross=args.cross,join=not args.no_join,tensor_bytes=sizes,phase='built')
    save(args.output,report)
    report['graph']=envelope(spec)
    report['phase']='graph_complete'
    save(args.output,report)
    report['materialized']=envelope(spec,True)
    report['phase']='complete'
    report['peak_rss_gib']=common.peak_rss_gb()
    save(args.output,report)
    print(args.output.name,[(p['capacity_bytes'],p['traffic_bytes']) for p in report['graph']['points']],flush=True)


if __name__=='__main__':
    main()
