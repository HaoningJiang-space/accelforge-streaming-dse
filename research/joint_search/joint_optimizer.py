"""Stage 0–2 gate: one finite conditional generation and native Fusion Join."""
import os
import time
from unittest.mock import patch

from accelforge.mapper.FFM._join_pmappings.pmapping_group import PmappingGroup
from accelforge.mapper.FFM.generation_contract import GenerationContract
from research.tracking_audit import common
from .conditional_generator import ArchitectureEnumerator, JointGenerationContract
from .conditional_composer import compose, query_architecture
from . import ffm_backend as backend


def _search_2mm(case, domain, capture):
    common.clear_switches()
    os.environ['AF_CAPACITY_MEMBERSHIP'] = 'bitset'
    common.af.set_n_parallel_jobs(1)
    started = time.perf_counter()
    spec, jobs = backend.prepare(case,domain)
    preparation_s = time.perf_counter()-started
    groups, objects, return_jobs, enumeration = {}, {}, {}, []

    def enumerate_joint(**kwargs):
        for k in ('capacity_targets','capacity_exact','membership_format'):
            kwargs.pop(k,None)
        objectives = kwargs.pop('objectives')
        engine = ArchitectureEnumerator(objectives,domain,**kwargs)
        result = engine.run()
        if capture is not None:
            capture(engine.job,kwargs['symbols'],*result)
        enumeration.append(dict(einsum=engine.job.einsum_name,
            model_rows=len(result[0]),**engine.stats))
        return result

    start = time.perf_counter()
    with patch.object(backend.tiles,'get_tile_shape_choices_for_targets',enumerate_joint):
        for name, by_compatibility in jobs.items():
            gs, obs, js = [], {}, []
            for same in by_compatibility.values():
                _, new_groups, new_objects, new_jobs = backend.templates.make_pmappings_from_templates(same)
                gs.extend(new_groups); obs.update(new_objects); js.extend(new_jobs)
            groups[name] = PmappingGroup.combine_combineable(gs,'All')
            objects[name], return_jobs[name] = obs, js
    generation_s = time.perf_counter()-start
    contract = JointGenerationContract(GenerationContract.capture(common.RU),domain)
    candidates = backend.package(spec,groups,objects,return_jobs,contract)
    start = time.perf_counter()
    result = compose(candidates)
    join_s = time.perf_counter()-start
    start = time.perf_counter()
    frontiers = {point:query_architecture(result,domain,point) for point in domain.points}
    query_s = time.perf_counter()-start
    return frontiers,dict(preparation_s=preparation_s,generation_s=generation_s,
        join_s=join_s,query_s=query_s,total_s=time.perf_counter()-started,
        enumeration=enumeration,
        generated_rows=sum(len(g.mappings.data) for gs in groups.values() for g in gs),
        shared_generation_calls=1,shared_join_calls=1,consumer_requirements_enabled=False)


def search_2mm(case, domain, capture=None):
    saved = {k:v for k,v in os.environ.items() if k.startswith('AF_')}
    try:
        return _search_2mm(case,domain,capture)
    finally:
        common.clear_switches()
        os.environ.update(saved)
