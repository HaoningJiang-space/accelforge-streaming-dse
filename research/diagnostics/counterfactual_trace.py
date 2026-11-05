"""Untimed native trace for bounded consumer counterfactuals/effect diagnostics."""
import argparse
from collections import Counter,defaultdict
import gzip
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import time
from unittest.mock import patch

import numpy as np
import pandas as pd

from research.diagnostics.generation_provenance_3mm import GenerationProvenance
from research.diagnostics.profile_3mm_search import execute,snapshots
from research.diagnostics.scoped_resource_effect import compile_closed,concrete_oracle,parse,Unsupported,namespaced,chain_root_max
from research.tracking_audit import common

COSTS=('Total<SEP>energy','Total<SEP>latency')


def sources(frame):
    return sorted(c for c in frame if c.endswith('<SEP>compressed_index'))


def scalar(value):
    if hasattr(value,'item'):return value.item()
    if value==int(value):return int(value)
    raise ValueError('nonprimitive transition metadata')


def frozen_frame(frame):
    columns={};dtypes={}
    for c in frame:
        if frame[c].dtype.kind in 'biuf':
            columns[c]=frame[c].tolist();dtypes[c]=str(frame[c].dtype)
        elif frame[c].dtype.kind=='O':
            # Native exact-capacity metadata can contain SymPy Integers. Do not
            # route them through float during serialization or key construction.
            values=[scalar(v)for v in frame[c]]
            if any(type(v)is not int for v in values):raise ValueError('noninteger object transition column')
            columns[c]=values;dtypes[c]='uint64'if values and max(values)>=2**63 else 'int64'
        else:raise ValueError('trace requires primitive numeric transition columns')
    return dict(index=[int(x)for x in frame.index],columns=columns,dtypes=dtypes,
        native_dtypes={c:str(frame[c].dtype)for c in frame})


class CounterfactualTrace(GenerationProvenance):
    def __init__(self):
        super().__init__()
        self.buckets=[];self.active=[];self.local_groups=[]

    def __enter__(self):
        super().__enter__()
        module=importlib.import_module('accelforge.mapper.FFM._join_pmappings.pmapping_dataframe')
        comp=importlib.import_module('accelforge.mapper.FFM._join_pmappings.compress_pmappings')
        cls=module.PmappingDataframe
        compress,merge,prepare,limit,pareto=comp._compress,cls.merge_next,cls._prepare_join_plan,cls.limit_capacity,cls.make_pareto
        pandas_merge=pd.merge;signature=inspect.signature(merge)
        def compressed(einsum_name,pmappings,start_index):
            result=compress(einsum_name,pmappings,start_index)
            self.local_groups.append(dict(target=repr(self.target),einsum=str(einsum_name),
                group=len(self.local_groups),frame=result[0].data.copy(deep=True)))
            return result
        def joined(left,right,*args,**kwargs):
            bound=signature.bind(left,right,*args,**kwargs);bound.apply_defaults();v=bound.arguments
            record=dict(id=len(self.buckets),target=repr(self.target),
                shared_loop_index=v['shared_loop_index'],next_shared_loop_index=v['next_shared_loop_index'],
                live_tensors=sorted(map(str,v['live_tensors'])),
                alias_count=len(v['duplicated_aliased_tensors']),
                left_sources=sources(left.data),right_sources=sources(right.data))
            self.buckets.append(record);self.active.append(record)
            try:
                result=merge(left,right,*args,**kwargs)
                record['returned']=result.data.copy(deep=True)
                plan=record.pop('_plan',None)
                if plan is not None:
                    record['operations']=[list(x)for x in (plan['column_operations']or[])]
                    record['allocation_count']=len(plan['live_to_alloc'])
                    record['free_count']=len(plan['shared_to_free'])
                    record['left_match']=plan['left_match'];record['right_match']=plan['right_match']
                return result
            finally:self.active.pop()
        def prepared(left,right,*args,**kwargs):
            plan=prepare(left,right,*args,**kwargs)
            if self.active:
                r=self.active[-1];r['_plan']=plan
                r['prepared_left']=left.data.copy(deep=True)
                r['prepared_right']=right.data.copy(deep=True)
            return plan
        def matched(*args,**kwargs):
            frame=pandas_merge(*args,**kwargs)
            if self.active and tuple(kwargs.get('suffixes',()))==('', '_RIGHT_MERGE'):
                if 'matched'in self.active[-1]:raise AssertionError('multiple numeric matches in bucket')
                self.active[-1]['matched']=frame.copy(deep=True)
            return frame
        def capacity(frame,*args,**kwargs):
            if self.active:
                r=self.active[-1]
                if set(r['left_sources']+r['right_sources'])<=set(frame.data)and 'pre_capacity'not in r:
                    r['pre_capacity']=frame.data.copy(deep=True)
            return limit(frame,*args,**kwargs)
        def skyline(frame,*args,**kwargs):
            if self.active:
                r=self.active[-1]
                if len(sources(frame.data))==3 and r['next_shared_loop_index']==-1:
                    if 'terminal_pool'in r:raise AssertionError('multiple terminal skyline inputs')
                    r['terminal_pool']=frame.data.copy(deep=True)
            return pareto(frame,*args,**kwargs)
        for owner,name,function in ((comp,'_compress',compressed),(cls,'merge_next',joined),
            (cls,'_prepare_join_plan',prepared),(pd,'merge',matched),
            (cls,'limit_capacity',capacity),(cls,'make_pareto',skyline)):
            self.stack.enter_context(patch.object(owner,name,function))
        return self


