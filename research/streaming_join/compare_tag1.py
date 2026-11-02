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
glb_mib = float(os.environ.get('COMPARE_GLB_MIB', '0.5'))
spec.arch.find('GlobalBuffer').size = glb_mib * 1024 * 1024 * 8
spec.mapper.ffm.metrics = metrics
spec.mapper.ffm.max_pmapping_templates_per_einsum = int(os.environ.get('COMPARE_MAX_TEMPLATES', '1'))
start = time.perf_counter()
pm = make_pmappings(spec, print_number_of_pmappings=False)
make_s = time.perf_counter() - start
print('GENERATED', json.dumps({'shape': shape, 'max_templates_per_einsum': spec.mapper.ffm.max_pmapping_templates_per_einsum, 'make_s': make_s, 'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}), flush=True)

original = PmappingDataframe.merge_next
counts = {'chunks': 0, 'max_chunk_product': 0, 'empty_chunks': 0,
          'chunk_join_s': 0.0, 'frontier_merge_s': 0.0, 'frontier_merges': 0}
inside_stream = False

def measured(self, right, *args, **kwargs):
    if not kwargs.get('_streaming_disabled'):
        return original(self, right, *args, **kwargs)
    counts['chunks'] += 1
    counts['max_chunk_product'] = max(counts['max_chunk_product'], len(self.data) * len(right.data))
    start = time.perf_counter()
    result = original(self, right, *args, **kwargs)
    counts['chunk_join_s'] += time.perf_counter() - start
    counts['empty_chunks'] += len(result.data) == 0
    return result

original_stream = PmappingDataframe._merge_next_streaming
original_concat = PmappingDataframe.concat

def measured_stream(self, *args, **kwargs):
    global inside_stream
    inside_stream = True
    try:
        return original_stream(self, *args, **kwargs)
    finally:
        inside_stream = False

def measured_concat(*args, **kwargs):
    if not inside_stream:
        return original_concat(*args, **kwargs)
    start = time.perf_counter()
    result = original_concat(*args, **kwargs)
    counts['frontier_merge_s'] += time.perf_counter() - start
    counts['frontier_merges'] += 1
    return result

PmappingDataframe.merge_next = measured
PmappingDataframe._merge_next_streaming = measured_stream
PmappingDataframe.concat = staticmethod(measured_concat)

def run(limit):
    os.environ['AF_STREAMING_JOIN_PAIRS'] = str(limit)
    t = time.perf_counter()
    result = join_pmappings(copy.deepcopy(pm))
    return result.data, time.perf_counter() - t

mode = os.environ.get('COMPARE_MODE', 'paired')
if mode in {'baseline', 'stream'}:
    data, elapsed = run(0 if mode == 'baseline' else pair_limit)
    cols = sorted(c for c in data.columns if c.startswith('reservation<SEP>') or
                  (c.startswith('Total<SEP>') and c != 'Total<SEP>mapping'))
    assert cols and len(data)
    if metrics & af.Metrics.RESOURCE_USAGE:
        assert any(c.startswith('reservation<SEP>') for c in cols), cols
    if mode == 'stream':
        assert counts['chunks'] and counts['max_chunk_product'] <= pair_limit, counts
    best = (data['Total<SEP>energy'] * data['Total<SEP>latency']).idxmin()
    assert data.loc[best, 'Total<SEP>mapping']() is not None
    out = {'mode': mode, 'shape': shape, 'glb_mib': glb_mib, 'resource_usage': bool(metrics & af.Metrics.RESOURCE_USAGE),
           'max_templates_per_einsum': spec.mapper.ffm.max_pmapping_templates_per_einsum,
           'pair_limit': pair_limit, 'make_s': make_s, 'join_s': elapsed,
           'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           'columns': cols, 'values': data[cols].sort_values(cols).to_numpy(dtype=float).tolist(),
           'best_edp': float((data['Total<SEP>energy'] * data['Total<SEP>latency']).min()), **counts}
    target = os.environ['COMPARE_RESULT_PATH']
    with open(target + '.tmp', 'w') as f:
        json.dump(out, f)
    os.replace(target + '.tmp', target)
    print('RESULT', json.dumps({k: v for k, v in out.items() if k != 'values'}), flush=True)
    sys.exit(0)
if mode != 'paired':
    raise ValueError('COMPARE_MODE must be paired, baseline, or stream')

baseline, baseline_s = run(0)
print('BASELINE', json.dumps({'join_s': baseline_s, 'n': len(baseline), 'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}), flush=True)
streamed, streaming_s = run(pair_limit)
def comparison_columns(data):
    return sorted(c for c in data.columns if c.startswith('reservation<SEP>') or (c.startswith('Total<SEP>') and c != 'Total<SEP>mapping'))

columns = comparison_columns(baseline)
assert columns and columns == comparison_columns(streamed), columns
if metrics & af.Metrics.RESOURCE_USAGE:
    assert any(c.startswith('reservation<SEP>') for c in columns), columns
assert len(baseline) == len(streamed), (len(baseline), len(streamed))
a = baseline[columns].sort_values(columns).to_numpy(dtype=float)
b = streamed[columns].sort_values(columns).to_numpy(dtype=float)
np.testing.assert_allclose(a, b, rtol=1e-12, atol=1e-20)
assert counts['chunks'] > 0, 'No streaming was exercised'
assert counts['max_chunk_product'] <= pair_limit, counts
for data in (baseline, streamed):
    best = (data['Total<SEP>energy'] * data['Total<SEP>latency']).idxmin()
    assert data.loc[best, 'Total<SEP>mapping']() is not None
print('COMPARISON', json.dumps({'resource_usage': bool(metrics & af.Metrics.RESOURCE_USAGE), 'shape': shape,
    'pair_limit': pair_limit, 'make_s': make_s, 'baseline_join_s': baseline_s,
    'streaming_join_s': streaming_s, 'rows': len(a), 'objective_columns': columns,
    'objectives_equal': True, 'best_mapping_reconstructed': True, 'peak_rss_kib_process_so_far': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    **counts}), flush=True)
