"""Causal replay of six archived native 3mm mappings; no new search mechanism."""
import argparse
import ast
import copy
import hashlib
import importlib
import inspect
import json
import math
from pathlib import Path
from unittest.mock import patch

from accelforge.frontend import mapping as mp
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build,mapping_structure

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'research/graph_coopt/results/coupling/known_shape_reversal.json'
CASE=common.Case('matmuls','nvdla',(3,256,256))
METRICS=common.RU|common.af.Metrics.ACTIONS
RAW_GB='reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'


def restore(record):
    allowed={'Mapping','Nested','Sequential','Storage','Reservation','Temporal','Spatial','Compute'}
    fields={'component','tensors','rank_variable','tile_shape','initial_tile_shape','name',
            'einsum','purposes','resource','persistent','nodes','type'}
    if record['type'] not in allowed or set(record)-fields:
        raise ValueError('unknown archived mapping node or field')
    values={k:v for k,v in record.items()if k!='type'}
    for key in ('tensors','purposes'):
        if isinstance(values.get(key),str):values[key]=ast.literal_eval(values[key])
    if 'persistent'in values:
        if values['persistent'] not in ('True','False'):raise ValueError('invalid archived boolean')
        values['persistent']=values['persistent']=='True'
    for key in ('tile_shape','initial_tile_shape'):
        if values.get(key)is not None:values[key]=int(values[key])
    if 'nodes'in values:values['nodes']=[restore(n)for n in values['nodes']]
    return getattr(mp,record['type'])(**values)


def number(value):
    result=float(value)
    if not math.isfinite(result):raise ValueError('nonfinite model observation')
    return int(result) if result.is_integer() else result


def reservation_observation(reuse):
    entries=[];depths={}
    for buffet,stats in reuse.buffet_stats.items():
        if str(buffet.level)!='GlobalBuffer':continue
        bits=number(stats.max_occupancy);depth=int(stats.n_loops_above)
        if type(bits)is not int or bits<0:raise ValueError('noninteger GB reservation')
        entries.append(dict(tensor=str(buffet.tensor),bits=bits,bytes=bits/8,
                            loop_depth=depth,persistent=bool(stats.persistent)))
        depths[depth]=depths.get(depth,0)+bits
    cumulative=0;prefixes=[]
    for depth,bits in sorted(depths.items()):
        cumulative+=bits;prefixes.append(dict(loop_depth=depth,cumulative_bits=cumulative))
    return dict(tensors=entries,reservation_prefixes=prefixes,
        phase_peak_bits=max((p['cumulative_bits']for p in prefixes),default=0),
        scope='native buffet/reservation accounting, not an independent physical live-set proof')