def effect_diagnosis(buckets):
    start=time.perf_counter()
    resource_keys=set();state_keys=set();frontiers=defaultdict(list)
    unknowns=Counter();checks=0;producer_occurrences=0;records=[];cross_shapes=defaultdict(set)
    construction_s=validation_s=0.
    for bucket in buckets:
        if (bucket['next_shared_loop_index']!=-1 or bucket.get('allocation_count',1)or
            bucket.get('free_count',1)or bucket['alias_count']):
            unknowns['nonclosed_or_allocation_free_alias']+=1;continue
        if not all(k in bucket for k in ('prepared_left','prepared_right','matched','pre_capacity')):
            unknowns['missing_observed_numeric_input']+=1;continue
        left,right,paired,observed=(bucket[k]for k in ('prepared_left','prepared_right','matched','pre_capacity'))
        resources=[c for c in left if parse(c)is not None and parse(c)[0]in ('GlobalBuffer','Register')]
        right_resources=[c for c in right if parse(c)is not None and parse(c)[0]in ('GlobalBuffer','Register')]
        ops=[tuple(op)for op in bucket['operations']if parse(op[0])is not None and parse(op[0])[0]in ('GlobalBuffer','Register')]
        requirements=sorted(c for c in left if c not in (*COSTS,*sources(left),*resources))
        cache={};bucket_records=[]
        try:
            construction_start=time.perf_counter()
            for position in range(len(left)):
                producer_occurrences+=1
                values=tuple(int(left[c].iloc[position])for c in resources)
                effect=cache.setdefault(values,None)
                if effect is None:
                    effect=compile_closed(dict(zip(resources,values)),right_resources,ops);cache[values]=effect
                key=(effect.variables,effect.outputs)
                resource_keys.add(key);cross_shapes[key].add(bucket['target'])
                requirement=(bucket['id'],tuple((c,scalar(left[c].iloc[position]))for c in requirements),key)
                cost=tuple(float(left[c].iloc[position])for c in COSTS)
                state_keys.add((requirement,cost));frontiers[requirement].append(cost)
                bucket_records.append(dict(left_position=position,effect=effect.record(),energy=cost[0],latency=cost[1]))
            construction_s+=time.perf_counter()-construction_start
            validation_start=time.perf_counter()
            if not paired.index.is_unique or not observed.index.is_unique:
                raise Unsupported('nonunique paired row index')
            for index in observed.index:
                # Column-wise scalar access preserves exact integer resource values.
                lv={c:int(paired[c].loc[index])for c in resources}
                rv={c:int(paired[c+'_RIGHT_MERGE'if c in left else c].loc[index])for c in right_resources}
                effect=cache[tuple(lv[c]for c in resources)]
                predicted=effect.evaluate(rv)
                if predicted!=concrete_oracle(lv,rv,ops):
                    raise AssertionError('symbolic effect differs from independent scalar interpreter')
                for c,value in predicted.items():
                    if c not in observed or int(observed[c].loc[index])!=value:
                        raise AssertionError('effect differs from native closed-scope result')
                checks+=1
            validation_s+=time.perf_counter()-validation_start
        except Unsupported as error:
            unknowns[str(error)]+=1;continue
        records.append(dict(bucket=bucket['id'],target=bucket['target'],producer_states=bucket_records))
    frontier_start=time.perf_counter();conditional=0
    for costs in frontiers.values():
        unique=sorted(set(costs))
        conditional+=sum(not any(p!=q and p[0]<=q[0]and p[1]<=q[1]for p in unique)for q in unique)
    return dict(scope='Closed prepared numeric program only, not arbitrary continuation substitutability.',
        normalization_scope='Sufficient componentwise term reduction only; distinct canonical keys need not be semantically distinct on the admissible domain.',
        producer_row_occurrences=producer_occurrences,distinct_resource_functions=len(resource_keys),
        complete_fixed_context_cost_states=len(state_keys),conditional_equal_effect_pareto_states=conditional,
        resource_functions_observed_at_multiple_shape_targets=sum(len(v)>1 for v in cross_shapes.values()),
        native_matched_row_checks=checks,supported_buckets=len(records),unsupported_buckets=dict(unknowns),
        construction_and_validation_s=time.perf_counter()-start,records=records,
        summary_construction_s=construction_s,native_and_scalar_validation_s=validation_s,
        conditional_frontier_s=time.perf_counter()-frontier_start,
        generation_already_paid=True,avoided_generation_s=0.)


