"""Replay one trusted capture; run with one job, timeout, and RLIMIT_AS."""
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
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.mapper.FFM._pareto_df.df_convention import col_used_in_joining

af.set_n_parallel_jobs(1)
with open(os.environ['CAPTURE_FILE'], 'rb') as f:
    original_left, original_right, args, kwargs = pickle.load(f)
limit = int(os.environ.get('COMPARE_PAIR_LIMIT', '4096'))
counts = {'chunks': 0, 'max_chunk_product': 0}
original = PmappingDataframe.merge_next

def measured(self, right, *a, **kw):
    if kw.get('_streaming_disabled'):
        counts['chunks'] += 1
        counts['max_chunk_product'] = max(counts['max_chunk_product'], len(self.data)*len(right.data))
    return original(self, right, *a, **kw)

PmappingDataframe.merge_next = measured

def run(pair_limit):
    os.environ['AF_STREAMING_JOIN_PAIRS'] = str(pair_limit)
    left, right, local_args, local_kwargs = copy.deepcopy((original_left, original_right, args, kwargs))
    start = time.perf_counter()
    result = left.merge_next(right, *local_args, **local_kwargs)
    return result.data, time.perf_counter()-start

# Warm both paths before timing; then alternate execution order.
base, warm_base_s = run(0)
stream, warm_stream_s = run(limit)
columns = sorted(c for c in base.columns if col_used_in_joining(c))

def verify(base, stream):
    assert columns == sorted(c for c in stream.columns if col_used_in_joining(c))
    left = base[columns].sort_values(columns).reset_index(drop=True)
    right = stream[columns].sort_values(columns).reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right, check_dtype=False, check_exact=False,
                                  rtol=1e-12, atol=1e-20)
    return len(left)

rows = verify(base, stream)
base_times, stream_times = [], []
for iteration in range(3):
    if iteration % 2 == 0:
        base, elapsed_base = run(0)
        stream, elapsed_stream = run(limit)
    else:
        stream, elapsed_stream = run(limit)
        base, elapsed_base = run(0)
    assert verify(base, stream) == rows
    base_times.append(elapsed_base)
    stream_times.append(elapsed_stream)
assert counts['chunks'] and counts['max_chunk_product'] <= limit, counts
print('REPLAY', json.dumps({'left_rows':len(original_left.data), 'right_rows':len(original_right.data),
    'pair_upper_bound':len(original_left.data)*len(original_right.data), 'pair_limit':limit,
    'warmup_baseline_s':warm_base_s, 'warmup_streaming_s':warm_stream_s,
    'baseline_seconds':base_times, 'streaming_seconds':stream_times,
    'baseline_median_s':statistics.median(base_times), 'streaming_median_s':statistics.median(stream_times),
    'frontier_rows':rows, 'checked_columns':columns, 'equal':True,
    'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    **counts}), flush=True)
