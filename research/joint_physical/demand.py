"""LP-proposed integer tiles with shared hardware and fusion properties.

Materialize only selected complete assignments. Never invoke native Cartesian
Tile expansion. Completed rows still pass through unmodified native numeric Join.
This is a heuristic candidate generator, not a completeness certificate.
"""
from fractions import Fraction as F
from itertools import product
import json
import math
import os
import time
from unittest.mock import patch

import numpy as np
from scipy.optimize import linprog
import sympy as sp

from accelforge.mapper.FFM._join_pmappings.pmapping_group import PmappingGroup
from accelforge.mapper.FFM._pareto_df import exact_resources as exact
from accelforge.mapper.FFM._pareto_df.target_membership import build_target_membership
from accelforge.mapper.FFM.generation_contract import GenerationContract
from research.fusion_envelope.native import model_from_capture, NativeEnvelope
from research.joint_search import ffm_backend as backend
from research.joint_search.conditional_generator import JointGenerationContract
from research.joint_search.conditional_composer import compose,query_architecture
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import mapping_structure
from .generator import PhysicalDomain,prepare


class Proposer:
    def __init__(self,domain,completion_limit=0):
        self.domain = domain
        self.properties = {p:set() for p in domain.points}
        self.cache = {}
        self.processed = {}
        self.round = 0
        self.completion_limit = completion_limit
        self.stats = dict(symbolic_models=0,lp_requests=0,lp_solves=0,lp_cache_hits=0,
            proposed_integer_rows=0,feasible_integer_rows=0,materialized_rows=0,
            cartesian_tile_expansions=0,proxy_demands=0,complete_factor_assignments=0)

    def __call__(self,**data):
        for key in ('capacity_targets','capacity_exact','membership_format'):
            data.pop(key,None)
        job,symbols = data['job'],tuple(data['symbols'])
        model,energy,latency = model_from_capture(data,(self.domain.upper.px,self.domain.upper.py))
        self.stats['symbolic_models'] += 1
        n = len(symbols)
        indices = {s:i for i,s in enumerate(symbols)}
        objectives = {o.name:o for o in data['objectives']}
        fused = []
        for node in job.mapping.nodes:
            if isinstance(node,backend.tiles.Temporal) and node._fused:
                fused.append((node.rank_variable,node.tile_shape))
        previous = dict(job.rank_variable_bounds)
        spatial = {'reuse_input':sp.Integer(1),'reuse_output':sp.Integer(1)}
        for node in job.mapping.nodes:
            if isinstance(node,backend.tiles.Loop):
                if isinstance(node,backend.tiles.Spatial):
                    spatial[node.name] *= sp.sympify(previous[node.rank_variable])/node.tile_shape
                previous[node.rank_variable] = node.tile_shape
        compiled = {name:backend.tiles.compile_objective(symbols,obj.formula)
                    for name,obj in objectives.items() if name in ('Total<SEP>energy','Total<SEP>latency')}

        def costs(choices,name):
            values = backend.tiles.call_compiled_objective(compiled[name],*choices.astype(common.af.util.NUMPY_FLOAT_TYPE).T)
            return np.broadcast_to(np.asarray(values),(len(choices),))

        def feasible(choices,point):
            if not len(choices):
                return choices
            valid = np.ones(len(choices),dtype=bool)
            env = dict(zip(symbols,choices.T))
            for outer,inner in data['what_tiles_symbol'].what_tiles_symbol:
                a = env[outer] if outer in env else outer
                b = env[inner] if inner in env else inner
                valid &= np.asarray(a)>=np.asarray(b)
            choices = choices[valid]
            if not len(choices):
                return choices
            valid = np.ones(len(choices),dtype=bool)
            env = dict(zip(symbols,choices.T))
            for name,obj in objectives.items():
                if name.startswith('usage<SEP>memory<SEP>'):
                    memory = name.split('<SEP>')[-1]
                    bound = point.capacity_bytes*8 if memory=='GlobalBuffer' else job.resource_capacities.get(memory)
                    if bound is None:
                        continue
                    values = exact.bit_array(obj.formula,env,len(choices))
                    valid &= values<=bound
            for name,formula in spatial.items():
                values = exact.bit_array(formula,env,len(choices))
                valid &= values <= (point.px if name=='reuse_input' else point.py)
            choices = choices[valid]
            return backend.tiles.check_loops(list(symbols),choices,data['max_loop_check_groups'],data['what_tiles_symbol'])

        def rounded(logs,fixed):
            possibilities = []
            for i,value in enumerate(logs):
                if i in fixed:
                    possibilities.append((fixed[i],))
                else:
                    lo,hi = math.floor(value+1e-8),math.ceil(value-1e-8)
                    lo,hi = max(0,lo),min(int(model.upper[i]),hi)
                    possibilities.append(tuple(sorted({lo,hi})))
            if not possibilities:
                return np.empty((1,0),dtype=np.int64)
            rows = []
            for count,values in enumerate(product(*possibilities)):
                if count>=64:
                    break
                rows.append(tuple(1<<int(v) for v in values))
            # Local integer neighbors repair fractional LP minima and preserve
            # useful low-workspace variants without full Cartesian enumeration.
            bases = list(rows)
            for row in bases:
                for i in range(n):
                    if i in fixed:
                        continue
                    for shift in (-1,1):
                        exponent = int(math.log2(row[i]))+shift
                        if 0<=exponent<=model.upper[i]:
                            neighbor = list(row)
                            neighbor[i] = 1<<exponent
                            rows.append(tuple(neighbor))
            rows = sorted(set(rows))
            return np.asarray(rows,dtype=np.int64).reshape((-1,n))

        source = model.source_contract
        source_key = (str(job.einsum_name),source['energy'],source['latency'],
            tuple(sorted(source['memory'].items())),tuple(sorted(source['spatial'].items())),
            tuple(source['factor_relations']),tuple(source['symbols']),
            json.dumps(mapping_structure(job.mapping),sort_keys=True),
            tuple((str(rank),str(symbol)) for rank,symbol in fused))
        cache = self.cache.setdefault(source_key,{})
        def propose(point,objective,fixed):
            rhs = model.target_rhs(point)
            # Capping redundant RHS values enables exact reuse across factor
            # geometries with the same active constraints, without selecting a
            # known winner from a reference run.
            signature = tuple(min(b,sum(max(F(),a)*model.upper[i] for i,a in row.items()))
                              for b,row in zip(rhs,model.rows))
            scale = max([F(1)]+[abs(v) for v in objective.terms.values()])
            normalized = tuple(sorted((i,v/scale) for i,v in objective.terms.items()))
            key = (normalized,signature,tuple(sorted(fixed.items())))
            self.stats['lp_requests'] += 1
            if key in cache:
                self.stats['lp_cache_hits'] += 1
                return cache[key]
            if not n:
                result = np.empty((1,0),dtype=np.int64) if all(b>=0 for b in rhs) else np.empty((0,0),dtype=np.int64)
            else:
                c = np.zeros(len(model.upper))
                for i,value in normalized:
                    c[i] = float(value)
                bounds = [(0,None)]*len(c)
                for i,value in fixed.items():
                    bounds[i] = (value,value)
                answer = linprog(c,A_ub=model.matrix,b_ub=[float(b) for b in rhs],bounds=bounds,
                                 method='highs',options={'threads':1})
                self.stats['lp_solves'] += 1
                result = rounded(answer.x[:n],fixed) if answer.success else np.empty((0,n),dtype=np.int64)
            cache[key] = result
            return result

        selected = {}
        complete = None
        if self.completion_limit:
            counts = [int(v)+1 for v in model.upper[:n]]
            total = math.prod(counts)
            if total>self.completion_limit:
                raise ValueError('bounded exact factor completion exceeds the declared limit')
            complete = np.asarray([tuple(1<<k for k in row) for row in product(*(range(k) for k in counts))],
                                  dtype=np.int64).reshape((total,n))
            self.stats['complete_factor_assignments'] += total
        for target,point in enumerate(self.domain.points):
            if complete is not None:
                for row in feasible(complete,point):
                    selected.setdefault(tuple(int(v) for v in row),set()).add(target)
                continue
            demand_sets = [{}]
            if str(job.einsum_name)=='QK_softmax' or self.round>0:
                for prop in sorted(self.properties[point]):
                    prop = dict(prop)
                    fixed = {}
                    compatible = True
                    for rank,symbol in fused:
                        if rank not in prop:
                            continue
                        value = prop[rank]
                        if symbol in indices:
                            fixed[indices[symbol]] = int(math.log2(value))
                        elif int(symbol)!=value:
                            compatible = False
                    if compatible and fixed:
                        demand_sets.append(fixed)
                        self.stats['proxy_demands'] += 1
            candidates = []
            processed = self.processed.setdefault((source_key,point),set())
            for fixed in demand_sets:
                fixed_key = tuple(sorted(fixed.items()))
                if fixed_key in processed:
                    continue
                for weight in (F(),F(1,4),F(1,2),F(1)):
                    objective = energy.plus(latency.scale(weight))
                    choices = propose(point,objective,fixed)
                    self.stats['proposed_integer_rows'] += len(choices)
                    choices = feasible(choices,point)
                    self.stats['feasible_integer_rows'] += len(choices)
                    if len(choices):
                        score = costs(choices,'Total<SEP>energy')+float(weight)*costs(choices,'Total<SEP>latency')
                        by_property = {}
                        for i,row in enumerate(choices):
                            values = dict(zip(symbols,row))
                            prop = tuple((str(rank),int(values[symbol] if symbol in values else symbol))
                                         for rank,symbol in fused)
                            by_property.setdefault(prop,[]).append(i)
                        for ids in by_property.values():
                            ordered = sorted(ids,key=lambda i:(score[i],tuple(choices[i])))
                            candidates.extend(tuple(int(v) for v in choices[i]) for i in ordered[:2])
                processed.add(fixed_key)
            for row in set(candidates):
                selected.setdefault(row,set()).add(target)
                values = dict(zip(symbols,row))
                prop = {}
                for rank,symbol in fused:
                    prop.setdefault(rank,int(values[symbol] if symbol in values else symbol))
                if prop:
                    self.properties[point].add(tuple(sorted(prop.items())))
        rows = sorted(selected)
        choices = np.asarray(rows,dtype=np.int64).reshape((-1,n)) if n else np.empty((len(rows),0),dtype=np.int64)
        membership = build_target_membership(len(rows),len(self.domain.points),
            [([i],sorted(selected[row])) for i,row in enumerate(rows)],'packed')
        self.stats['materialized_rows'] += len(rows)
        return choices,membership


