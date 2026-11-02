"""Inspect compatible join keys without materializing their Cartesian pairs."""
import inspect
import json
import os
import pickle
import sys


def no_children(event, args):
    if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
        raise RuntimeError('Child processes disabled: ' + event)


sys.addaudithook(no_children)
import pandas as pd
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe

with open(os.environ['CAPTURE_FILE'], 'rb') as f:
    left, right, args, kwargs = pickle.load(f)
b = inspect.signature(PmappingDataframe.merge_next).bind(left, right, *args, **kwargs)
b.apply_defaults()
cl, cr = b.arguments['compatibility_left'], b.arguments['compatibility_right']
left_match, right_match = [], []

def check(a, b, name):
    a, b = getattr(a.tile_pattern, name), getattr(b.tile_pattern, name)
    if isinstance(a, str) or isinstance(b, str):
        left_match.append(a)
        right_match.append(b)
    elif a != b:
        raise ValueError(f'mismatched {name}')

for name in cl.tensor_names & cr.tensor_names:
    ta, tb = cl.get_tensor_by_name(name), cr.get_tensor_by_name(name)
    for a, b in zip(ta.loops, tb.loops):
        check(a, b, 'initial_tile_shape')
        check(a, b, 'tile_shape')
for a, b in zip(cl.loops, cr.loops):
    check(a, b, 'calculated_n_iterations')

if left_match:
    assert len(set(left_match)) == len(left_match) and len(set(right_match)) == len(right_match), 'duplicate keys require special handling'
    la = left.data.groupby(left_match, dropna=False, sort=False).size().reset_index(name='left_count')
    rb = right.data.groupby(right_match, dropna=False, sort=False).size().reset_index(name='right_count')
    joined = pd.merge(la, rb, left_on=left_match, right_on=right_match, how='inner')
    sizes = joined['left_count'] * joined['right_count']
    matched = int(sizes.sum())
    largest = int(sizes.max()) if len(sizes) else 0
    groups = len(joined)
else:
    matched = len(left.data) * len(right.data)
    largest, groups = matched, int(bool(matched))
print(json.dumps({'left_rows':len(left.data), 'right_rows':len(right.data),
    'pair_upper_bound':len(left.data)*len(right.data), 'matched_pairs':matched,
    'matched_key_groups':groups, 'largest_key_group_pairs':largest,
    'left_keys':left_match, 'right_keys':right_match,
    'input_dataframe_bytes':int(left.data.memory_usage(index=True, deep=True).sum()
                                + right.data.memory_usage(index=True, deep=True).sum())}), flush=True)
