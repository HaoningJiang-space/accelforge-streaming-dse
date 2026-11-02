"""Single-process tag 1.0 A/B test; require external timeout and RLIMIT_AS."""
import copy
import json
import os
from pathlib import Path
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

root = Path(__file__).resolve().parents[2]
af.set_n_parallel_jobs(1)
shape = [int(x) for x in os.environ.get('COMPARE_SHAPE', '32,64,128').split(',')]
pair_limit = int(os.environ.get('COMPARE_PAIR_LIMIT', '64'))
metrics = af.Metrics.ENERGY | af.Metrics.LATENCY
if '--resource-usage' in sys.argv:
    metrics |= af.Metrics.RESOURCE_USAGE
spec = af.Spec.from_yaml(root / 'examples/arches/tpu_v4i.yaml', root / 'research/streaming_join/glu_tag1.yaml',
                         jinja_parse_data=dict(zip(('M', 'G', 'C'), shape)))
spec.arch.find('GlobalBuffer').size = 0.5 * 1024 * 1024 * 8
spec.mapper.ffm.metrics = metrics
spec.mapper.ffm.max_pmapping_templates_per_einsum = int(os.environ.get('COMPARE_MAX_TEMPLATES', '1'))
start = time.perf_counter()
pm = make_pmappings(spec, print_number_of_pmappings=False)
make_s = time.perf_counter() - start
print('GENERATED', json.dumps({'shape': shape, 'max_templates_per_einsum': spec.mapper.ffm.max_pmapping_templates_per_einsum, 'make_s': make_s, 'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}), flush=True)

original = PmappingDataframe.merge_next
counts = {'chunks': 0, 'max_chunk_product': 0}

def measured(self, right, *args, **kwargs):
    if kwargs.get('_streaming_disabled'):
        counts['chunks'] += 1
        counts['max_chunk_product'] = max(counts['max_chunk_product'], len(self.data) * len(right.data))
    return original(self, right, *args, **kwargs)

PmappingDataframe.merge_next = measured

def run(limit):
    os.environ['AF_STREAMING_JOIN_PAIRS'] = str(limit)
    t = time.perf_counter()
    result = join_pmappings(copy.deepcopy(pm))
    return result.data, time.perf_counter() - t

baseline, baseline_s = run(0)
print('BASELINE', json.dumps({'join_s': baseline_s, 'n': len(baseline), 'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}), flush=True)
streamed, streaming_s = run(pair_limit)
columns = sorted(c for c in baseline.columns if c.startswith('Total<SEP>') and c != 'Total<SEP>mapping')
assert columns and columns == sorted(c for c in streamed.columns if c.startswith('Total<SEP>') and c != 'Total<SEP>mapping'), columns
assert len(baseline) == len(streamed), (len(baseline), len(streamed))
a = baseline[columns].sort_values(columns).to_numpy(dtype=float)
b = streamed[columns].sort_values(columns).to_numpy(dtype=float)
np.testing.assert_allclose(a, b, rtol=1e-12, atol=1e-20)
assert counts['chunks'] > 0, 'No streaming was exercised'
assert counts['max_chunk_product'] <= pair_limit, counts
print('COMPARISON', json.dumps({'resource_usage': bool(metrics & af.Metrics.RESOURCE_USAGE), 'shape': shape,
    'pair_limit': pair_limit, 'make_s': make_s, 'baseline_join_s': baseline_s,
    'streaming_join_s': streaming_s, 'rows': len(a), 'objective_columns': columns,
    'objectives_equal': True, 'peak_rss_kib_process_so_far': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    **counts}), flush=True)
