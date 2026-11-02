"""Measure observable dataframe sizes for a trusted captured join.

Dataframe bytes are estimates, not process-wide peak or a complete accounting of
Pandas/NumPy scratch space. Run modes in separate bounded processes.
"""
import json
import os
import pickle
import resource
import sys
import time


def no_children(event, args):
    if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
        raise RuntimeError('Child processes disabled: ' + event)


sys.addaudithook(no_children)
import accelforge as af
import pandas as pd

af.set_n_parallel_jobs(1)
with open(os.environ['CAPTURE_FILE'], 'rb') as f:
    left, right, args, kwargs = pickle.load(f)
mode = os.environ.get('COMPARE_MODE', 'baseline')
if mode not in ('baseline', 'stream'):
    raise ValueError('COMPARE_MODE must be baseline or stream')
os.environ['AF_STREAMING_JOIN_PAIRS'] = '0' if mode == 'baseline' else os.environ.get('COMPARE_PAIR_LIMIT', '4096')


def bytes_of(df):
    return int(df.memory_usage(index=True, deep=True).sum())


def provenance_bytes(df):
    cols = [c for c in df.columns if 'mapping' in c.lower() or 'compressed_index' in c.lower()]
    return int(df[cols].memory_usage(index=True, deep=True).sum()) if cols else 0


observed = {'candidate_tables': 0, 'max_candidate_rows': 0, 'max_candidate_bytes': 0}
original_merge = pd.merge

def track_merge(*a, **kw):
    result = original_merge(*a, **kw)
    if kw.get('suffixes') in (['', '_RIGHT_MERGE'], ('', '_RIGHT_MERGE')):
        observed['candidate_tables'] += 1
        observed['max_candidate_rows'] = max(observed['max_candidate_rows'], len(result))
        observed['max_candidate_bytes'] = max(observed['max_candidate_bytes'], bytes_of(result))
    return result

input_bytes = bytes_of(left.data) + bytes_of(right.data)
input_provenance_bytes = provenance_bytes(left.data) + provenance_bytes(right.data)
pd.merge = track_merge
start = time.perf_counter()
try:
    result = left.merge_next(right, *args, **kwargs)
finally:
    pd.merge = original_merge
elapsed = time.perf_counter() - start
summary = {'mode':mode, 'left_rows':len(left.data), 'right_rows':len(right.data),
           'input_dataframe_bytes':input_bytes, 'input_provenance_bytes':input_provenance_bytes,
           'frontier_rows':len(result.data), 'frontier_dataframe_bytes':bytes_of(result.data),
           'frontier_provenance_bytes':provenance_bytes(result.data), 'join_s':elapsed,
           'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, **observed}
print('MEMORY', json.dumps(summary), flush=True)
