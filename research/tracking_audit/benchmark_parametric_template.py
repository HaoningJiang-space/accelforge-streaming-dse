"""Compile one MatMul template over integer (Px, Py, SRAM) before choosing queries."""
import argparse
import copy
from dataclasses import dataclass
import hashlib
import importlib
import json
from pathlib import Path
import time
from unittest.mock import patch

import numpy as np
import sympy

from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, mapping_structure, save, validate_pick
from research.tracking_audit.retarget_local_mappings import instantiate
from research.tracking_audit.parametric_template import Box, RegionEnumerator

tiles = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')
pmapper = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings')
E, L = 'Total<SEP>energy', 'Total<SEP>latency'
GB = 'usage<SEP>memory<SEP>GlobalBuffer'


@dataclass
class Program:
    kwargs: dict
    objectives: list
    model: dict
    template_key: str
    point: tuple
    spec: object


def prepare(size, point, template_key=None):
    """Prepare a real FFM template; stop before it enumerates any Tile choices."""
    if type(size) is not int or size <= 0 or size & (size-1):
        raise ValueError('prototype requires power-of-two MatMul bounds')
    case = common.Case('matmuls', 'nvdla', (1, size, size))
    spec = build(case, point[:2], point[2], common.RU)
    evaluated = spec._spec_eval_expressions(eval_arch=False, eval_non_arch=True)
    jobs = pmapper.get_jobs(evaluated, common.RU, evaluated.workload.einsum_names, True)
    pmapper._fill_jobs_with_memories_to_track(jobs, evaluated, common.RU, False)
    candidates = [(json.dumps(mapping_structure(j.mapping), sort_keys=True), j)
                  for groups in jobs.values() for group in groups.values() for j in group]
    candidates.sort(key=lambda pair: pair[0])
    if template_key is None:
        template_key, job = candidates[0]  # no query results or costs used to choose it
    else:
        job = next((j for key,j in candidates if key == template_key), None)
        if job is None:
            raise ValueError('the compiled template does not exist at this architecture')
    captured = {}
    original_model = tiles.run_model

    class StopPreparation(Exception):
        pass

    def model(j):
        result = original_model(j)
        captured['model'] = result[1]
        return result

    def stop(**kwargs):
        captured.update(kwargs)
        raise StopPreparation

    with patch.object(tiles, 'run_model', model), patch.object(tiles, 'get_tile_shape_choices_for_targets', stop):
        try:
            tiles._make_tile_shapes(job)
        except StopPreparation:
            pass
    kwargs = {k:captured[k] for k in ('symbols','what_tiles_symbol','job','keep_symbols','max_loop_check_groups')}
    return Program(kwargs, captured['objectives'], captured['model'], template_key, point, spec)


def parameterize(program):
    """Restricted adapter: exact capacity, fixed costs, unit spatial min_usage.

    For this perfect-tiled power-of-two MatMul, spatial usage is a tile symbol
    divided by a positive integer fanout. Its ordering is invariant to fanout.
    Feasibility/fallback events can therefore use the raw integer extent. No
    coefficient is inferred from a sampled target's already-pruned candidates.
    """
    axes, objectives = {}, []
    for old in program.objectives:
        o = copy.copy(old)
        if o.name == GB:
            if not o.exact:
                raise ValueError('integer-bit resource model required')
            # Keep the original bit formula for prefix Pareto; parameter axis C
            # below is measured in bits (queries in the benchmark convert bytes).
            axes[o.name] = 2
        elif o.name.startswith(('usage<SEP>spatial', 'min_usage_')):
            name = next((n for n in ('reuse_input','reuse_output') if o.name.endswith(n)), None)
            if name is None or (o.min_value is not None and o.min_value != 1) or (o.max_value is not None and o.max_value != 1):
                raise ValueError('only the two NVDLA unit-usage constraints are supported')
            axis = ('reuse_input','reuse_output').index(name)
            formula = sympy.simplify(o.formula * program.point[axis])
            if not isinstance(formula, sympy.Symbol) or formula not in program.kwargs['symbols']:
                raise ValueError('this prototype requires single-symbol spatial extents')
            o.formula = formula
            o.exact = True
            axes[o.name] = axis
        objectives.append(o)
    if set(axes.values()) != {0,1,2}:
        raise ValueError('all three parameter constraints must be present')
    if program.kwargs['keep_symbols']:
        raise ValueError('this first experiment is restricted to one unfused template')
    return objectives, axes


def instantiate_objectives(program, point):
    """Strong independent baseline: prepared formulas, original FFM enumeration."""
    objectives = [copy.copy(o) for o in program.objectives]
    for o in objectives:
        if o.name == GB:
            o.max_value = point[2] * 8
        elif o.name.startswith(('usage<SEP>spatial', 'min_usage_')):
            name = next(n for n in ('reuse_input','reuse_output') if o.name.endswith(n))
            axis = ('reuse_input','reuse_output').index(name)
            o.formula = o.formula * sympy.Rational(program.point[axis], point[axis])
    return objectives


