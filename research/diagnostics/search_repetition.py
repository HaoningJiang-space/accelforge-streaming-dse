"""Retrospective identity observations. No cache/pruning decisions are changed."""
from contextlib import ExitStack
from dataclasses import fields,is_dataclass
from enum import Enum
import importlib
import inspect

import numpy as np
import pandas as pd
import sympy
from unittest.mock import patch

from research.tracking_audit.shape_capacity_audit import mapping_structure
from accelforge.frontend.mapping import MappingNode
from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse


def freeze(value):
    if isinstance(value,sympy.Basic):return ('sympy',sympy.srepr(value))
    if isinstance(value,np.generic):return ('numpy',value.dtype.str,value.item())
    if isinstance(value,MappingNode):return freeze(mapping_structure(value))
    if is_dataclass(value):return (type(value).__name__,tuple((f.name,freeze(getattr(value,f.name)))for f in fields(value)))
    if isinstance(value,Enum):return (type(value).__name__,value.name)
    if isinstance(value,dict):return tuple(sorted((str(k),freeze(v))for k,v in value.items()))
    if isinstance(value,(set,frozenset)):return ('set',tuple(sorted((freeze(v)for v in value),key=repr)))
    if isinstance(value,(list,tuple)):return tuple(freeze(v)for v in value)
    if value is None or type(value)in (str,int,float,bool,bytes):return value
    raise TypeError('unknown forensic identity type: '+str(type(value)))


class Observations:
    def __init__(self):self.entries={}
    def add(self,key,target,rows=0,actual=True):
        entry=self.entries.setdefault(key,dict(requests=0,actual=0,rows=0,actual_rows=0,first_rows=rows,
                                             first_actual_rows=None,targets=set()))
        entry['requests']+=1;entry['rows']+=rows;entry['targets'].add(repr(target))
        if actual:
            entry['actual']+=1;entry['actual_rows']+=rows
            if entry['first_actual_rows']is None:entry['first_actual_rows']=rows
    def summary(self):
        es=list(self.entries.values())
        return dict(requests=sum(e['requests']for e in es),unique_keys=len(es),
            keys_seen_at_multiple_targets=sum(len(e['targets'])>1 for e in es),
            repeated_requests=sum(e['requests']-1 for e in es),
            requested_rows=sum(e['rows']for e in es),actual_calls=sum(e['actual']for e in es),
            repeated_actual_calls=sum(max(0,e['actual']-1)for e in es),
            repeated_actual_rows=sum(e['actual_rows']-(e['first_actual_rows']or 0)for e in es))


