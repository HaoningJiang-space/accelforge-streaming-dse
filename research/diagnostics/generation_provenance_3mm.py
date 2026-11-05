"""G1 only: retrospective whole-task value on the frozen native 3mm search."""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack, contextmanager
from functools import wraps
import hashlib
import importlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np

from research.diagnostics.profile_3mm_search import execute, snapshots
from research.tracking_audit import common


def tile_key(frame, symbols, einsum=None):
    """Column-wise extraction avoids iterrows' lossy mixed-float coercion."""
    columns = [f'{einsum}<SEP>{s}' if einsum is not None else s for s in symbols]
    if any(c not in frame for c in columns):
        raise AssertionError(f'lost original Tile symbols: {columns}')
    values = []
    for c in columns:
        a = frame[c].to_numpy()
        # Native concatenation can promote different templates' sparse symbol
        # columns to float. Accept only exactly represented small integers.
        if a.dtype.kind not in 'iu' and not (a.dtype.kind == 'f' and
            np.isfinite(a).all() and (np.abs(a) < 2**53).all() and (a == np.floor(a)).all()):
            raise AssertionError(f'Tile column must remain exact integral: {c}: {a.dtype}')
        values.append([int(x) for x in a])
    return list(zip(*values)) if columns else [()] * len(frame)


def task_value(tasks, batches, used_tiles, generation_s, total_s):
    """Post-hoc, whole-task deletion only; no per-row time apportionment."""
    used_tiles = set(used_tiles)
    useful = {t['id'] for t in tasks if used_tiles.intersection(t['tile_ids'])}
    dead = [t for t in tasks if t['id'] not in useful]
    dead_batches = [b for b in batches if not useful.intersection(b['task_ids'])]
    job_s = sum(t['evaluation_s'] for t in tasks)
    batch_s = sum(b['non_job_s'] for b in batches)
    unknown_s = generation_s - job_s - batch_s
    if unknown_s < -1e-6:
        raise AssertionError('generation timing attribution double counts')
    saving_s = sum(t['evaluation_s'] for t in dead) + sum(b['non_job_s'] for b in dead_batches)
    if not 0 <= saving_s <= generation_s + 1e-6 or total_s < generation_s:
        raise AssertionError('invalid whole-task upper estimate')
    return dict(tasks=len(tasks), tasks_with_final_descendants=len(useful),
        tasks_without_final_descendants=len(dead), batches=len(batches),
        wholly_unused_batches=len(dead_batches),
        model_rows=sum(len(t['tile_ids']) for t in tasks), used_generated_tiles=len(used_tiles),
        unused_model_rows=sum(len(t['tile_ids']) for t in tasks)-len(used_tiles),
        job_evaluation_s=job_s, batch_non_job_s=batch_s,
        uncredited_generation_s=max(0., unknown_s),
        unused_job_evaluation_s=sum(t['evaluation_s'] for t in dead),
        unused_batch_non_job_s=sum(b['non_job_s'] for b in dead_batches),
        posthoc_whole_task_saving_s=saving_s,
        posthoc_whole_task_generation_fraction=saving_s/generation_s,
        fixed_other_cost_speedup_projection=total_s/(total_s-saving_s),
        necessary_task_ids=sorted(useful), no_descendant_task_ids=[t['id'] for t in dead])