def oracle(program, objectives=None):
    work = dict(state_expansions=0, expanded_rows=0)
    original = tiles._expand_symbol_choices

    def expand(*args, **kwargs):
        result = original(*args, **kwargs)
        work['state_expansions'] += 1
        work['expanded_rows'] += len(result)
        return result

    # The strong baseline shares immutable symbolic preparation. Copying the
    # entire Spec here would charge unrelated Python work to enumeration.
    kwargs = dict(program.kwargs)
    job = copy.copy(kwargs['job'])
    job.messages, job.pmapping_keep_rates = [], {}
    job.n_total_pmappings, job.n_valid_pmappings, job.n_evaluated_pmappings = 1, 1, 0
    kwargs['job'] = job
    with patch.object(tiles, '_expand_symbol_choices', expand):
        choices = tiles.get_tile_shape_choices(objectives or program.objectives, **kwargs)
    return choices, work


def selected_costs(program, choices):
    from accelforge.mapper.FFM._pareto_df import exact_resources as exact
    symbols = program.kwargs['symbols']
    if not len(choices):
        return np.empty((0,3))
    gb = next(o.formula for o in program.objectives if o.name == GB)
    columns = []
    if not hasattr(program, '_compiled_costs'):
        program._compiled_costs = {key:tiles.compile_objective(symbols, program.model[key]) for key in (E,L)}
    for key in (E,L):
        fn = program._compiled_costs[key]
        v = tiles.call_compiled_objective(fn, *choices.astype(tiles.util.NUMPY_FLOAT_TYPE).T)
        columns.append(np.broadcast_to(v, len(choices)))
    columns.append(exact.bit_array(gb, dict(zip(symbols, choices.T)), len(choices)))
    return np.column_stack(columns)


def frontier(costs):
    if not len(costs):
        return costs
    mask = tiles.makepareto_numpy(costs, ['min'] * costs.shape[1])
    return np.unique(costs[mask], axis=0)


def reconstruct_best(program, choices, costs):
    if not len(choices):
        return None
    i = int(np.argmin(costs[:,0]*costs[:,1]))
    job = program.kwargs['job']
    row = {f'{job.einsum_name}<SEP>{s}':int(v)
           for s,v in zip(program.kwargs['symbols'],choices[i])}
    mapping = instantiate(job.mapping,row,job.einsum_name)
    return {E:costs[i,0], L:costs[i,1], 'raw_gb_bits':int(costs[i,2]),
            'Total<SEP>mapping':lambda:mapping}


def validate_selected(case, point, pick):
    result = validate_pick(case,point[:2],point[2],pick)
    if pick is not None and result['gb_bytes']*8 != pick['raw_gb_bits']:
        raise AssertionError('reconstructed GlobalBuffer bits differ from the compiled row')
    result['exact_gb_match'] = True
    return result


class CompiledTemplate:
    def __init__(self, program, family_bytes):
        if tuple(program.point) != tuple(hi for lo,hi in family_bytes.ranges):
            raise ValueError('prepare the template at the declared family upper corner')
        self.program = program
        self.family_bytes = family_bytes
        # Capacity units stay identical to the independent enumerator all the
        # way through constraints and prefix Pareto. Only public queries use B.
        lo,hi = family_bytes.ranges[2]
        family = Box((*family_bytes.ranges[:2], (lo*8, hi*8)))
        objectives, axes = parameterize(program)
        self.engine = RegionEnumerator(tiles, objectives, family, axes=axes,
                                       **copy.deepcopy(program.kwargs)).build()
        parts = [s.choices for s in self.engine.leaves]
        self.choices = np.unique(np.concatenate(parts), axis=0) if parts else np.empty((0,len(program.kwargs['symbols'])))
        costs = selected_costs(program, self.choices)
        index = {tuple(row):i for i,row in enumerate(self.choices.tolist())}
        self.costs, self.choice_index = costs, index
        self.frontiers = [frontier(costs[[index[tuple(row)] for row in s.choices.tolist()]])
                          for s in self.engine.leaves]
        self.cost_rows = len(self.choices)

    def query(self, point):
        point = tuple(point)
        if len(point) != 3 or any(type(x) is not int for x in point) or not self.family_bytes.contains(point):
            raise ValueError('query outside the integer-byte architecture family')
        i = self.engine.locate((point[0],point[1],point[2]*8))
        if i is None:
            return np.empty((0,len(self.program.kwargs['symbols']))), np.empty((0,3))
        return self.engine.leaves[i].choices.copy(), self.frontiers[i].copy()

    def best_mapping(self, point):
        """Recover provenance from stored Tile assignments; no cost-model call."""
        choices, _ = self.query(point)
        if not len(choices):
            return None
        ids = [self.choice_index[tuple(row)] for row in choices.tolist()]
        return reconstruct_best(self.program,choices,self.costs[ids])


def canonical_choices(values):
    return np.unique(values, axis=0)


