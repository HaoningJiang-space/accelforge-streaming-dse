"""Native Snowcat envelope and frozen prediction evaluation, one case per worker."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import mapping_structure
from accelforge.mapper.FFM._make_pmappings.make_pmappings import get_per_tensor_size
from research.structure_prediction.predict import boundaries, predictions, evaluate

ROOT=Path(__file__).parent
E='Total<SEP>energy'
R='reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'
METRICS=common.af.Metrics.ENERGY | common.af.Metrics.RESOURCE_USAGE
CASES={
    'cal_mm2_4_4':('matmuls',dict(N_EINSUMS=2,M=4,KN=4),{}),
    'held_mm2_2_8':('matmuls',dict(N_EINSUMS=2,M=2,KN=8),{}),
    'held_mm2_8_4':('matmuls',dict(N_EINSUMS=2,M=8,KN=4),{}),
    'held_mm3_4_4':('matmuls',dict(N_EINSUMS=3,M=4,KN=4),{}),
    'held_glu_2_4_4':('glu',dict(M=2,G=4,C=4),{}),
    'held_attention_4_1_4':('attention',dict(N_TOKENS=4,N_HEADS=1,D_HEAD=4),{}),
    'scaled_gpt':('gpt',dict(N_TOKENS=2),dict(D=4,G=4,J=4,H=1,E=4,F=4,C=16)),
    'scaled_mobilenet':('mobilenet',dict(BATCH_SIZE=1),dict(P0=4,Q0=4,P1=4,Q1=4,P2=4,Q2=4,N0=4,N1=4,N2=4,T0=8,T1=8)),
    'original_mobilenet':('mobilenet',dict(BATCH_SIZE=1),{}),
    'original_gpt_tokens2':('gpt',dict(N_TOKENS=2),{}),
}


def build(name):
    workload,params,overrides=CASES[name]
    path=common.ROOT/('examples/workloads/gpt3_6.7B.yaml' if workload=='gpt' else common.WORKLOADS[workload][0])
    spec=common.af.Spec.from_yaml(ROOT/'snowcat.yaml',path,jinja_parse_data=params)
    spec.workload.rank_sizes.update(overrides)
    sizes={str(t):int(n) for t,n in get_per_tensor_size(spec).items()}
    # Registered workloads all declare All:8 and one instance: elements == bytes.
    if dict(spec.workload.bits_per_value)!={'All':8} or spec.workload.n_instances!=1:
        raise ValueError('v1 requires INT8 and one workload instance')
    spec.arch.find('GlobalBuffer').size=sum(sizes.values())*8
    spec.mapper.ffm.metrics=spec.model.metrics=METRICS
    return spec,sizes,dict(workload_path=path.relative_to(common.ROOT).as_posix(),parameters=params,
                           rank_overrides=overrides,workload_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def envelope(spec,materialized=False,failure_path=None):
    spec=copy.deepcopy(spec)
    copy_only=all(e.is_copy_operation for e in spec.workload.einsums)
    if materialized:
        spec.arch.find('MainMemory').tensors.keep='All'
        spec.mapper.ffm.max_fused_loops=0
    start=perf_counter()
    result,stats=common.search(spec,gen_env={'AF_GENERATION_VARIABLE_RESOURCES':'GlobalBuffer'},
                               join_env=None if copy_only else {'AF_VARIABLE_RESOURCES':'GlobalBuffer'})
    search_s=perf_counter()-start
    if R not in result.data and copy_only:
        result.data[R]=0
    if result.data.empty or R not in result.data:
        raise ValueError('no complete reference frontier')
    retained=[]
    best=math.inf
    for _,row in result.data.sort_values([R,E]).iterrows():
        if float(row[E])>=best-1e-9:
            continue
        best=float(row[E])
        retained.append(row)
    points=[]
    start=perf_counter()
    for row in retained:
        cap=int(row[R])
        if cap!=row[R] or cap%8:
            raise ValueError('require integral byte footprints')
        replay=copy.deepcopy(spec)
        replay.arch.find('GlobalBuffer').size=cap
        replay.mapping=copy.deepcopy(row['Total<SEP>mapping']())
        replay.model.metrics=replay.mapper.ffm.metrics=METRICS | common.af.Metrics.ACTIONS
        ev=common.evaluate_mapping(replay).data
        # Copy-containing graphs can replay with lifetime -1 rather than 0.
        # Check all absolute buffer reservations, not one lifetime's label.
        resource_columns=[c for c in ev if c.startswith('reservation_bits<SEP>GlobalBuffer<SEP>')]
        if len(ev)==1 and resource_columns:
            values=[float(ev[c].iloc[0]) for c in resource_columns]
            if any(not math.isfinite(v) or v!=int(v) or not 0<=v<=cap for v in values):
                raise AssertionError(f'invalid replay reservations at {cap} bits: {values}')
            ev[R]=max(values)
        if R not in ev and copy_only:
            ev[R]=0
        if len(ev)!=1 or R not in ev:
            if failure_path is not None:
                replay.arch.find('GlobalBuffer').size=spec.arch.find('GlobalBuffer').size
                full=common.evaluate_mapping(replay).data
                def snapshot(frame):
                    return dict(rows=len(frame),columns=list(frame.columns),
                                energy=[float(v) for v in frame[E]] if E in frame else None,
                                reservation_bits=[float(v) for v in frame[R]] if R in frame else None)
                save(failure_path,dict(reported_capacity_bits=cap,reported_traffic_bits=float(row[E]),
                                      target_replay=snapshot(ev),envelope_replay=snapshot(full),
                                      mapping=mapping_structure(replay.mapping)))
            raise AssertionError(f'missing replay capacity witness: rows={len(ev)}, capacity_bits={cap}, has_R={R in ev}')
        ev=ev.iloc[0]
        actions={c:float(ev[c]) for c in ev.index if '<SEP>action<SEP>MainMemory<SEP>' in c}
        if not math.isclose(sum(actions.values()),float(ev[E]),rel_tol=1e-9):
            raise AssertionError('unit-cost objective does not equal backing-store bits')
        if not math.isclose(float(ev[E]),float(row[E]),rel_tol=1e-9) or int(ev[R])>cap:
            raise AssertionError('mapping replay changes traffic or exceeds capacity')
        points.append(dict(capacity_bytes=cap//8,traffic_bytes=float(ev[E])/8,
                           dram_actions_bits=actions,mapping=mapping_structure(replay.mapping)))
    return dict(points=points,search_seconds=search_s,replay_seconds=perf_counter()-start,stats=stats)


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    tmp.replace(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case',choices=CASES)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    common.set_jobs(1)
    spec,sizes,source=build(args.case)
    ops=[dict(name=str(e.name),inputs=sorted(map(str,e.input_tensor_names)),outputs=sorted(map(str,e.output_tensor_names)))
         for e in spec.workload.einsums]
    border=boundaries(ops,sizes)
    report=dict(case=args.case,phase='structure',source=source,tensor_bytes=sizes,operators=ops,boundaries=border,
                envelope_bytes=sum(sizes.values()),predictions=predictions(border),
                protocol_sha256=hashlib.sha256((ROOT/'PROTOCOL.md').read_bytes()).hexdigest(),local_curves=[])
    save(args.output,report)
    for e in spec.workload.einsums:
        isolated=copy.deepcopy(spec)
        payload=isolated.workload.model_dump()
        payload['einsums']=[e.model_dump()]
        isolated.workload=type(isolated.workload).model_validate(payload)
        # These aliases refer to graph-global Inputs/Intermediates. Snowcat uses
        # no input/weight/output aliases, so remove them for isolated operators.
        isolated.renames=type(isolated.renames)()
        for op in isolated.workload.einsums:
            op.renames=type(op.renames)()
        local=envelope(isolated)
        report['local_curves'].append(dict(op=str(e.name),**local))
        report['phase']='local_frontiers'
        save(args.output,report)
    report['predictions']=predictions(border,[c['points'] for c in report['local_curves']])
    frozen=json.dumps(report['predictions'],sort_keys=True,separators=(',',':'))
    report['prediction_sha256']=hashlib.sha256(frozen.encode()).hexdigest()
    report['phase']='predictions_frozen_before_graph_search'
    save(args.output.with_name(args.output.stem+'_predictions.json'),report)
    save(args.output,report)
    report['graph']=envelope(spec,failure_path=args.output.with_name(args.output.stem+'_replay_failure.json'))
    report['phase']='graph_complete'
    save(args.output,report)
    report['materialized']=envelope(spec,True)
    report['evaluation']=evaluate(report['predictions'],report['graph']['points'])
    def at(curve,c):
        return min((p['traffic_bytes'] for p in curve if p['capacity_bytes']<=c),default=math.inf)
    capacities=sorted({p['capacity_bytes'] for key in ('graph','materialized') for p in report[key]['points']})
    report['first_measured_fusion_benefit_bytes']=next((c for c in capacities
        if math.isfinite(at(report['materialized']['points'],c))
        and at(report['graph']['points'],c)<at(report['materialized']['points'],c)-1e-9),None)
    report['phase']='complete'
    report['peak_rss_gib']=common.peak_rss_gb()
    save(args.output,report)
    print(args.case,[(p['capacity_bytes'],p['traffic_bytes']) for p in report['graph']['points']],flush=True)


if __name__=='__main__':
    main()
