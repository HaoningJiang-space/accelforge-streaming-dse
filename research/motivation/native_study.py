"""Native FFM pilot: architecture selection under explicit materialization."""
import argparse
import copy
import json
import logging
import math
from pathlib import Path
from time import perf_counter

from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, mapping_structure


def run_point(case, shape, capacity, mode):
    if mode not in ('graph','zero_loops','materialized'):
        raise ValueError('unknown mode')
    spec=build(case,shape,capacity,common.EL)
    if mode in ('zero_loops','materialized'):
        spec.mapper.ffm.max_fused_loops=0
    if mode=='materialized':
        spec.arch.find('MainMemory').tensors.keep='All'
    start=perf_counter()
    result,stats=common.search(spec)
    elapsed=perf_counter()-start
    row=common.best_row(result.data)
    base=dict(shape=shape,capacity_bytes=capacity,mode=mode,seconds=elapsed,stats=stats)
    if row is None:
        return dict(**base,feasible=False)
    spec.mapping=copy.deepcopy(row['Total<SEP>mapping']())
    spec.model.metrics=common.RU | common.af.Metrics.ACTIONS
    spec.mapper.ffm.metrics=spec.model.metrics
    evaluated=common.evaluate_mapping(spec).data
    if len(evaluated)!=1:
        raise AssertionError('expected one replay result')
    ev=evaluated.iloc[0]
    if 'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right' not in evaluated:
        raise AssertionError('replay did not retain absolute GlobalBuffer reservations')
    energy,latency=(float(ev[k]) for k in ('Total<SEP>energy',common.LATENCY))
    for key in ('Total<SEP>energy',common.LATENCY):
        if not math.isclose(float(ev[key]),float(row[key]),rel_tol=1e-6):
            raise AssertionError(f'replay mismatch: {key}')
    for key in evaluated:
        if key.startswith('reservation_bits<SEP>'):
            bound=ev['capacity_reference_bits<SEP>'+key.split('<SEP>')[1]]
            if not 0<=ev[key]<=bound:
                raise AssertionError('capacity violation')
    actions={key:float(ev[key]) for key in evaluated if '<SEP>action<SEP>MainMemory<SEP>' in key}
    graph_replay=None
    if mode=='materialized':
        graph_spec=build(case,shape,capacity,common.EL)
        graph_spec.model.metrics=common.EL
        graph_spec.mapping=copy.deepcopy(spec.mapping)
        check=common.evaluate_mapping(graph_spec).data.iloc[0]
        graph_replay=all(math.isclose(float(check[k]),float(ev[k]),rel_tol=1e-6)
                         for k in ('Total<SEP>energy',common.LATENCY))
        if not graph_replay:
            raise AssertionError('materialized mapping changes score on graph target')
    return dict(**base,feasible=True,energy=energy,latency=latency,edp=energy*latency,
                dram_actions_bits=actions,mapping=mapping_structure(spec.mapping),
                materialized_replays_on_graph_target=graph_replay,
                reservations_bits={key:float(ev[key]) for key in evaluated if key.startswith('reservation_bits<SEP>')},
                frontier=[dict(energy=float(r['Total<SEP>energy']),latency=float(r[common.LATENCY]))
                          for _,r in result.data.iterrows()])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workload',default='matmuls',choices=('matmuls','glu','attention'))
    parser.add_argument('--params',default='2,4,8')
    parser.add_argument('--shapes',default='4x8')
    parser.add_argument('--capacities',default='96')
    parser.add_argument('--modes',default='graph,zero_loops,materialized')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    logging.getLogger().setLevel(logging.ERROR)
    case=common.Case.parse(args.workload,'nvdla',args.params)
    provenance=common.effective_config(case)
    common.set_jobs(1)
    shapes=[tuple(map(int,s.split('x'))) for s in args.shapes.split(',')]
    capacities=list(map(int,args.capacities.split(',')))
    report=dict(case=str(case),provenance=provenance,shapes=shapes,capacities=capacities,
                scope='Native fixed action prices; no physical area claim; reference over declared FFM grammar',points=[])
    for capacity in capacities:
        for shape in shapes:
            modes=args.modes.split(',')
            # Alternate mode order; timings still include within-process warm caches.
            if (capacities.index(capacity)*len(shapes)+shapes.index(shape))%2:
                modes=list(reversed(modes))
            for mode in modes:
                row=run_point(case,shape,capacity,mode)
                report['points'].append(row)
                report['peak_rss_gib']=common.peak_rss_gb()
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
                print(case,shape,capacity,mode,row.get('edp'),round(row['seconds'],3),flush=True)


if __name__=='__main__':
    main()