class GenerationProvenance:
    """Serial read-only sidecars; no metadata columns enter native Pareto/Join."""
    def __init__(self):
        self.target = None
        self.observer_s = 0.
        self.tasks = []
        self.batches = []
        self.by_uuid = {}
        self.tile_origins = {}
        self.local_rows = []
        self.compressed = {}
        self.roots = {}
        self.generation_s = 0.
        self.current = None

    @contextmanager
    def observe(self):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observer_s += time.perf_counter()-start

    def adjusted(self, start, observer_start):
        elapsed = time.perf_counter()-start-(self.observer_s-observer_start)
        if elapsed < 0:
            raise AssertionError('negative observer-corrected duration')
        return elapsed

    def __enter__(self):
        self.stack = ExitStack()
        jobs = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_pmappings_from_templates')
        tiles = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')
        pmapper = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings')
        compress = importlib.import_module('accelforge.mapper.FFM._join_pmappings.compress_pmappings')
        join = importlib.import_module('accelforge.mapper.FFM._join_pmappings.join_pmappings')
        original_job, original_batch = jobs.make_tile_shapes, pmapper.make_pmappings_from_templates
        original_gen, original_choices = common.make_pmappings, tiles.get_tile_shape_choices_for_targets
        original_compress, original_restore = compress._compress, join.restore_mappings

        def generation(*args, **kwargs):
            start, obs = time.perf_counter(), self.observer_s
            result = original_gen(*args, **kwargs)
            self.generation_s += self.adjusted(start, obs)
            return result

        def batch(jobs_with_similar_compatibilities):
            start, obs, first = time.perf_counter(), self.observer_s, len(self.tasks)
            result = original_batch(jobs_with_similar_compatibilities)
            elapsed = self.adjusted(start, obs)
            with self.observe():
                children = self.tasks[first:]
                non_job = elapsed-sum(t['evaluation_s'] for t in children)
                if non_job < -1e-6:
                    raise AssertionError('non-additive compatibility batch attribution')
                self.batches.append(dict(id=f'batch:{len(self.batches)}', target=repr(self.target),
                    task_ids=[t['id'] for t in children], non_job_s=max(0., non_job)))
            return result

        def evaluate(job):
            with self.observe():
                if self.current is not None or str(job.job_id) in self.by_uuid:
                    raise AssertionError('nested/repeated Job execution')
                task = dict(id=f'task:{len(self.tasks)}', native_job_uuid=str(job.job_id),
                    target=repr(self.target), einsum=str(job.einsum_name),
                    template=job.mapping.compact_str(), symbols=None, phases={}, tile_ids=[])
                self.tasks.append(task)
                self.by_uuid[str(job.job_id)] = task
                self.current = task
            start, obs = time.perf_counter(), self.observer_s
            try:
                result = original_job(job)
                task['evaluation_s'] = self.adjusted(start, obs)
                with self.observe():
                    if task['symbols'] is None:
                        raise AssertionError('missing Tile enumeration observation')
                    keys = tile_key(result[0], task['symbols'])
                    if len(set(keys)) != len(keys):
                        raise AssertionError('ambiguous duplicate Tile assignments')
                    task['_tile_lookup'] = {k:f'{task["id"]}:tile:{i}' for i,k in enumerate(keys)}
                    task['tile_assignments'] = [list(k) for k in keys]
                    task['tile_ids'] = list(task['_tile_lookup'].values())
                    self.tile_origins.update({tile:(task,key) for key,tile in task['_tile_lookup'].items()})
                return result
            finally:
                self.current = None

        def choices(**kwargs):
            result = original_choices(**kwargs)
            with self.observe():
                if self.current is None or self.current['native_job_uuid'] != str(kwargs['job'].job_id):
                    raise AssertionError('enumeration has no active Job')
                self.current['symbols'] = [s.name for s in kwargs['symbols']]
                self.current['enumerated_rows'] = len(result[0])
            return result

        def compressed(einsum_name, pmappings, start_index):
            result = original_compress(einsum_name, pmappings, start_index)
            with self.observe():
                data = pmappings.mappings.data
                col = f'{einsum_name}<SEP>mapping'
                # Group by native Job origin, retaining exact integer columns.
                for origin, frame in data.groupby(col, sort=False):
                    task = self.by_uuid[str(origin)]
                    keys = tile_key(frame, task['symbols'], str(einsum_name))
                    for index, key in zip(frame.index, keys):
                        tile = task['_tile_lookup'][key]
                        lookup = (repr(self.target), str(einsum_name), int(index))
                        if lookup in self.compressed:
                            raise AssertionError('duplicate compressed index')
                        self.compressed[lookup] = tile
                        self.local_rows.append(dict(target=lookup[0], einsum=lookup[1],
                            compressed_index=lookup[2], tile_id=tile, task_id=task['id']))
            return result

        def restore(pmappings, joined, decompress_data, einsum_names):
            with self.observe():
                data = joined.data
                columns = [f'{e}<SEP>compressed_index' for e in einsum_names]
                if any(c not in data or data[c].dtype.kind not in 'iu' for c in columns):
                    raise AssertionError('missing/inexact final compressed lineage')
                values = zip(*(data[c].tolist() for c in columns))
                roots = [tuple(self.compressed[(repr(self.target), str(e), int(i))]
                    for e,i in zip(einsum_names, row)) for row in values]
                self.roots[repr(self.target)] = roots
            result = original_restore(pmappings, joined, decompress_data, einsum_names)
            with self.observe():
                if list(result.data.index) != list(range(len(roots))):
                    raise AssertionError('unexpected final row reordering')
                # Check source identities and assignments after native decompression,
                # rather than relying on reset_index to certify row order.
                for column,e in enumerate(einsum_names):
                    source_col = f'{e}<SEP>mapping'
                    for position,root in enumerate(roots):
                        task,key = self.tile_origins[root[column]]
                        origin = next(k for k in pmappings.pmapping_objects[e]
                            if str(k)==task['native_job_uuid'])
                        if result.data[source_col].iloc[position] is not pmappings.pmapping_objects[e][origin]:
                            raise AssertionError('source identity changed during decompression')
                        if tile_key(result.data.iloc[position:position+1],task['symbols'],str(e)) != [key]:
                            raise AssertionError('Tile lineage changed during decompression')
            return result

        def phase(function, name):
            @wraps(function)
            def measured(*args, **kwargs):
                start, obs = time.perf_counter(), self.observer_s
                result = function(*args, **kwargs)
                elapsed = self.adjusted(start, obs)
                if self.current is not None:
                    self.current['phases'][name] = self.current['phases'].get(name, 0.)+elapsed
                return result
            return measured

        try:
            for owner, name, function in (
                (common, 'make_pmappings', generation),
                (pmapper, 'make_pmappings_from_templates', batch),
                (jobs, 'make_tile_shapes', evaluate),
                (tiles, 'get_tile_shape_choices_for_targets', choices),
                (compress, '_compress', compressed),
                (join, 'restore_mappings', restore),
            ):
                self.stack.enter_context(patch.object(owner, name, function))
            for name, label in (('run_model','symbolic_model'),
                ('get_tile_shape_choices_for_targets','target_dispatch'), ('compile_dict','output_compilation')):
                self.stack.enter_context(patch.object(tiles, name, phase(getattr(tiles,name),label)))
        except BaseException:
            self.stack.close()
            raise
        return self

    def __exit__(self, *exc):
        return self.stack.__exit__(*exc)

    def finish(self, outputs, total_s):
        sources = {}
        used = set()
        for point, frame in outputs.items():
            label = repr(((point[0],point[1]), (131072,135168)))
            roots = self.roots[label]
            rows = []
            for index in frame.index:
                tiles = roots[int(index)]
                used.update(tiles)
                rows.append(dict(returned_row=int(index), tile_ids=list(tiles)))
            sources[','.join(map(str,point))] = rows
        # Every Tile used in a complete frontier must have a generation origin.
        all_tiles = {v for t in self.tasks for v in t['tile_ids']}
        if not used.issubset(all_tiles):
            raise AssertionError('unknown final Tile origin')
        summary = task_value(self.tasks, self.batches, used, self.generation_s, total_s)
        local_counts = Counter(row['task_id'] for row in self.local_rows)
        stage_counts = Counter()
        stage_seconds = Counter()
        phase_seconds = defaultdict(lambda:dict(all_tasks_s=0., no_final_descendant_tasks_s=0.))
        by_target = {}
        for label in sorted({t['target'] for t in self.tasks}):
            tasks = [t for t in self.tasks if t['target']==label]
            alive = set(summary['necessary_task_ids'])
            by_target[label] = dict(tasks=len(tasks), necessary=sum(t['id'] in alive for t in tasks),
                evaluation_s=sum(t['evaluation_s'] for t in tasks),
                no_descendant_evaluation_s=sum(t['evaluation_s'] for t in tasks if t['id'] not in alive))
        for t in self.tasks:
            t['has_final_descendant'] = t['id'] in summary['necessary_task_ids']
            t['used_tile_ids'] = sorted(used.intersection(t['tile_ids']))
            t['local_join_input_row_occurrences'] = local_counts[t['id']]
            stage = ('frontier_descendant' if t['has_final_descendant'] else
                'no_model_rows' if not t['tile_ids'] else
                'no_local_join_rows' if not local_counts[t['id']] else 'join_rows_no_final_descendant')
            t['observed_stage_class'] = stage
            stage_counts[stage] += 1
            stage_seconds[stage] += t['evaluation_s']
            for name, seconds in t.get('phases',{}).items():
                phase_seconds[name]['all_tasks_s'] += seconds
                if not t['has_final_descendant']:
                    phase_seconds[name]['no_final_descendant_tasks_s'] += seconds
        public_tasks = [{k:v for k,v in t.items() if not k.startswith('_')} for t in self.tasks]
        return dict(summary=summary, by_shared_shape_target=by_target,
            generation_s=self.generation_s, observer_corrected_search_s=total_s,
            observer_bookkeeping_s=self.observer_s, tasks=public_tasks, batches=self.batches,
            observed_stage_classes=dict(counts=dict(stage_counts), job_evaluation_s=dict(stage_seconds)),
            nested_phase_attribution=dict(phase_seconds),
            compressed_local_rows=self.local_rows, final_sources=sources,
            used_tile_ids=sorted(used),
            scope='Post-hoc whole-task deletion estimate, not a safe pruning certificate or universal algorithmic upper bound. No row-proportional time credits; native equal-source folding retained.')