def replay(mapping,shape,capacity):
    spec=build(CASE,tuple(shape),capacity,METRICS);spec.mapping=copy.deepcopy(mapping)
    common.clear_switches()
    module=importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.run_model')
    original_run=module.run_model;original_reuse=module.analyze_reuse_and_add_reservations_to_mapping
    phases=[];joins=[];active=[]
    from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
    merge=PmappingDataframe.merge_next;prepare=PmappingDataframe._prepare_join_plan
    signature=inspect.signature(merge)
    def resources(obj):
        return dict(rows=len(obj.data),columns={c:[number(v)for v in obj.data[c]]
            for c in obj.data if c.startswith(('reservation_bits<SEP>GlobalBuffer','reservation<SEP>GlobalBuffer',
                'tensor<SEP>','capacity_reference_bits<SEP>GlobalBuffer','resource_capacity_bits<SEP>GlobalBuffer'))})
    def reservation(r):
        return dict(tensor=str(r.name),resource=r.resource_name,above_loop_index=r.above_loop_index,
            loops=[dict(rank=str(l.rank_name),tile=str(l.tile_pattern))for l in r.loops])
    def capture_prepare(self,right,*args,**kwargs):
        plan=prepare(self,right,*args,**kwargs)
        if active:
            active[-1].update(prepared_left=resources(self),prepared_right=resources(right),
                shared_to_free=[reservation(r)for r in plan['shared_to_free']],
                live_to_alloc=[reservation(r)for r in plan['live_to_alloc']])
            active[-1]['_plan']=plan
        return plan
    def capture_merge(self,right,*args,**kwargs):
        bound=signature.bind(self,right,*args,**kwargs).arguments
        entry=dict(shared_loop_index=bound['shared_loop_index'],
            next_shared_loop_index=bound['next_shared_loop_index'],
            live_tensors=sorted(map(str,bound['live_tensors'])),
            left_before=resources(self),right_before=resources(right))
        active.append(entry)
        try:
            result=merge(self,right,*args,**kwargs)
            entry['result']=resources(result)
            plan=entry.pop('_plan',None)
            if plan is not None:entry['resource_column_operations']=[list(op)for op in (plan['column_operations']or [])
                if any('GlobalBuffer'in str(c) for c in op)]
            joins.append(entry);return result
        finally:active.pop()
    def capture_reuse(job):
        result=original_reuse(job)
        current=reservation_observation(result)
        current.update(einsum=str(job.einsum_name),model_mapping=mapping_structure(job.mapping))
        phases.append(current)
        return result
    def capture_run(job):
        # Archived structures omit derived component objects. Restore references
        # from THIS evaluated target/Einsum, including tensor-renamed may_reuse.
        for node in job.mapping.nodes:
            if getattr(node,'component',None):node.component_object=job.spec.arch.find(node.component)
        result=original_run(job);df=result[1]
        phases[-1].update(energy_j=number(df['Total<SEP>energy']),
            latency_s=number(df['Total<SEP>latency']),
            actions={k:number(v)for k,v in df.items()if k.startswith('action<SEP>')},
            component_latencies_s={k:number(v)for k,v in df.items()if k.startswith('latency<SEP>')},
            detailed_energy_j={k:number(v)for k,v in df.items()if k.startswith('energy<SEP>')},
            model_resource_prefixes={k:number(v)for k,v in df.items()if k.startswith('reservation_bits<SEP>')})
        return result
    error=None
    with patch.object(module,'run_model',capture_run),patch.object(module,'analyze_reuse_and_add_reservations_to_mapping',capture_reuse), \
         patch.object(PmappingDataframe,'merge_next',capture_merge),patch.object(PmappingDataframe,'_prepare_join_plan',capture_prepare):
        try:frame=common.evaluate_mapping(spec).data
        except Exception as exc:
            frame=None;error=f'{type(exc).__name__}: {exc}'
    phase_peak=max((p['phase_peak_bits']for p in phases),default=0)
    record=dict(shape=shape,capacity_bytes=capacity,mapping_id=common.mapping_identity(mapping),
        phases=phases,join_resource_transfers=joins,maximum_phase_reservation_bits=phase_peak,evaluation_error=error,
        resource_units='absolute bits; AF_RESOURCE_UNITS defaults to bits after clearing AF switches',
        independent_physical_lifetime_validation=False)
    if frame is None or not len(frame):
        if phase_peak<=capacity*8:raise RuntimeError(f'unexplained replay failure: {error}')
        record.update(feasible=False,reason='known native phase reservation exceeds capacity',
                      joined_rows=0,excess_phase_bits=phase_peak-capacity*8)
    else:
        if len(frame)!=1:raise ValueError('fixed mapping produced more than one model row')
        row=frame.iloc[0];peak=int(row[RAW_GB]);e=float(row['Total<SEP>energy']);t=float(row[common.LATENCY])
        record.update(feasible=peak<=capacity*8,globalbuffer_peak_bits=peak,energy_j=e,
            latency_s=t,edp_j_s=e*t,joined_rows=1,
            actions={c:number(row[c])for c in row.index if '<SEP>action<SEP>'in c},
            detailed_energy_j={c:number(row[c])for c in row.index if '<SEP>energy<SEP>'in c})
    return record