def search(case,domain,rounds=1,completion_limit=0):
    if case.workload!='attention':
        raise ValueError('first demand-driven gate supports the actual Attention graph')
    if completion_limit and (rounds!=1 or case.params[0]>16):
        raise ValueError('factor completion is only a bounded small native verification mode')
    domain = PhysicalDomain(domain.points)
    saved = {k:v for k,v in os.environ.items() if k.startswith('AF_')}
    try:
        common.clear_switches()
        common.af.set_n_parallel_jobs(1)
        os.environ['AF_CAPACITY_MEMBERSHIP'] = 'bitset'
        started = time.perf_counter()
        NativeEnvelope(case)  # Guards frozen model, architecture and source assumptions.
        spec,jobs = prepare(case,domain)
        preparation_s = time.perf_counter()-started
        proposer = Proposer(domain,completion_limit)
        groups,objects,returned_jobs = {},{},{}
        phase = time.perf_counter()
        def forbid_cartesian(*args,**kwargs):
            raise AssertionError('demand generator attempted full native Cartesian Tile expansion')
        with patch.object(backend.tiles,'get_tile_shape_choices_for_targets',proposer),patch.object(
                backend.tiles,'_compute_symbol_choices',forbid_cartesian):
            # Numerical properties come from both heavy operators before proxy
            # materialization. Full graph composition still follows native order.
            for stage in range(rounds):
                proposer.round = stage
                if stage:
                    spec,jobs = prepare(case,domain)
                for name in sorted(jobs,key=lambda n:str(n)=='QK_softmax'):
                    if rounds>1 and stage==0 and str(name)=='QK_softmax':
                        continue
                    groups.setdefault(name,[])
                    objects.setdefault(name,{})
                    returned_jobs.setdefault(name,[])
                    for same in jobs[name].values():
                        _,pg,po,pj = backend.templates.make_pmappings_from_templates(same)
                        groups[name].extend(pg)
                        objects[name].update(po)
                        returned_jobs[name].extend(pj)
            groups = {name:PmappingGroup.combine_combineable(gs,'All') for name,gs in groups.items()}
        generation_s = time.perf_counter()-phase
        candidates = backend.package(spec,groups,objects,returned_jobs,
            JointGenerationContract(GenerationContract.capture(common.RU),domain,version='lp-demand-tiles-v1'))
        phase = time.perf_counter()
        result = compose(candidates)
        join_s = time.perf_counter()-phase
        outputs = {p:query_architecture(result,domain,p) for p in domain.points}
        return outputs,dict(preparation_s=preparation_s,generation_s=generation_s,join_s=join_s,
            total_s=time.perf_counter()-started,proposer=proposer.stats,
            generated_rows=sum(len(g.mappings.data) for gs in groups.values() for g in gs),
            global_hardware_variable=True,native_numeric_join=True,heuristic=True,
            full_cartesian_tile_enumeration=False,proposal_rounds=rounds,
            bounded_factor_completion=bool(completion_limit))
    finally:
        common.clear_switches()
        os.environ.update(saved)
