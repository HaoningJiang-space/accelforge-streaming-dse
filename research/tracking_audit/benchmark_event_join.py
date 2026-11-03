"""Alternate finite-target backends and replay frozen Join inputs.

Fingerprints, deep copies, result serialization and Mapping re-evaluation are
outside wall timers. Instrumented Join replays are separate diagnostic runs.
Only load/run trusted local AccelForge inputs; snapshots remain in memory.
"""
import argparse
import copy
from dataclasses import fields, is_dataclass
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import common
from generation_profile import GenerationPhases


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def normalize(value):
    if is_dataclass(value):
        return {'type': type(value).__name__, **{f.name: normalize(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((normalize(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def numeric_signature(data, canonical=False):
    frame = data.select_dtypes(include=['number', 'bool'])
    if canonical:
        frame = frame[sorted(frame.columns)]
        if len(frame.columns):
            frame = frame.sort_values(list(frame.columns), kind='stable')
    h = hashlib.sha256()
    for column in frame:
        array = frame[column].to_numpy()
        h.update(json.dumps([column, array.dtype.str, array.shape]).encode())
        h.update(array.tobytes())
    return h.hexdigest()


def input_signature(pm):
    groups = []
    for einsum, candidates in pm.einsum2pmappings.items():
        mapping_ids = {uid: common.mapping_identity(m) for uid, m in pm.pmapping_objects[einsum].items()}
        for position, group in enumerate(candidates):
            data = group.mappings.data
            object_columns = {}
            for column in data:
                if data[column].dtype.kind == 'O':
                    object_columns[column] = [mapping_ids.get(v, str(v)) for v in data[column]]
            blocks = getattr(data._mgr, 'blocks', ())  # Pandas diagnostic, not a search dependency.
            groups.append(dict(
                einsum=str(einsum), position=position, rows=len(data),
                compatibility=normalize(group.compatibility),
                schema=[[c, str(data[c].dtype)] for c in data],
                ordered_numeric=numeric_signature(data), canonical_numeric=numeric_signature(data, True),
                provenance=digest(object_columns), index=digest(data.index.tolist()),
                blocks=[dict(dtype=str(b.dtype), shape=list(b.shape), columns=b.mgr_locs.as_array.tolist())
                        for b in blocks],
                total_estimate=group.mappings.n_total_pmappings,
                valid_estimate=group.mappings.n_valid_pmappings))
    return {'groups': groups, 'rows': sum(g['rows'] for g in groups),
            'group_sizes': sorted(g['rows'] for g in groups)}


def frontier_record(result):
    # Same final frontier convention as benchmark_symbolic_generation.py.
    numeric = result.data.select_dtypes(include='number')
    columns = sorted(numeric.columns)
    numeric = numeric[columns].drop_duplicates().sort_values(columns).reset_index(drop=True)
    return {'columns': columns, 'values': numeric.values.tolist()}


class JoinPhases(GenerationPhases):
    def __init__(self):
        super().__init__(common)
        join = importlib.import_module('accelforge.mapper.FFM._join_pmappings.join_pmappings')
        frame = importlib.import_module('accelforge.mapper.FFM._join_pmappings.pmapping_dataframe')
        pareto = importlib.import_module('accelforge.mapper.FFM._pareto_df.pareto')
        self.targets = [
            (common, 'join_pmappings', 'join_total'),
            (join, 'compress_einsum2pmappings', 'compress'),
            (join, 'join_pmappings', 'join_core'),
            (join, 'decompress_pmappings', 'decompress'),
            (frame.PmappingDataframe, 'merge_next', 'pair_join'),
            (frame, 'makepareto', 'dataframe_pareto'),
            (pareto, 'makepareto_numpy', 'numeric_pareto'),
        ]


def join_once(pm):
    common.clear_switches()
    os.environ['AF_VARIABLE_RESOURCES'] = 'GlobalBuffer'
    try:
        start = time.perf_counter()
        result = common.join_pmappings(pm)
        elapsed = time.perf_counter() - start
    finally:
        common.clear_switches()
    return result, elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--counts', type=int, default=64)
    args = parser.parse_args()
    if args.repeats < 1 or args.counts < 2:
        parser.error('repeats >= 1 and counts >= 2 are required')
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    case = common.Case('glu', 'nvdla', (64, 128, 256))
    caps = [.03125 * 8**(i / (args.counts - 1)) for i in range(args.counts)]
    caps[-1] = .25
    report = dict(case=str(case), caps=caps, repeats=args.repeats,
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  python=platform.python_version(), numpy=np.__version__, system=platform.platform(),
                  hashseed=os.environ.get('PYTHONHASHSEED'), jobs=1,
                  threads={k: os.environ.get(k) for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMBA_NUM_THREADS')},
                  warmups=[], searches=[], replays=[], profiles=[], inputs={}, frontiers={})
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, indent=2) + '\n')

    # Both methods receive a full untimed case-specific warmup before comparison.
    snapshots, last_results = {}, {}
    for repeat in range(-1, args.repeats):
        methods = ['independent', 'events'] if repeat % 2 == 0 else ['events', 'independent']
        for mode in methods:
            common.clear_switches()
            os.environ.update({**common.capacity_fractions_env(caps),
                               'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer',
                               'AF_TARGET_ENUMERATION': mode,
                               'AF_ENUMERATION_PREFIX_BYTES': '0',
                               'AF_ENUMERATION_PARETO_BYTES': '8388608' if mode == 'independent' else '0'})
            spec = common.build(case, max(caps), common.RU)
            start = time.perf_counter()
            pm = common.make_pmappings(spec, print_number_of_pmappings=False)
            make_s = time.perf_counter() - start
            # Join mutates input indices. Record a pre-Join snapshot outside timers.
            signature = input_signature(pm)
            input_key = digest(signature)
            report['inputs'].setdefault(input_key, signature)
            if repeat == args.repeats - 1:
                snapshots[mode] = copy.deepcopy(pm)
            result, join_s = join_once(pm)
            front = frontier_record(result)
            front_key = digest(front)
            report['frontiers'].setdefault(front_key, front)
            row = dict(repeat=repeat, mode=mode, make_s=make_s, join_s=join_s,
                       search_s=make_s + join_s, input=input_key, frontier=front_key,
                       rows_front=len(result.data))
            report['warmups' if repeat < 0 else 'searches'].append(row)
            last_results[mode] = result
            save()
            print('SEARCH', json.dumps(row), flush=True)

    for repeat in range(args.repeats):
        for mode in (['independent', 'events'] if repeat % 2 == 0 else ['events', 'independent']):
            # Freeze candidate ordering/provenance; copy before every replay.
            replay = copy.deepcopy(snapshots[mode])
            signature = input_signature(replay)
            key = digest(signature)
            report['inputs'].setdefault(key, signature)
            result, elapsed = join_once(replay)
            row = dict(repeat=repeat, source=mode, join_s=elapsed, input=key,
                       frontier=digest(frontier_record(result)))
            report['replays'].append(row)
            save()
            print('REPLAY', json.dumps(row), flush=True)

    for mode in ('independent', 'events'):
        replay = copy.deepcopy(snapshots[mode])
        with JoinPhases() as profile:
            result, elapsed = join_once(replay)
        report['profiles'].append(dict(source=mode, join_s=elapsed,
                                       phases=profile.snapshot(), frontier=digest(frontier_record(result))))
        save()
    report['picks'] = {}
    for mode, result in last_results.items():
        report['picks'][mode] = [common.check_pick(case, cap, common.best_row(
            common.rows_for_capacity(result.data, cap, max(caps)))) for cap in caps]
    report['all_picks_valid'] = all(p['ok'] for picks in report['picks'].values() for p in picks)
    report['exact_frontiers'] = len({r['frontier'] for key in ('searches', 'replays', 'profiles') for r in report[key]}) == 1
    report['summary'] = {}
    for mode in ('independent', 'events'):
        runs = [r for r in report['searches'] if r['mode'] == mode]
        report['summary'][mode] = {key: statistics.median(r[key] for r in runs) for key in ('make_s', 'join_s', 'search_s')}
        report['summary'][mode]['replay_join_median_s'] = statistics.median(
            r['join_s'] for r in report['replays'] if r['source'] == mode)
    report['peak_rss_gb'] = common.peak_rss_gb()
    save()
    print('SUMMARY', json.dumps(report['summary']), flush=True)
    return 0 if report['all_picks_valid'] and report['exact_frontiers'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
