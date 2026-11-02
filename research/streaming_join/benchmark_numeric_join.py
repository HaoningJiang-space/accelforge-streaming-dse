"""Compare optional numeric execution in one captured, complete FFM join."""
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

af.set_n_parallel_jobs(1)
with open(os.environ['CAPTURE_FILE'], 'rb') as f:
    inputs = pickle.load(f)
pair_limit = int(os.environ.get('COMPARE_PAIR_LIMIT', '4096'))
os.environ['AF_STREAMING_JOIN_PAIRS'] = str(pair_limit)


def run(numeric):
    os.environ['AF_NUMERIC_JOIN'] = str(int(numeric))
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
numeric, numeric_warm = run(True)
rows, fields = verify(base, numeric)
times = {'pandas': [], 'numeric': []}
for i in range(3):
    outputs = {}
    for name in (('pandas', 'numeric') if i % 2 == 0 else ('numeric', 'pandas')):
        outputs[name], elapsed = run(name == 'numeric')
        times[name].append(elapsed)
    assert verify(outputs['pandas'], outputs['numeric']) == (rows, fields)
print('NUMERIC_JOIN', json.dumps({'pair_limit': pair_limit, 'scope': 'captured_complete_ffm_join',
    'warmup_s': {'pandas': base_warm, 'numeric': numeric_warm}, 'seconds': times,
    'median_s': {k: statistics.median(v) for k, v in times.items()}, 'rows': rows,
    'fields': fields, 'equal': True, 'process_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
