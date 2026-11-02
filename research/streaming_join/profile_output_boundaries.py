"""Profile exact FFM output Pareto boundary groups on a trusted capture."""
import copy
import json
import os
import pickle
import sys


def no_children(event, args):
    if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
        raise RuntimeError('Child processes disabled: ' + event)


sys.addaudithook(no_children)
import accelforge as af
from accelforge.mapper.FFM._pareto_df.df_convention import is_fused_loop_col, is_n_iterations_col

af.set_n_parallel_jobs(1)
os.environ['AF_STREAMING_JOIN_PAIRS'] = '0'
with open(os.environ['CAPTURE_FILE'], 'rb') as f:
    left, right, args, kwargs = pickle.load(f)
result = left.merge_next(right, *args, **kwargs).data
keys = [c for c in result.columns if is_fused_loop_col(c) and not is_n_iterations_col(c)]
if keys:
    sizes = result.groupby(keys, sort=False, dropna=False, observed=True).size().to_numpy()
else:
    sizes = [len(result)] if len(result) else []
print('BOUNDARIES', json.dumps({'rows': len(result), 'boundary_columns': keys, 'group_count': len(sizes),
    'group_max': int(max(sizes, default=0)), 'size_1_groups': int(sum(s == 1 for s in sizes)),
    'size_2_groups': int(sum(s == 2 for s in sizes)), 'size_3_to_10_groups': int(sum(3 <= s <= 10 for s in sizes)),
    'size_over_10_groups': int(sum(s > 10 for s in sizes)), 'largest_groups': sorted(map(int, sizes), reverse=True)[:20]}))
