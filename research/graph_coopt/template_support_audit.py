"""Read-only pre-enumeration support overapproximation and actual work audit.

All original jobs execute. The abstraction permits every loop-deletion subset
and ignores rank/order/tile/resource-size restrictions. Thus missing support can
only be established in this relaxed direct-FFM-interface model, not by observing
which templates survive Pareto or win a complete search.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from dataclasses import asdict
import hashlib
import importlib
import json
from pathlib import Path
import time
from unittest.mock import patch

import pandas as pd
import sympy

from research.graph_coopt.workload_dag import WorkloadDAG
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build


def interface_key(compatibility, shared):
    """Necessary backing/count conditions; no sufficient Fusion contract."""
    by_name = {}
    for tensor in compatibility.tensors:
        if tensor.name in by_name:
            return None  # do not guess which duplicate is the backing copy
        by_name[tensor.name] = tensor
    if not set(shared).issubset(by_name):
        return None
    return tuple((name, by_name[name].resource_name, bool(by_name[name].persistent),
                  sum(not loop.is_spatial for loop in by_name[name].loops),
                  sum(loop.is_spatial for loop in by_name[name].loops))
                 for name in sorted(shared))


def possible_interfaces(compatibility, shared, max_patterns=128):
    """Overapproximate all unit-loop reductions; unknown is not an empty set.

    Legal loop permutations preserve per-tensor temporal/spatial counts. Dropping
    ranks/order, reservation indices, sizes and alias constraints only relaxes the
    predicate. Every subset is permitted even if impossible for actual tiles.
    """
    n = compatibility.n_loops
    if not shared or (1 << n) > max_patterns or interface_key(compatibility, shared) is None:
        return None
    result = set()
    for mask in range(1 << n):
        removed = [i for i in range(n) if not mask & (1 << (n - i - 1))]
        try:
            key = interface_key(compatibility.drop_loop_indices(removed), shared)
        except (ValueError, AssertionError, TypeError):
            return None
        if key is None:
            return None
        result.add(key)
    return frozenset(result)


def support_status(left, rights):
    if left is None:
        return 'unknown'
    if any(right is not None and left & right for right in rights):
        return 'possible_support'
    if any(right is None for right in rights):
        return 'unknown'
    # Requires a complete catalog of the mandatory neighbor's raw templates.
    return 'no_relaxed_support'


def observed_masks(job, result, template_module):
    if result.empty:
        return {}
    comp = job.compatibility.populate_loops()
    columns = {}
    for loop in comp.loops:
        value = loop.tile_pattern.calculated_n_iterations
        if isinstance(value, sympy.Symbol):
            value = value.name
        if isinstance(value, str):
            columns[f'{job.einsum_name}<SEP>{value}'] = result[value]
    prefixed = pd.DataFrame(columns, index=result.index)
    mask = template_module.get_fused_loop_indices(prefixed, comp, job.einsum_name, return_as_int=True)
    if isinstance(mask, int):
        return {mask: len(result)}
    return {int(k): int(v) for k, v in mask.value_counts().items()}


class SupportAudit:
    """Serial-only observer at _fill_jobs -> _allocate_jobs and tile evaluation."""
    def __init__(self, spec, max_patterns=128):
        self.dag = WorkloadDAG.from_workload(spec.workload)
        self.max_patterns = max_patterns
        self.records = {}
        self.compatibilities = {}
        self.relations = []
        self.pre_analysis_s = 0.
        self.inspection_s = 0.
        self.jobs_by_einsum = {}

    def before_allocate(self, jobs):
        started = time.perf_counter()
        if self.records:
            raise ValueError('an audit instance observes one complete generation only')
        for einsum, by_compatibility in jobs.items():
            self.jobs_by_einsum[str(einsum)] = []
            for job_list in by_compatibility.values():
                for job in job_list:
                    key = str(job.job_id)
                    comp = job.compatibility
                    self.compatibilities[key] = comp
                    self.jobs_by_einsum[str(einsum)].append(key)
                    self.records[key] = dict(template_id=key, einsum=str(einsum),
                        template_fingerprint=hashlib.sha256(job.mapping.compact_str().encode()).hexdigest(),
                        template=job.mapping.compact_str(), raw_fused_loops=[dict(
                            rank=str(loop.rank_name), spatial=loop.is_spatial) for loop in comp.loops],
                        raw_tensor_backings=[dict(tensor=str(t.name), resource=t.resource_name,
                            persistent=bool(t.persistent), loops=[dict(rank=str(loop.rank_name),
                                spatial=loop.is_spatial) for loop in t.loops])
                            for t in sorted(comp.tensors, key=lambda t: t.name)],
                        rank_bounds={str(k): int(v) for k, v in job.rank_variable_bounds.items()},
                        memories_track_all=sorted(job.memories_track_all),
                        memories_track_pmappings_only=sorted(job.memories_track_pmappings_only),
                        ignored_resources=sorted(job.ignored_resources),
                        evaluation_calls=0, tile_generation_s=0., output_rows=0,
                        observed_effective_loop_patterns={}, inspection_unknown=None,
                        neighbor_checks=[])
        # Direct data-dependency edges are mandatory; shared external inputs are
        # included in each pair's incidence, but do not create false DAG edges.
        for producer, consumer in sorted({(a, b) for a, b, _ in self.dag.edges}):
            shared = frozenset(t for t, users in self.dag.tensor_uses
                               if producer in users and consumer in users)
            for source, target in ((producer, consumer), (consumer, producer)):
                right_ids = self.jobs_by_einsum.get(target, [])
                rights = [possible_interfaces(self.compatibilities[k], shared, self.max_patterns) for k in right_ids]
                for key in self.jobs_by_einsum.get(source, []):
                    left = possible_interfaces(self.compatibilities[key], shared, self.max_patterns)
                    status = support_status(left, rights)
                    relation = dict(template_id=key, neighbor=target, shared_tensors=sorted(shared),
                                    status=status, relaxed_interface_count=None if left is None else len(left))
                    self.records[key]['neighbor_checks'].append(relation)
                    self.relations.append(relation)
        for record in self.records.values():
            checks = record['neighbor_checks']
            record['pre_status'] = ('no_relaxed_support' if any(c['status'] == 'no_relaxed_support' for c in checks)
                                    else 'unknown' if not checks or any(c['status'] == 'unknown' for c in checks)
                                    else 'possible_support')
        self.pre_analysis_s += time.perf_counter() - started

    def inspect_result(self, job, result, elapsed, template_module):
        started = time.perf_counter()
        record = self.records[str(job.job_id)]
        record['evaluation_calls'] += 1
        record['tile_generation_s'] += elapsed
        record['output_rows'] += len(result)
        try:
            masks = observed_masks(job, result, template_module)
            raw = self.compatibilities[str(job.job_id)]
            if raw.n_loops != job.compatibility.n_loops:
                raise ValueError('pre/post template loop count changed')
            for mask, count in masks.items():
                if mask < 0 or mask >= (1 << raw.n_loops):
                    raise ValueError('invalid observed loop mask')
                target = record['observed_effective_loop_patterns']
                target[str(mask)] = target.get(str(mask), 0) + count
            # This checks that the concrete normalized interface is covered by
            # the pre-analysis. It is not a complete numeric join oracle.
            for check in record['neighbor_checks']:
                predicted = possible_interfaces(raw, check['shared_tensors'], self.max_patterns)
                if predicted is None:
                    continue
                for mask in masks:
                    removed = [i for i in range(raw.n_loops) if not mask & (1 << (raw.n_loops - i - 1))]
                    key = interface_key(raw.drop_loop_indices(removed), check['shared_tensors'])
                    if key not in predicted:
                        raise AssertionError('observed interface escaped the pre-enumeration overapproximation')
        except (KeyError, ValueError, TypeError) as error:
            record['inspection_unknown'] = str(error)
        self.inspection_s += time.perf_counter() - started

    def observe(self):
        from accelforge.util import get_n_parallel_jobs
        if get_n_parallel_jobs() != 1:
            raise ValueError('template support audit requires exactly one worker')
        mapper = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings')
        template = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_pmappings_from_templates')
        allocate, tiles = mapper._allocate_jobs, template.make_tile_shapes
        stack = ExitStack()

        def allocation(jobs):
            self.before_allocate(jobs)
            return allocate(jobs)

        def evaluate(job):
            started = time.perf_counter()
            output = tiles(job)
            elapsed = time.perf_counter() - started
            self.inspect_result(job, output[0], elapsed, template)
            return output

        stack.enter_context(patch.object(mapper, '_allocate_jobs', allocation))
        stack.enter_context(patch.object(template, 'make_tile_shapes', evaluate))
        return stack

    def report(self):
        if any(r['evaluation_calls'] != 1 for r in self.records.values()):
            raise AssertionError('the audit must execute every original serial template exactly once')
        records = list(self.records.values())
        unsupported = [r for r in records if r['pre_status'] == 'no_relaxed_support']
        started = time.perf_counter()
        observed_without_witness = []
        for record in records:
            if not record['output_rows'] or record['inspection_unknown'] is not None:
                continue
            for check in record['neighbor_checks']:
                shared = check['shared_tensors']

                def concrete_keys(key):
                    r, raw = self.records[key], self.compatibilities[key]
                    if r['inspection_unknown'] is not None:
                        return None
                    keys = frozenset(interface_key(raw.drop_loop_indices(
                        [i for i in range(raw.n_loops) if not int(mask) & (1 << (raw.n_loops - i - 1))]), shared)
                        for mask in r['observed_effective_loop_patterns'])
                    return None if None in keys else keys

                peers = [concrete_keys(key) for key in self.jobs_by_einsum[check['neighbor']]]
                status = support_status(concrete_keys(record['template_id']), peers)
                check['observed_relaxed_status'] = status
                if status == 'no_relaxed_support':
                    observed_without_witness.append(record)
        observed_without_witness = {r['template_id']: r for r in observed_without_witness}.values()
        return dict(templates=records, pre_analysis_s=self.pre_analysis_s,
                    post_inspection_s=self.inspection_s,
                    post_support_analysis_s=time.perf_counter() - started,
                    summary=dict(templates=len(records), status_counts=dict(Counter(r['pre_status'] for r in records)),
                        templates_with_multiple_effective_patterns=sum(len(r['observed_effective_loop_patterns']) > 1 for r in records),
                        inspection_unknowns=sum(r['inspection_unknown'] is not None for r in records),
                        tile_generation_s=sum(r['tile_generation_s'] for r in records),
                        generation_s_spent_on_no_relaxed_support=sum(r['tile_generation_s'] for r in unsupported),
                        nonempty_templates_without_observed_relaxed_witness=len(observed_without_witness),
                        zero_output_templates=sum(r['output_rows'] == 0 for r in records),
                        raw_difference_s=sum(r['tile_generation_s'] for r in unsupported) - self.pre_analysis_s,
                        actual_skipped_jobs=0, numeric_support_proven=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--params', default='3,16,16')
    parser.add_argument('--shapes', default='4x8,8x4')
    parser.add_argument('--capacities-bytes', default='512,1024')
    parser.add_argument('--max-patterns', type=int, default=128)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    common.af.set_n_parallel_jobs(1)
    case = common.Case.parse('matmuls', 'nvdla', args.params)
    shapes = [tuple(map(int, s.split('x'))) for s in args.shapes.split(',')]
    capacities = sorted(set(map(int, args.capacities_bytes.split(','))))
    if args.max_patterns < 1 or not shapes or not capacities:
        raise ValueError('positive pattern budget, shapes and capacities required')
    runs = []
    for shape in shapes:
        for capacity in capacities:
            common.clear_switches()
            spec = build(case, shape, capacity, common.RU)
            audit = SupportAudit(spec, args.max_patterns)
            started = time.perf_counter()
            with audit.observe():
                pm = common.make_pmappings(spec, print_number_of_pmappings=False)
            runs.append(dict(shape=shape, capacity_bits=capacity * 8,
                generation_and_audit_s=time.perf_counter() - started,
                generation_contracts=[asdict(c) for c in pm.generation_contracts],
                final_local_rows=pm.n_pareto_optimal_pmappings(), **audit.report()))
    report = dict(scope='Read-only necessary-interface relaxation; every original template executes. Not a search speedup or proof of global Fusion feasibility.',
                  abstraction='All loop deletion subsets; backing resource/persistence and temporal/spatial counts only. Rank, order, aliases, tile values, sizes and global joint consistency relaxed.',
                  workload=str(case), runs=runs)
    report['max_patterns'] = args.max_patterns
    paths = [Path(__file__), common.ROOT/'accelforge/mapper/FFM/_make_pmappings/make_pmappings.py',
             common.ROOT/'accelforge/mapper/FFM/_make_pmappings/make_pmappings_from_templates/make_pmappings_from_templates.py']
    report['source_sha256'] = {str(p.relative_to(common.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps([dict(shape=r['shape'], capacity_bits=r['capacity_bits'], **r['summary']) for r in runs], indent=2))


if __name__ == '__main__':
    main()
