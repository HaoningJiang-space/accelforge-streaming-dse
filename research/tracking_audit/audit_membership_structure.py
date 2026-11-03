"""Measure actual matched-pair membership sparsity and sampled capacity runs.

Diagnostics are deliberately separate from uninstrumented timing. Intervals here
are runs of declared target IDs, not proofs of continuous-capacity regions.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import common
from benchmark_membership import digest, input_stats, semantic_frontiers
from accelforge.mapper.FFM._pareto_df.capacity_membership import (
    decode_column, is_membership_col, validate_membership,
)


def interval_stats(frames):
    histogram, cardinalities, masks = Counter(), Counter(), set()
    nrows = 0
    for frame in frames:
        words = validate_membership(frame)
        keys = []
        for column in words:
            memory, labels = decode_column(column)
            if memory != 'GlobalBuffer':
                raise ValueError('this audit expects only GlobalBuffer membership')
            keys.extend((float(label), column, bit) for bit, label in enumerate(labels))
        previous = np.zeros(len(frame), dtype=bool)
        runs = np.zeros(len(frame), dtype=np.int64)
        count = np.zeros(len(frame), dtype=np.int64)
        for _, column, bit in sorted(keys):
            allowed = ((frame[column].to_numpy() >> np.uint64(bit)) & np.uint64(1)).astype(bool)
            runs += allowed & ~previous
            count += allowed
            previous = allowed
        histogram.update(map(int, runs))
        cardinalities.update(map(int, count))
        masks.update(tuple(map(int, row)) for row in frame[list(words)].to_numpy())
        nrows += len(frame)
    return dict(rows=nrows, sampled_run_histogram=dict(sorted(histogram.items())),
                target_cardinality_histogram=dict(sorted(cardinalities.items())),
                unique_masks=len(masks), max_sampled_runs=max(histogram, default=0))


@contextmanager
def trace_materialized_pairs():
    original = pd.merge
    records = []

    def merge(*args, **kwargs):
        frame = original(*args, **kwargs)
        words = [c for c in frame if is_membership_col(c) and not c.endswith('_RIGHT_MERGE')
                 and c + '_RIGHT_MERGE' in frame]
        if words:
            live = np.zeros(len(frame), dtype=bool)
            for column in words:
                live |= (frame[column].to_numpy() & frame[column + '_RIGHT_MERGE'].to_numpy()) != 0
            records.append(dict(matched_pairs=len(frame), no_common_target=int((~live).sum())))
        return frame

    pd.merge = merge
    try:
        yield records
    finally:
        pd.merge = original


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workload', choices=common.WORKLOADS, default='glu')
    p.add_argument('--arch', choices=common.ARCHES, default='nvdla')
    p.add_argument('--params', default='64,128,256')
    p.add_argument('--count', type=int, default=64)
    p.add_argument('--low', type=float, default=.03125)
    p.add_argument('--high', type=float, default=.25)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--generation-only', action='store_true', help='only measure input intervals, without Join/query evaluation')
    a = p.parse_args()
    if a.count < 2 or not 0 < a.low < a.high:
        p.error('count >= 2 and 0 < low < high required')
    case = common.Case.parse(a.workload, a.arch, a.params)
    caps = [a.low * (a.high / a.low)**(i / (a.count - 1)) for i in range(a.count)]
    caps[-1] = a.high
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    os.environ.update({**common.capacity_fractions_env(caps),
                       'AF_TARGET_ENUMERATION': 'events', 'AF_CAPACITY_MEMBERSHIP': 'bitset',
                       'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer'})
    start = time.perf_counter()
    pm = common.make_pmappings(common.build(case, a.high, common.RU), print_number_of_pmappings=False)
    generation_s = time.perf_counter() - start
    frames = [g.mappings.data for groups in pm.einsum2pmappings.values() for g in groups]
    report = dict(case=str(case), caps=caps, input=input_stats(pm),
                  input_intervals=interval_stats(frames), generation_s=generation_s,
                  parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    if a.generation_only:
        print(json.dumps(report['input_intervals']), flush=True)
        return 0
    common.clear_switches()
    os.environ.update({'AF_VARIABLE_RESOURCES': 'GlobalBuffer', 'AF_CAPACITY_MEMBERSHIP': 'bitset'})
    with trace_materialized_pairs() as pairs:
        start = time.perf_counter()
        result = common.join_pmappings(pm)
        report['instrumented_join_s'] = time.perf_counter() - start
    total = sum(r['matched_pairs'] for r in pairs)
    empty = sum(r['no_common_target'] for r in pairs)
    report.update(pair_joins=pairs, matched_pairs=total, no_common_target=empty,
                  rho_zero=empty / total if total else 0.,
                  output_intervals=interval_stats([result.data]))
    full, queries = semantic_frontiers(result.data, caps)
    report['boolean_frontier_digest'], report['query_frontier_digest'] = digest(full), digest(queries)
    report['picks'] = [common.check_pick(case, cap, common.best_row(
        common.rows_for_capacity(result.data, cap, a.high))) for cap in caps]
    report['all_picks_valid'] = all(p['ok'] for p in report['picks'])
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:report[k] for k in ('case','matched_pairs','no_common_target','rho_zero',
                                         'input_intervals','output_intervals','all_picks_valid')}), flush=True)
    return 0 if report['all_picks_valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
