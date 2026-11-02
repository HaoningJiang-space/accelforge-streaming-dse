"""Compare original and three streaming paths on one trusted captured Join."""
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
from accelforge.mapper.FFM._join_pmappings.boundary_frontier import BoundaryFrontier
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe

af.set_n_parallel_jobs(1)
with open(os.environ['CAPTURE_FILE'], 'rb') as f:
    inputs = pickle.load(f)
limit = int(os.environ.get('COMPARE_PAIR_LIMIT', '4096'))
repeats = int(os.environ.get('COMPARE_REPEATS', '3'))
counts = {'stores':0, 'new_groups':0, 'touched_groups':0, 'old_rows_scanned':0,
          'new_rows_scanned':0, 'cross_pairs':0, 'overlap_groups':0, 'fallbacks':0}
original_init, original_add = BoundaryFrontier.__init__, BoundaryFrontier.add
original_merge = PmappingDataframe.merge_next
chunk_counts = {name: 0 for name in ('original','stream','incremental','partitioned')}
mode_name = None

def measured_merge(self, right, *args, **kwargs):
    if kwargs.get('_streaming_disabled'):
        chunk_counts[mode_name] += 1
    return original_merge(self, right, *args, **kwargs)
PmappingDataframe.merge_next = measured_merge

def measured_init(self, *args, **kwargs):
    counts['stores'] += 1
    return original_init(self, stats=counts)

def measured_add(self, data):
    ok = original_add(self, data)
    if not ok: counts['fallbacks'] += 1
    return ok
BoundaryFrontier.__init__, BoundaryFrontier.add = measured_init, measured_add


def run(mode):
    global mode_name
    mode_name = mode
    os.environ['AF_STREAMING_JOIN_PAIRS'] = str(0 if mode == 'original' else limit)
    os.environ['AF_INCREMENTAL_PARETO'] = str(int(mode == 'incremental'))
    os.environ['AF_PARTITIONED_FRONTIER'] = str(int(mode == 'partitioned'))
    left, right, args, kwargs = copy.deepcopy(inputs)
    start = time.perf_counter()
    output = left.merge_next(right, *args, **kwargs)
    return output.data, time.perf_counter() - start


def verify(a, b):
    columns = sorted(c for c in a.columns if col_used_in_joining(c))
    assert columns == sorted(c for c in b.columns if col_used_in_joining(c))
    pd.testing.assert_frame_equal(a[columns].sort_values(columns).reset_index(drop=True),
        b[columns].sort_values(columns).reset_index(drop=True), check_dtype=False,
        check_exact=False, rtol=1e-12, atol=1e-20)
    return len(a), len(columns)

modes = ['original','stream','incremental','partitioned']
warm = {mode:run(mode) for mode in modes}
reference = warm['original'][0]
rows, fields = verify(reference, reference)
for data, elapsed in warm.values(): verify(reference, data)
times = {mode:[] for mode in modes}
for i in range(repeats):
    for mode in (modes if i % 2 == 0 else modes[::-1]):
        data, elapsed = run(mode)
        verify(reference, data)
        times[mode].append(elapsed)
print('BOUNDARY_BENCH', json.dumps({'pair_limit':limit, 'warmup_s':{k:v[1] for k,v in warm.items()},
    'seconds':times, 'median_s':{k:statistics.median(v) for k,v in times.items()},
    'rows':rows, 'fields':fields, 'equal':True, 'chunks_including_warmup':chunk_counts, 'partitioned_counts_including_warmup':counts,
    'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}), flush=True)
