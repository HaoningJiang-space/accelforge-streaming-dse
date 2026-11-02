"""Compare optional incremental frontiers in one captured, complete FFM join."""
import copy
import json
import os
import pickle
import resource
import statistics
import sys
import time


def no_children(event, args):
    if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
        raise RuntimeError('Child processes disabled: ' + event)


sys.addaudithook(no_children)
import accelforge as af
import pandas as pd
from accelforge.mapper.FFM._pareto_df.df_convention import col_used_in_joining
import accelforge.mapper.FFM._join_pmappings.incremental_pareto as incremental

counts = {'fast_merges': 0, 'fallbacks': 0}
comparisons = {'cross_pairs': 0, 'overlap_groups': 0, 'old_rows_scanned': 0, 'new_rows_scanned': 0}
original = incremental.cross_frontier_frame
def counted(*args, **kwargs):
    result = original(*args, stats=comparisons, **kwargs)
    counts['fast_merges' if result is not None else 'fallbacks'] += 1
    return result
incremental.cross_frontier_frame = counted

af.set_n_parallel_jobs(1)
with open(os.environ['CAPTURE_FILE'], 'rb') as f:
    inputs = pickle.load(f)
pair_limit = int(os.environ.get('COMPARE_PAIR_LIMIT', '4096'))
os.environ['AF_STREAMING_JOIN_PAIRS'] = str(pair_limit)


def run(enabled):
    os.environ['AF_INCREMENTAL_PARETO'] = str(int(enabled))
    left, right, args, kwargs = copy.deepcopy(inputs)
    start = time.perf_counter()
    result = left.merge_next(right, *args, **kwargs)
    return result.data, time.perf_counter() - start


def verify(a, b):
    columns = sorted(c for c in a.columns if col_used_in_joining(c))
    assert columns == sorted(c for c in b.columns if col_used_in_joining(c))
    pd.testing.assert_frame_equal(a[columns].sort_values(columns).reset_index(drop=True),
                                  b[columns].sort_values(columns).reset_index(drop=True),
                                  check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-20)
    return len(a), len(columns)


base, base_warm = run(False)
incremental_result, incremental_warm = run(True)
rows, fields = verify(base, incremental_result)
times = {'general': [], 'incremental': []}
for i in range(3):
    outputs = {}
    for name in (('general', 'incremental') if i % 2 == 0 else ('incremental', 'general')):
        outputs[name], elapsed = run(name == 'incremental')
        times[name].append(elapsed)
    assert verify(outputs['general'], outputs['incremental']) == (rows, fields)
print('INCREMENTAL_JOIN', json.dumps({'pair_limit': pair_limit, 'scope': 'captured_complete_ffm_join',
    'warmup_s': {'general': base_warm, 'incremental': incremental_warm}, 'seconds': times,
    'median_s': {k: statistics.median(v) for k, v in times.items()}, 'rows': rows,
    'fields': fields, 'equal': True, **counts, 'cross_comparison_stats': comparisons, 'process_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
