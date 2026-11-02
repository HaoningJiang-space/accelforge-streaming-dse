"""Instrument one trusted FFM Join after warmup; times are wall-clock estimates."""
import copy
import importlib
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

mod = importlib.import_module('accelforge.mapper.FFM._join_pmappings.pmapping_dataframe')
P = mod.PmappingDataframe
af.set_n_parallel_jobs(1)
with open(os.environ['CAPTURE_FILE'], 'rb') as f:
    original_left, original_right, args, kwargs = pickle.load(f)
mode = os.environ.get('COMPARE_MODE', 'stream')
if mode not in ('baseline', 'stream'):
    raise ValueError('COMPARE_MODE must be baseline or stream')
os.environ['AF_STREAMING_JOIN_PAIRS'] = '0' if mode == 'baseline' else os.environ.get('COMPARE_PAIR_LIMIT', '4096')

state = {'preparing':0, 'resource':0, 'merging':0}
counts = {}

def reset():
    counts.clear()
    counts.update({'prepare_s':0.0, 'key_partition_s':0.0, 'match_s':0.0,
                   'resource_s':0.0, 'column_add_s':0.0, 'local_pareto_s':0.0,
                   'frontier_merge_s':0.0, 'candidate_rows':0, 'candidate_tables':0,
                   'prepare_calls':0, 'frontier_merges':0})


def active():
    return not any(state.values())


def wrap_method(name, bucket, flag=None):
    original = getattr(P, name)
    def wrapped(*a, **kw):
        outer = active()
        if flag:
            state[flag] += 1
        start = time.perf_counter()
        try:
            return original(*a, **kw)
        finally:
            elapsed = time.perf_counter() - start
            if flag:
                state[flag] -= 1
            if outer:
                counts[bucket] += elapsed
                if bucket == 'prepare_s': counts['prepare_calls'] += 1
    setattr(P, name, wrapped)


reset()
wrap_method('_prepare_join_plan', 'prepare_s', 'preparing')
wrap_method('_prepare_column_operations', 'prepare_s', 'preparing')
wrap_method('_matching_pair_plan', 'key_partition_s', 'preparing')
for method in ('adjust_reservations','free_to_loop_index','shift_bottom_reservation_left',
               'limit_capacity','max_right_to_left'):
    wrap_method(method, 'resource_s', 'resource')
wrap_method('make_pareto', 'local_pareto_s')
original_concat = P.concat

def concat(*a, **kw):
    outer = active()
    state['merging'] += 1
    start = time.perf_counter()
    try:
        return original_concat(*a, **kw)
    finally:
        state['merging'] -= 1
        if outer:
            counts['frontier_merge_s'] += time.perf_counter()-start
            counts['frontier_merges'] += 1

P.concat = staticmethod(concat)
original_add = mod.add_to_col

def add(*a, **kw):
    outer = active()
    start = time.perf_counter()
    try:
        return original_add(*a, **kw)
    finally:
        if outer: counts['column_add_s'] += time.perf_counter()-start

mod.add_to_col = add
original_merge = pd.merge

def merge(*a, **kw):
    outer = active() and kw.get('suffixes') in (['', '_RIGHT_MERGE'], ('', '_RIGHT_MERGE'))
    start = time.perf_counter()
    result = original_merge(*a, **kw)
    if outer:
        counts['match_s'] += time.perf_counter()-start
        counts['candidate_rows'] += len(result)
        counts['candidate_tables'] += 1
    return result

pd.merge = merge

def run():
    left, right, local_args, local_kwargs = copy.deepcopy((original_left, original_right, args, kwargs))
    start = time.perf_counter()
    result = left.merge_next(right, *local_args, **local_kwargs)
    return result, time.perf_counter()-start

warm, warm_s = run()
reset()
result, elapsed = run()
assert len(result.data) == len(warm.data)
accounted = sum(counts[k] for k in ('prepare_s','key_partition_s','match_s','resource_s',
                                      'column_add_s','local_pareto_s','frontier_merge_s'))
print('PHASES',json.dumps({'mode':mode,'warmup_s':warm_s,'join_s':elapsed,
    'frontier_rows':len(result.data),'instrumented_sum_s':accounted,
    'other_s':elapsed-accounted,'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    **counts}),flush=True)
