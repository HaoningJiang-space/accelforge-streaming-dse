"""Compare one real JoinPlan's column additions on Pandas, NumPy and CUDA.

This is only the post-match column-addition stage. It does not implement tensor
alloc/free, feasibility, Pareto, multi-architecture masks, or a GPU Join.
Run only with trusted captures, one CPU thread and a small CuPy pool limit.
"""
import copy
import inspect
import json
import os
import pickle
import statistics
import sys
import time


def no_children(event, args):
    if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
        raise RuntimeError('Child processes disabled: ' + event)


sys.addaudithook(no_children)
import numpy as np
import pandas as pd
import cupy as cp
from accelforge.mapper.FFM._join_pmappings import pmapping_dataframe as mod
from accelforge.mapper.FFM._pareto_df.df_convention import is_fused_loop_col

with open(os.environ['CAPTURE_FILE'], 'rb') as f:
    left, right, args, kwargs = pickle.load(f)
bound = inspect.signature(mod.PmappingDataframe.merge_next).bind(left, right, *args, **kwargs)
bound.apply_defaults()
a = bound.arguments
plan = left._prepare_join_plan(right, a['shared_loop_index'], a['live_tensors'],
    a['still_live_reservations'], a['compatibility_left'], a['compatibility_right'], a['compatibility_joined'])
assert not plan['make_empty_result']
if plan['left_match']:
    df = pd.merge(left.data, right.data, how='inner', left_on=plan['left_match'],
                  right_on=plan['right_match'], suffixes=['', '_RIGHT_MERGE'])
else:
    df = pd.merge(left.data, right.data, how='cross', suffixes=['', '_RIGHT_MERGE'])
df = df.drop(columns=[c for c in df.columns if is_fused_loop_col(c) and c not in plan['remaining_symbols']])
limit = int(os.environ.get('BENCH_MAX_ROWS', '20000'))
if len(df) > limit:
    raise ValueError(f'fixture has {len(df)} matched rows, exceeding BENCH_MAX_ROWS={limit}')
operations, _ = left._prepare_column_operations(right, df, plan['max_nloops'], plan['min_nloops'])
assert operations and len(df)

# Compile names into column IDs, preserving intermediate columns created by
# the original add_to_col operation and its dtype-promotion semantics.
names, ids = [], {}
def add_id(name):
    if name not in ids:
        ids[name] = len(names)
        names.append(name)
    return ids[name]
for target, source in operations:
    add_id(source)
    add_id(target)
steps = np.asarray([(ids[target], ids[source]) for target,source in operations], dtype=np.int32)
initial = []
for name in names:
    if name not in df:
        initial.append(None)
        continue
    arr = np.ascontiguousarray(df[name].to_numpy(copy=True))
    if arr.dtype.kind not in 'biuf':
        raise TypeError(f'non-numeric operation column {name}: {arr.dtype}')
    initial.append(arr)


def compute(xp, arrays):
    for target, source in steps:
        target, source = int(target), int(source)
        if arrays[source] is None:
            raise ValueError(f'source column missing for operation {source}')
        if arrays[target] is None:
            arrays[target] = arrays[source].copy()
            continue
        if arrays[target].dtype != arrays[source].dtype:
            arrays[target] = arrays[target].astype(xp.float64)
            arrays[source] = arrays[source].astype(xp.float64)
        arrays[target] = arrays[target] + arrays[source]
    return arrays


def pandas_run():
    start=time.perf_counter()
    result=df.copy()
    for target,source in operations:
        mod.add_to_col(result,target,source)
    return result,time.perf_counter()-start


def numpy_run():
    start=time.perf_counter()
    arrays=[None if x is None else x.copy() for x in initial]
    compute(np, arrays)
    return arrays,time.perf_counter()-start


def gpu_run():
    start=time.perf_counter()
    arrays=[None if x is None else cp.asarray(x) for x in initial]
    cp.cuda.Stream.null.synchronize()
    uploaded=time.perf_counter()
    compute(cp, arrays)
    cp.cuda.Stream.null.synchronize()
    computed=time.perf_counter()
    result=[None if x is None else cp.asnumpy(x) for x in arrays]
    cp.cuda.Stream.null.synchronize()
    downloaded=time.perf_counter()
    return result, {'upload_s':uploaded-start,'compute_s':computed-uploaded,
                    'download_s':downloaded-computed,'total_s':downloaded-start,
                    'pool_used_bytes':int(cp.get_default_memory_pool().used_bytes()),
                    'pool_total_bytes':int(cp.get_default_memory_pool().total_bytes())}


def verify(reference, arrays):
    for name, arr in zip(names, arrays):
        assert arr is not None and name in reference
        expected = reference[name].to_numpy()
        if expected.dtype.kind in 'biu' and arr.dtype.kind in 'biu':
            np.testing.assert_array_equal(expected, arr, err_msg=name)
        else:
            np.testing.assert_allclose(expected.astype(float), arr.astype(float),
                                       rtol=1e-12, atol=1e-20, equal_nan=True, err_msg=name)

# Record post-context available memory; context and libraries may allocate GPU
# memory outside CuPy's pool limit. All times include per-run copies.
free_before,total_memory=cp.cuda.runtime.memGetInfo()
reference, _ = pandas_run()
numpy_result, _ = numpy_run()
gpu_result, _ = gpu_run()
verify(reference,numpy_result)
verify(reference,gpu_result)
pandas_times,numpy_times,gpu_times=[],[],[]
for iteration in range(3):
    if iteration % 2:
        gpu_result,gpu_t = gpu_run()
        numpy_result,numpy_t = numpy_run()
    else:
        numpy_result,numpy_t = numpy_run()
        gpu_result,gpu_t = gpu_run()
    reference,pandas_t = pandas_run()
    verify(reference,numpy_result)
    verify(reference,gpu_result)
    pandas_times.append(pandas_t)
    numpy_times.append(numpy_t)
    gpu_times.append(gpu_t)
free_after,_=cp.cuda.runtime.memGetInfo()
print('NUMERIC_PLAN',json.dumps({'scope':'prepared_column_additions_only',
    'matched_rows':len(df),'operations':len(steps),'numeric_columns':len(names),
    'input_bytes':sum(x.nbytes for x in initial if x is not None),
    'pandas_seconds':pandas_times,'numpy_seconds':numpy_times,'gpu_runs':gpu_times,
    'pandas_median_s':statistics.median(pandas_times),'numpy_median_s':statistics.median(numpy_times),
    'gpu_total_median_s':statistics.median(x['total_s'] for x in gpu_times),
    'device_free_before':int(free_before),'device_free_after':int(free_after),
    'device_total':int(total_memory),'cupy_pool_limit_bytes':int(cp.get_default_memory_pool().get_limit()),
    'equal':True}),flush=True)