def run(args):
    if args.queries < 1:
        raise ValueError('at least one query is required')
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    case = common.Case('matmuls','nvdla',(1,args.size,args.size))
    report = {'config': common.effective_config(case), 'queries': []}
    report['source_sha256'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (Path(__file__),Path(__file__).with_name('parametric_template.py'))}
    family = Box(((8,128),(16,384),(args.min_capacity,args.max_capacity)))
    # Warm the generic Skyline JIT without touching any family/template.
    frontier(np.array([[1.,2.,3.],[2.,1.,2.]]))
    t0 = time.perf_counter()
    program = prepare(args.size, (128,384,args.max_capacity))
    prepared_s = time.perf_counter()-t0
    t0 = time.perf_counter()
    compiled = CompiledTemplate(program, family)
    compile_s = time.perf_counter()-t0
    report.update(family=family.ranges, template_id=hashlib.sha256(program.template_key.encode()).hexdigest(),
                  template=program.template_key, prepare_s=prepared_s, compile_s=compile_s,
                  stats=compiled.engine.stats, unique_cost_rows=compiled.cost_rows,
                  regions=[{'boxes':[b.ranges for b in s.targets], 'choices':s.choices.tolist(),
                            'frontier':f.tolist()} for s,f in zip(compiled.engine.leaves,compiled.frontiers)])
    save(args.output, report)

    # Query points are created AFTER compilation, and never passed to build().
    rng = np.random.default_rng(args.seed)
    points = [(48,128,132*1024),(24,256,128*1024),(96,64,64*1024),(40,160,96*1024)]
    points = [p for p in points if family.contains(p)]
    while len(points) < args.queries:
        point = tuple(int(rng.integers(lo,hi+1)) for lo,hi in family.ranges)
        if point not in points:
            points.append(point)
    points = points[:args.queries]
    total_query = total_enum = 0.
    total_direct = 0.
    work = dict(state_expansions=0, expanded_rows=0, cost_rows=0)
    for i, point in enumerate(points):
        t0 = time.perf_counter()
        choices, actual = compiled.query(point)
        pick = compiled.best_mapping(point)
        query_s = time.perf_counter()-t0
        t0 = time.perf_counter()
        independent, counts = oracle(program, instantiate_objectives(program, point))
        independent_costs = selected_costs(program, independent)
        expected = frontier(independent_costs)
        reconstruct_best(program,independent,independent_costs)
        enumeration_s = time.perf_counter()-t0
        # A separately constructed physical architecture validates the adapter,
        # not just two backends consuming the same normalized formula.
        t0 = time.perf_counter()
        direct = prepare(args.size, point, program.template_key)
        direct_choices, _ = oracle(direct)
        direct_costs = selected_costs(direct,direct_choices)
        direct_frontier = frontier(direct_costs)
        reconstruct_best(direct,direct_choices,direct_costs)
        direct_s = time.perf_counter()-t0
        checks = dict(tiles=np.array_equal(canonical_choices(choices), canonical_choices(independent)),
                      frontier=np.array_equal(actual,expected),
                      physical_tiles=np.array_equal(canonical_choices(choices),canonical_choices(direct_choices)),
                      physical_frontier=np.array_equal(actual,direct_frontier))
        # Validate every round's source/physical mapping outside ALL timers.
        # A later successful round must never overwrite an earlier failure.
        validation = validate_selected(case,point,pick)
        checks['reconstruction'] = validation['ok']
        total_query += query_s
        total_enum += enumeration_s
        total_direct += direct_s
        for key,value in counts.items():
            work[key] += value
        work['cost_rows'] += len(independent)
        record = dict(point=point, checks=checks, rows=len(choices), frontier=actual.tolist(),
                      reconstruction=validation,
                      query_s=query_s, strong_independent_s=enumeration_s, direct_physical_s=direct_s,
                      cumulative=dict(parametric_s=prepared_s+compile_s+total_query,
                                      strong_independent_s=prepared_s+total_enum,
                                      direct_physical_s=total_direct), independent_work=counts)
        report['queries'].append(record)
        save(args.output,report)
        if not all(checks.values()):
            np.savez(args.output.with_suffix('.mismatch.npz'),actual_tiles=choices,
                     independent_tiles=independent,physical_tiles=direct_choices,
                     actual_frontier=actual,physical_frontier=direct_frontier)
            raise AssertionError(f'parametric mismatch at {point}: {checks}')
        print(point, len(choices), checks, flush=True)
    report['summary'] = dict(all_match=True, queries=len(points), independent_work=work,
                            preprocess_s=prepared_s+compile_s, query_s=total_query,
                            strong_independent_s=prepared_s+total_enum, direct_physical_s=total_direct,
                            measured_break_even=next((i+1 for i,q in enumerate(report['queries'])
                                if q['cumulative']['parametric_s'] <= q['cumulative']['strong_independent_s']), None))
    save(args.output,report)
    print(json.dumps(report['summary']),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=256)
    p.add_argument('--min-capacity',type=int,default=32768)
    p.add_argument('--max-capacity',type=int,default=262144)
    p.add_argument('--queries',type=int,default=64)
    p.add_argument('--seed',type=int,default=731)
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args())