def archived_effects():
    path=common.ROOT/'research/diagnostics/results/causal_3mm_controls.json'
    archive=json.loads(path.read_text());records=[];checks=0
    for replay in archive['replays']:
        if replay['source_capacity_bytes']!=replay['capacity_bytes']:continue
        predicted=[];composed=None;coordinates={};previous_value=None
        for step,transfer in enumerate(replay['join_resource_transfers']):
            if transfer['shared_to_free']or transfer['live_to_alloc']:
                raise Unsupported('archived adjustment unsupported')
            left={c:int(v[0])for c,v in transfer['prepared_left']['columns'].items()if parse(c)is not None}
            right={c:int(v[0])for c,v in transfer['prepared_right']['columns'].items()if parse(c)is not None}
            operations=transfer['resource_column_operations']
            effect=compile_closed(left,tuple(right),operations)
            value=effect.evaluate(right)
            if value!=concrete_oracle(left,right,operations):raise AssertionError('archive scalar oracle mismatch')
            expected={c:int(v[0])for c,v in transfer['result']['columns'].items()if parse(c)is not None}
            if value!=expected:raise AssertionError('archive native result mismatch')
            if step==0:
                composed=namespaced(effect,'Matmul1')
            else:
                if operations:raise Unsupported('archived continuation is not root-max')
                chained_left={c.rsplit('<SEP>',1)[0]+'<SEP>left':v for c,v in previous_value.items()}
                if chained_left!=left:raise AssertionError('archive preparation differs from declared root rename')
                if concrete_oracle(chained_left,right,operations)!=value:raise AssertionError('independent chain mismatch')
                composed=chain_root_max(composed,tuple(right),'Matmul2')
            coordinates.update({('Matmul1'if step==0 else'Matmul2')+'::'+c:v for c,v in right.items()})
            if composed.evaluate(coordinates)!=value:raise AssertionError('composed effect differs from native stages')
            previous_value=value
            predicted.append(dict(effect=effect.record(),coordinates=right,result=value))
            checks+=1
        peak=predicted[-1]['result']['reservation<SEP>GlobalBuffer<SEP>0<SEP>right']
        if peak!=replay['globalbuffer_peak_bits']:raise AssertionError('archive whole peak mismatch')
        records.append(dict(shape=replay['shape'],source_capacity=replay['source_capacity_bytes'],
            energy=replay['energy_j'],latency=replay['latency_s'],peak_bits=peak,
            fits_128=peak<=131072*8,fits_132=peak<=135168*8,transfers=predicted,
            composed_effect=composed.record(),composed_coordinates=coordinates))
    library_fronts={}
    for shape in ((16,384),(32,192),(64,96)):
        for cap in (131072,135168):
            # Full Pareto of this SIX-PLAN library, keeping E/T/R correlated.
            plans=[p for p in records if tuple(p['shape'])==shape and p['peak_bits']<=cap*8]
            vecs=[(p['energy'],p['latency'],p['peak_bits'],8)for p in plans]
            front=[q for q in vecs if not any(p!=q and all(a<=b for a,b in zip(p,q))for p in vecs)]
            library_fronts[','.join(map(str,(*shape,cap)))]=front
    return dict(native_transfer_checks=checks,fixed_plan_records=records,
        full_fixed_library_frontiers=library_fronts,
        scope='Six archived fixed mappings only; no new native replays or exhaustive physical grammar claim.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    common.af.set_n_parallel_jobs(1);common.clear_switches()
    trace=CounterfactualTrace();start=time.perf_counter()
    outputs,_=execute('events_ru',forensics=trace)
    elapsed=time.perf_counter()-start
    fronts=snapshots(outputs,True)
    expected=json.loads((common.ROOT/'research/diagnostics/results/search_cost_3mm/events_ru_1.json').read_text())['frontiers']
    if fronts!=expected:raise AssertionError('counterfactual trace changed full frontiers')
    provenance=trace.finish(outputs,elapsed-trace.observer_s)
    args.output.mkdir(parents=True,exist_ok=True)
    raw=dict(status='complete',frontiers=fronts,provenance=provenance,
        final_target_rows={','.join(map(str,point)):frozen_frame(frame[[c for c in frame if c in COSTS or c.startswith('reservation_bits<SEP>')]])
            for point,frame in outputs.items()},
        local_groups=[dict(g,frame=frozen_frame(g['frame']))for g in trace.local_groups],
        buckets=[{k:frozen_frame(v)if isinstance(v,pd.DataFrame)else v for k,v in b.items()}for b in trace.buckets])
    with gzip.open(args.output/'trace.json.gz','wt')as stream:json.dump(raw,stream)
    effects=effect_diagnosis(trace.buckets)
    archived=archived_effects()
    (args.output/'effects.json').write_text(json.dumps(dict(effects=effects,archived=archived),indent=2)+'\n')
    receipt=dict(status='complete',full_frontiers_equal=True,trace_wall_s=elapsed,
        source_sha256={str(p.relative_to(common.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__),Path(__file__).with_name('scoped_resource_effect.py'))},
        generation_work_avoided=False,scope='One untimed observed native grid; bounded semantic/classification diagnosis only.')
    (args.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(dict(status='complete',buckets=len(trace.buckets),effect_checks=effects['native_matched_row_checks'],
        supported=effects['supported_buckets'],unsupported=effects['unsupported_buckets'])),flush=True)


if __name__=='__main__':main()
