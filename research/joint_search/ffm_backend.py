"""NVDLA native preparation/packaging; no changes to reference FFM code."""
import importlib
from accelforge.mapper.FFM.pmappings import MultiEinsumPmappings
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build

tiles = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')
pmapper = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings')
templates = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_pmappings_from_templates')


def prepare(case, domain):
    if case.workload != 'matmuls' or case.arch != 'nvdla' or case.params[0] != 2:
        raise ValueError('requires NVDLA 2mm')
    if any(x & (x-1) for x in case.params[1:]):
        raise ValueError('requires perfect power-of-two matrix dimensions')
    if tiles.IMPERFECT or tiles.pareto_module.TOLERANCE != 0:
        raise ValueError('requires reference perfect tiling and zero tolerance')
    upper = domain.upper
    spec = build(case,(upper.px,upper.py),upper.capacity_bytes,common.RU)
    evaluated = spec._spec_eval_expressions(eval_arch=False,eval_non_arch=True)
    jobs = pmapper.get_jobs(evaluated,common.RU,evaluated.workload.einsum_names,True)
    pmapper._fill_jobs_with_memories_to_track(jobs,evaluated,common.RU,False)
    for groups in jobs.values():
        for group in groups.values():
            for job in group:
                if any(float(getattr(n,'leak_power',0)) != 0 for n in job.flattened_arch):
                    raise ValueError('fixed Tile costs require zero leakage')
                job.capacity_fractions = ('JointArchitectureDomain',domain.labels)
                job.capacity_target_bits = {}
    return spec, jobs


def package(spec, groups, objects, jobs, contract):
    flat, evaluated = {}, {}
    for name, js in jobs.items():
        for job in js:
            flat[name,job.flattened_arch[-1].name] = job.flattened_arch
            evaluated[name] = job.spec
    names=list(spec.workload.einsum_names)
    return MultiEinsumPmappings(spec,{n:groups[n] for n in names},objects,jobs,
        False,set(names),flat,evaluated,(contract,))