def phase_materialized_intermediates(mapping):
    """A fixed-map control, NOT a reoptimized or general no-sharing baseline.

    Restrict to root Sequential with three linear stages and root-backed T1/T2.
    Move backing to DRAM; insert full per-stage GB copies at the same root scope.
    All loop/spatial choices are preserved. No after-loop DRAM Storage is added.
    """
    result=copy.deepcopy(mapping)
    if any(isinstance(n,mp.Loop)for n in result.nodes):raise ValueError('outer-loop control unsupported')
    splits=[n for n in result.nodes if isinstance(n,mp.Sequential)]
    if len(splits)!=1 or len(splits[0].nodes)!=3:raise ValueError('requires three root sequential stages')
    shared=set()
    for n in result.nodes:
        if isinstance(n,mp.Storage)and n.component=='GlobalBuffer':shared.update(n.tensors)
    if shared!={'T1','T2'}:raise ValueError('control requires both full intermediates at root GB')
    result.nodes=[n for n in result.nodes if not(isinstance(n,mp.Storage)and n.component=='GlobalBuffer')]
    split=next(n for n in result.nodes if isinstance(n,mp.Sequential))
    result.nodes.insert(0,mp.Storage(component='MainMemory',tensors=['T1','T2']))
    relevant=({'T1'},{'T1','T2'},{'T2'})
    for child,tensors in zip(split.nodes,relevant):
        if any(isinstance(n,mp.Split)for n in child.nodes):raise ValueError('nested split control unsupported')
        child.nodes.insert(0,mp.Storage(component='GlobalBuffer',tensors=sorted(tensors)))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--zero-fusion-controls',action='store_true');args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    archive=json.loads(SOURCE.read_text());picks=archive['runs'][0]['picks']
    report=dict(status='in_progress',source=str(SOURCE.relative_to(ROOT)),
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),replays=[],
        residency_controls=[],zero_fused_loop_controls=[],mapping_search_calls=0,
        scope='native model causal diagnosis; no independent physical lifecycle or new optimizer')
    def save():args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    common.af.set_n_parallel_jobs(1)
    for pick in picks:
        mapping=restore(pick['mapping'])
        if common.mapping_identity(mapping)!=pick['mapping_id'] or mapping_structure(mapping)!=pick['mapping']:
            raise AssertionError('archive restoration changed source identity/structure')
        for capacity in (131072,135168):
            r=replay(mapping,pick['shape'],capacity)
            r.update(source_capacity_bytes=pick['capacity_bytes'],source_mapping_id=pick['mapping_id'])
            if capacity==pick['capacity_bytes']:
                if not r['feasible']:raise AssertionError('archived winner no longer fits its source hardware')
                for key,reference in (('energy_j',pick['energy']),('latency_s',pick['latency'])):
                    if not math.isclose(r[key],reference,rel_tol=1e-6):raise AssertionError('archive cost mismatch')
            report['replays'].append(r);save()
        if pick['capacity_bytes']==135168:
            controlled=phase_materialized_intermediates(mapping)
            r=replay(controlled,pick['shape'],135168)
            if not r['feasible']:raise AssertionError('materialization control unexpectedly infeasible')
            r.update(source_mapping_id=pick['mapping_id'],controlled_mapping=mapping_structure(controlled),
                contract='fixed loops/spatial; T1/T2 DRAM backing plus full per-phase GB copies; no reoptimization')
            report['residency_controls'].append(r);save()
    if args.zero_fusion_controls:
        for pick in picks:
            spec=build(CASE,tuple(pick['shape']),pick['capacity_bytes'],common.EL)
            spec.mapper.ffm.max_fused_loops=0
            result,stats=common.search(spec);report['mapping_search_calls']+=1
            row=common.best_row(result.data)
            if row is None:raise AssertionError('no zero-fused-loop control candidate')
            mapping=row['Total<SEP>mapping']();r=replay(mapping,pick['shape'],pick['capacity_bytes'])
            if not r['feasible']:raise AssertionError('zero-fused-loop control did not fit')
            selected_energy=float(row['Total<SEP>energy']);selected_latency=float(row[common.LATENCY])
            if not(math.isclose(r['energy_j'],selected_energy,rel_tol=1e-6)and
                   math.isclose(r['latency_s'],selected_latency,rel_tol=1e-6)):
                raise AssertionError('zero-fused-loop selected cost disagrees with replay')
            r.update(search=stats,mapping=mapping_structure(mapping),
                selected_cost_matches_replay=True,selected_energy_j=selected_energy,selected_latency_s=selected_latency,
                contract='native EL reoptimized with max_fused_loops=0; storage sharing still allowed')
            report['zero_fused_loop_controls'].append(r);save()
    report.update(status='complete',file_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__),ROOT/'accelforge/model/main.py',
            ROOT/'accelforge/model/_looptree/reuse/symbolic/symbolic.py',
            ROOT/'accelforge/mapper/FFM/_make_pmappings/make_pmappings_from_templates/run_model.py',
            ROOT/'accelforge/mapper/FFM/_join_pmappings/pmapping_dataframe.py',
            ROOT/'examples/arches/nvdla.yaml',ROOT/'examples/workloads/matmuls.yaml')})
    save();print(json.dumps(dict(status='complete',replays=len(report['replays']),
        residency_controls=len(report['residency_controls']),zero_fused_loop_controls=len(report['zero_fused_loop_controls']))))


if __name__=='__main__':main()
