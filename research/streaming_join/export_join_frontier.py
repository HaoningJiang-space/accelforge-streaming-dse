"""Export one trusted fixture's join-relevant frontier for revision comparison."""
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
from accelforge.mapper.FFM._pareto_df.df_convention import col_used_in_joining

af.set_n_parallel_jobs(1)
with open(os.environ['CAPTURE_FILE'], 'rb') as f:
    left, right, args, kwargs = pickle.load(f)
start = time.perf_counter()
result = left.merge_next(right, *args, **kwargs)
columns = sorted(c for c in result.data.columns if col_used_in_joining(c))
frame = result.data[columns].sort_values(columns).reset_index(drop=True)
target = os.environ['FRONTIER_FILE']
with open(target + '.tmp', 'wb') as f:
    pickle.dump(frame, f, protocol=pickle.HIGHEST_PROTOCOL)
os.replace(target + '.tmp', target)
print('EXPORTED', json.dumps({'rows':len(frame), 'columns':columns,
    'elapsed_s':time.perf_counter()-start,
    'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}), flush=True)