class RepetitionAudit:
    def __init__(self):
        self.target=None;self.prefix=Observations();self.compiles=Observations()
        self.models=Observations();self.programs=Observations();self.resource_inputs=Observations()
        self.unclassified_prefix_requests=0;self.retained_prefix_key_bytes=0
        self.unclassified_compile_requests=0;self.merge_calls=0
        self.key_budget_bytes=128*2**20
    def __enter__(self):
        self.stack=ExitStack()
        tiles=importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')
        df=importlib.import_module('accelforge.mapper.FFM._join_pmappings.pmapping_dataframe')
        original_expand=EnumerationReuse.expand;original_compile=EnumerationReuse.compile
        original_model=tiles.run_model;original_prepare=df.PmappingDataframe._prepare_join_plan
        original_merge=df.PmappingDataframe.merge_next;signature=inspect.signature(original_merge)
        original_pandas_merge=pd.merge
        pending=[]
        def expansion(scope,symbol,prefix,done,relations,imperfect,compute):
            before=scope.stats['expansions']
            result=original_expand(scope,symbol,prefix,done,relations,imperfect,compute)
            relation_key=(tuple(relations.what_tiles_symbol),tuple(relations.tile_shape_and_initial),
                tuple((s,tuple(v))for s,v in relations.delta_choices),tuple(relations.bounds))
            content=None if prefix is None else(prefix.dtype.str,prefix.shape,prefix.tobytes(order='C'))
            key=(symbol,tuple(done),relation_key,imperfect,content)
            size=0 if content is None else len(content[2])
            if key not in self.prefix.entries and self.retained_prefix_key_bytes+size>self.key_budget_bytes:
                self.unclassified_prefix_requests+=1
            else:
                if key not in self.prefix.entries:self.retained_prefix_key_bytes+=size
                # Actual Python key equality matches the native cache's key,
                # rather than conflating same-name Symbols with different assumptions.
                self.prefix.add(key,scope._target,len(result),scope.stats['expansions']>before)
            return result
        def compile_formula(scope,symbols,formula,float_type,compiler):
            before=scope.stats['compilations'];result=original_compile(scope,symbols,formula,float_type,compiler)
            key=(tuple(symbols),formula,np.dtype(float_type).str)
            try:hash(key)
            except TypeError:self.unclassified_compile_requests+=1
            else:self.compiles.add(key,scope._target,actual=scope.stats['compilations']>before)
            return result
        def model(job):
            result=original_model(job)
            physical={k:v for k,v in result[1].items()if not k.startswith('resource_capacity_bits<SEP>')}
            self.models.add(freeze((job.einsum_name,mapping_structure(job.mapping),physical)),self.target)
            return result
        def prepare(left,right,*args,**kwargs):
            result=original_prepare(left,right,*args,**kwargs)
            if pending:
                pending[-1]['plan']=result
                match=(result['left_match'],result['right_match'])
                def numeric(frame,extra):
                    columns=sorted(c for c in frame if c.startswith(('reservation<SEP>','tensor<SEP>'))or c in extra)
                    return tuple((c,frame[c].dtype.str,frame[c].to_numpy().tobytes())for c in columns)
                pending[-1]['numeric']=(numeric(left.data,match[0]),numeric(right.data,match[1]))
            return result
        def merge(left,right,*args,**kwargs):
            self.merge_calls+=1
            bound=signature.bind(left,right,*args,**kwargs).arguments
            context=freeze({k:v for k,v in bound.items()if k in ('shared_loop_index','next_shared_loop_index',
                'live_tensors','still_live_reservations','duplicated_aliased_tensors','compatibility_left',
                'compatibility_right','compatibility_joined','ignored_resources','drop_valid_reservations')})
            pending.append({})
            try:
                result=original_merge(left,right,*args,**kwargs)
                entry=pending[-1]
                if 'plan'in entry:
                    p=entry['plan'];program=freeze((context,p['left_match'],p['right_match'],
                        [op for op in(p['column_operations']or[])if any('GlobalBuffer'in str(c)for c in op)],
                        p['shared_to_free'],p['live_to_alloc']))
                    # Weight by actual pre-membership matched pairs, not by the
                    # much smaller post-Pareto result returned by merge_next.
                    pairs=entry.get('matched_pairs',0)
                    self.programs.add(program,self.target,pairs)
                    self.resource_inputs.add((program,entry['numeric']),self.target,pairs)
                return result
            finally:pending.pop()
        def pandas_merge(*args,**kwargs):
            result=original_pandas_merge(*args,**kwargs)
            if pending and tuple(kwargs.get('suffixes',()))==('', '_RIGHT_MERGE'):
                pending[-1]['matched_pairs']=pending[-1].get('matched_pairs',0)+len(result)
            return result
        self.stack.enter_context(patch.object(EnumerationReuse,'expand',expansion))
        self.stack.enter_context(patch.object(EnumerationReuse,'compile',compile_formula))
        self.stack.enter_context(patch.object(tiles,'run_model',model))
        self.stack.enter_context(patch.object(df.PmappingDataframe,'_prepare_join_plan',prepare))
        self.stack.enter_context(patch.object(df.PmappingDataframe,'merge_next',merge))
        self.stack.enter_context(patch.object(pd,'merge',pandas_merge))
        return self
    def __exit__(self,*args):return self.stack.__exit__(*args)
    def summary(self):
        return dict(prefix=self.prefix.summary(),formula_compile=self.compiles.summary(),
            physical_model_outputs=self.models.summary(),resource_programs=self.programs.summary(),
            resource_program_and_input_subframes=self.resource_inputs.summary(),
            unclassified_prefix_requests=self.unclassified_prefix_requests,
            unclassified_compile_requests=self.unclassified_compile_requests,merge_calls=self.merge_calls,
            retained_prefix_key_payload_bytes=self.retained_prefix_key_bytes,
            scope='Retrospective observations only. Resource rows count pre-membership matched pairs. Resource keys exclude cost/Pareto/membership state; not future-equivalence proofs or directly reusable complete states.',
            timing_scope='Heavy tracing excluded from all timing and phase-profile passes.')
