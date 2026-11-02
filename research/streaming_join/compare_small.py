"""Compare FFM joins in one process; invoke only with a hard process limit.

This script deliberately forbids subprocesses and configures one FFM job. The
caller must also set RLIMIT_AS, a timeout, and single-threaded BLAS settings.
"""
import copy
import json
import os
import resource
import sys
import time


def no_children(event, args):
    if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
        raise RuntimeError('Child processes disabled: ' + event)


sys.addaudithook(no_children)
import numpy as np
import accelforge as af
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe


af.set_n_parallel_jobs(1)
metrics = af.Metrics.ENERGY | af.Metrics.LATENCY
if '--resource-usage' in sys.argv:
    metrics |= af.Metrics.RESOURCE_USAGE
pair_limit = int(os.environ.get('COMPARE_PAIR_LIMIT', '128'))
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
glu = os.path.join(root, 'examples/workloads/transformers/_feedforward_types/glu_standalone.yaml')
spec = af.Spec.from_yaml(af.examples.arches.tpu_v4i, glu, jinja_parse_data={
    'BATCH_SIZE': 1, 'N_NEW_TOKENS': 128, 'N_HIDDEN_DIMS': 256, 'N_FF_DIMS': 512})
spec.arch.find('GlobalBuffer').size = 0.5 * 1024 * 1024 * 8
for action in spec.arch.find('MainMemory').actions:
    action.throughput_scale = 1.0
spec.mapper.metrics = metrics
start = time.perf_counter()
pm = make_pmappings(spec, print_progress=False)
make_s = time.perf_counter() - start
print('GENERATED', json.dumps({'make_s': make_s, 'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}), flush=True)

original_merge = PmappingDataframe.merge_next
counts = {'chunks': 0, 'max_chunk_product': 0}

def measured_merge(self, right, *args, **kwargs):
    if kwargs.get('_streaming_disabled'):
        counts['chunks'] += 1
        counts['max_chunk_product'] = max(counts['max_chunk_product'], len(self.data) * len(right.data))
    return original_merge(self, right, *args, **kwargs)

PmappingDataframe.merge_next = measured_merge

def run(limit):
    os.environ['AF_STREAMING_JOIN_PAIRS'] = str(limit)
    t = time.perf_counter()
    result = join_pmappings(copy.deepcopy(pm), metrics, print_progress=False)
    elapsed = time.perf_counter() - t
    return result.data, elapsed

baseline, baseline_s = run(0)
print('BASELINE', json.dumps({'join_s': baseline_s, 'n': len(baseline), 'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}), flush=True)
streamed, streaming_s = run(pair_limit)
columns = sorted(c for c in baseline.columns if c.startswith('Total<SEP>'))
assert columns and columns == sorted(c for c in streamed.columns if c.startswith('Total<SEP>'))
assert len(baseline) == len(streamed), (len(baseline), len(streamed))
a = baseline[columns].sort_values(columns).to_numpy(dtype=float)
b = streamed[columns].sort_values(columns).to_numpy(dtype=float)
np.testing.assert_allclose(a, b, rtol=1e-12, atol=1e-20)
assert counts['chunks'] > 0, 'No streaming was exercised'
assert counts['max_chunk_product'] <= pair_limit, counts
print('COMPARISON', json.dumps({'resource_usage': bool(metrics & af.Metrics.RESOURCE_USAGE),
    'shape': [128, 256, 512], 'pair_limit': pair_limit, 'make_s': make_s,
    'baseline_join_s': baseline_s, 'streaming_join_s': streaming_s,
    'rows': len(a), 'objective_columns': columns, 'objectives_equal': True,
    'peak_rss_kib_process_so_far': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    **counts}), flush=True)