def worker(args):
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    warm, _ = execute('events_ru')
    expected = snapshots(warm, True)
    del warm
    reference = json.loads(args.reference.read_text())['frontiers']
    if expected != reference:
        raise AssertionError('unobserved warm-up differs from frozen reference')
    audit = GenerationProvenance()
    start = time.perf_counter()
    actual, _ = execute('events_ru', forensics=audit)
    wall = time.perf_counter()-start
    fronts = snapshots(actual, True)
    if fronts != expected:
        raise AssertionError('provenance observer changed complete numerical fronts')
    report = audit.finish(actual, wall-audit.observer_s)
    report.update(status='complete', exact_full_frontiers_match_reference=True,
        frontiers=fronts, instrumented_wall_s=wall, workers=1,
        reference=str(args.reference.relative_to(common.ROOT)),
        source_sha256={str(p.relative_to(common.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), Path(__file__).with_name('profile_3mm_search.py'))})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report['summary']), flush=True)


def matrix(args):
    args.output.mkdir(parents=True, exist_ok=True)
    reports = []
    for i in range(args.repeats):
        path = args.output/f'trial_{i+1}.json'
        env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
            MKL_NUM_THREADS='1', NUMBA_NUM_THREADS='1', PYTHONHASHSEED='0')
        command = [sys.executable, '-m', 'research.diagnostics.generation_provenance_3mm',
            '--worker', '--output', str(path), '--reference', str(args.reference)]
        with path.with_suffix('.log').open('w') as log:
            done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
        if done.returncode:
            raise RuntimeError(f'G1 trace failed; see {path.with_suffix(".log")}')
        report = json.loads(path.read_text())
        reports.append(report)
        print(json.dumps(dict(trial=i+1, **report['summary'])), flush=True)
    metrics = ('posthoc_whole_task_saving_s', 'posthoc_whole_task_generation_fraction',
        'fixed_other_cost_speedup_projection', 'unused_job_evaluation_s', 'unused_batch_non_job_s')
    summary = dict(status='complete', repeats=args.repeats, reference=str(args.reference),
        all_full_frontiers_equal=all(r['frontiers']==reports[0]['frontiers'] for r in reports),
        per_trial_summaries=[r['summary'] for r in reports],
        medians={k:statistics.median(r['summary'][k] for r in reports) for k in metrics},
        scope=reports[0]['scope'])
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path,
        default=common.ROOT/'research/diagnostics/results/search_cost_3mm/events_ru_1.json')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        raise ValueError('positive repeat count required')
    worker(args) if args.worker else matrix(args)


if __name__=='__main__':
    main()
