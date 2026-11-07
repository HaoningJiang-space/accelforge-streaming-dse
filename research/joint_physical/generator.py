"""One shared symbol/factor search with a common physical hardware variable.

Unlike the rejected original-policy prototype, this intentionally removes the
spatial minimum-usage preference and its ordered fallback. It searches the same
broader policy as the min_usage=0 Event reference. Native numeric Join remains
responsible for full prefix compatibility and lifetime/resource composition.
"""
from dataclasses import dataclass
import os
import time
from unittest.mock import patch

import sympy as sp
import numpy as np

from accelforge.mapper.FFM._join_pmappings.pmapping_group import PmappingGroup
from accelforge.mapper.FFM.generation_contract import GenerationContract
from accelforge.mapper.FFM._pareto_df.target_membership import build_target_membership
from research.joint_search import ffm_backend as backend
from research.joint_search.conditional_generator import ArchitectureEnumerator, JointGenerationContract
from research.joint_search.conditional_composer import compose, query_architecture
from research.joint_budget.protocol import Hardware
from research.joint_budget.analytic_bounds import check_frozen_inputs
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build


@dataclass(frozen=True)
class PhysicalDomain:
    points: tuple

    @property
    def upper(self):
        # A preparation envelope, never a candidate physical hardware design.
        return Hardware(*(max(getattr(p,key) for p in self.points) for key in ('px','py','capacity_bytes')))

    @property
    def labels(self):
        return tuple((i+1)/len(self.points) for i in range(len(self.points)))


class PhysicalEnumerator(ArchitectureEnumerator):
    def __init__(self,objectives,domain,**kwargs):
        # Zero min-usage is an everywhere-valid preference. Removing it avoids
        # importing the original policy's fallback history into the new space.
        objectives = [o for o in objectives if not o.name.startswith('min_usage_')]
        super().__init__(objectives,domain,**kwargs)
        previous = dict(self.job.rank_variable_bounds)
        spatial = {'reuse_input':sp.Integer(1),'reuse_output':sp.Integer(1)}
        for node in self.job.mapping.nodes:
            if isinstance(node,backend.tiles.Loop):
                if isinstance(node,backend.tiles.Spatial):
                    spatial[node.name] *= sp.sympify(previous[node.rank_variable])/node.tile_shape
                previous[node.rank_variable] = node.tile_shape
        for objective in self.active:
            if objective.name.startswith('usage<SEP>spatial<SEP>ArrayFanout<SEP>'):
                objective.formula = spatial[objective.name.split('<SEP>')[-1]]

    def run(self):
        if self.symbols:
            return super().run()
        # Elementwise proxy templates can have no tile decisions. The general
        # cohort interpreter deliberately falls back for those templates; here
        # evaluate their constant physical constraints for every hardware ID.
        allowed = []
        for index,point in enumerate(self.domain.points):
            valid = True
            for objective in self.active:
                value = sp.sympify(objective.formula)
                maximum = self.axes[objective.name][index] if objective.name in self.axes else objective.max_value
                if maximum is not None and value>maximum:
                    valid = False
                if objective.min_value is not None and value<objective.min_value:
                    valid = False
            if valid:
                allowed.append(index)
        nrows = int(bool(allowed))
        choices = np.empty((nrows,0),dtype=np.float64)
        membership = build_target_membership(nrows,len(self.domain.points),
            [([0],allowed)] if allowed else [],'packed')
        self.job.target_enumeration_stats = dict(self.stats)
        return choices,membership


def prepare(case,domain):
    check_frozen_inputs()
    if case.arch!='nvdla' or case.workload not in ('matmuls','attention'):
        raise ValueError('frozen NVDLA MatMul/Attention workload required')
    if len({p.px*p.py for p in domain.points})!=1:
        raise ValueError('first direct joint gate requires equal configured PE count')
    if backend.tiles.IMPERFECT or backend.tiles.pareto_module.TOLERANCE!=0:
        raise ValueError('perfect tiling and zero tolerance required')
    ranks = case.params[1:] if case.workload=='matmuls' else case.params
    if any(n&(n-1) for n in ranks):
        raise ValueError('perfect power-of-two rank extents required')
    upper = domain.upper
    spec = build(case,(upper.px,upper.py),upper.capacity_bytes,common.RU)
    for dim in spec.arch.find('ArrayFanout').spatial:
        dim.min_usage = 0
    evaluated = spec._spec_eval_expressions(eval_arch=False,eval_non_arch=True)
    jobs = backend.pmapper.get_jobs(evaluated,common.RU,evaluated.workload.einsum_names,True)
    backend.pmapper._fill_jobs_with_memories_to_track(jobs,evaluated,common.RU,False)
    for groups in jobs.values():
        for values in groups.values():
            for job in values:
                if any(float(getattr(node,'leak_power',0))!=0 for node in job.flattened_arch):
                    raise ValueError('sharing fixed Tile costs requires zero leakage')
                job.capacity_fractions = ('JointArchitectureDomain',domain.labels)
                job.capacity_target_bits = {}
    return spec,jobs


def search(case,domain):
    domain = PhysicalDomain(domain.points)
    saved = {k:v for k,v in os.environ.items() if k.startswith('AF_')}
    try:
        common.clear_switches()
        os.environ['AF_CAPACITY_MEMBERSHIP'] = 'bitset'
        common.af.set_n_parallel_jobs(1)
        started = time.perf_counter()
        spec,jobs = prepare(case,domain)
        preparation_s = time.perf_counter()-started
        groups,objects,returned_jobs,enumeration = {},{},{},[]
        def enumerate_joint(**kwargs):
            for key in ('capacity_targets','capacity_exact','membership_format'):
                kwargs.pop(key,None)
            engine = PhysicalEnumerator(kwargs.pop('objectives'),domain,**kwargs)
            result = engine.run()
            enumeration.append(dict(einsum=engine.job.einsum_name,model_rows=len(result[0]),**engine.stats))
            return result
        phase = time.perf_counter()
        with patch.object(backend.tiles,'get_tile_shape_choices_for_targets',enumerate_joint):
            for name,by_compatibility in jobs.items():
                gs,obs,js = [],{},[]
                for same in by_compatibility.values():
                    _,part_groups,part_objects,part_jobs = backend.templates.make_pmappings_from_templates(same)
                    gs.extend(part_groups)
                    obs.update(part_objects)
                    js.extend(part_jobs)
                groups[name] = PmappingGroup.combine_combineable(gs,'All')
                objects[name],returned_jobs[name] = obs,js
        generation_s = time.perf_counter()-phase
        contract = JointGenerationContract(GenerationContract.capture(common.RU),domain,
                                          version='direct-physical-no-min-usage-v1')
        candidates = backend.package(spec,groups,objects,returned_jobs,contract)
        phase = time.perf_counter()
        result = compose(candidates)
        join_s = time.perf_counter()-phase
        phase = time.perf_counter()
        outputs = {point:query_architecture(result,domain,point) for point in domain.points}
        return outputs,dict(preparation_s=preparation_s,generation_s=generation_s,join_s=join_s,
            query_s=time.perf_counter()-phase,total_s=time.perf_counter()-started,
            enumeration=enumeration,shared_generation_calls=1,shared_join_calls=1,
            model_rows=sum(r['model_rows'] for r in enumeration),
            global_hardware_variable=True,numeric_join_requirements='unmodified native Join',
            policy='minimum spatial usage zero; no original fallback equivalence claim')
    finally:
        common.clear_switches()
        os.environ.update(saved)
