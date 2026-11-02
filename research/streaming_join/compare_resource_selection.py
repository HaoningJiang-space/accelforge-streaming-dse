"""Compare selective resource retention with full and independent searches.

Invoke under one-job, child-process, memory and timeout restrictions. The
capacity sweep is intentionally small and does not prove general correctness.
"""
import copy
import json
import math
import os
from pathlib import Path
import sys
import statistics
import time


def no_children(event, args):
    if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
        raise RuntimeError('Child processes disabled: ' + event)


sys.addaudithook(no_children)
import accelforge as af
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings

root = Path(__file__).resolve().parents[2]
af.set_n_parallel_jobs(1)
os.environ.pop('AF_STREAMING_JOIN_PAIRS', None)
os.environ.pop('AF_VARIABLE_RESOURCES', None)
shape = [int(x) for x in os.environ.get('COMPARE_SHAPE', '64,128,256').split(',')]
capacities = [float(x) for x in os.environ.get('COMPARE_CAPACITIES_MIB', '0.03125,0.0625,0.125,0.25,0.5').split(',')]
max_capacity = max(capacities)
max_templates = int(os.environ.get('COMPARE_MAX_TEMPLATES', '1'))
energy_latency = af.Metrics.ENERGY | af.Metrics.LATENCY
resource_metrics = energy_latency | af.Metrics.RESOURCE_USAGE
reservation = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'


def build(capacity, metrics):
    spec = af.Spec.from_yaml(root / 'examples/arches/tpu_v4i.yaml', root / 'research/streaming_join/glu_tag1.yaml',
        jinja_parse_data=dict(zip(('M','G','C'),shape)))
    spec.arch.find('GlobalBuffer').size = capacity * 1024 * 1024 * 8
    spec.mapper.ffm.metrics = metrics
    spec.mapper.ffm.max_pmapping_templates_per_einsum = max_templates
    return spec


def make(spec):
    start = time.perf_counter()
    result = make_pmappings(spec, print_number_of_pmappings=False)
    return result, time.perf_counter() - start


def join(pm, variable=None):
    if variable:
        os.environ['AF_VARIABLE_RESOURCES'] = variable
    else:
        os.environ.pop('AF_VARIABLE_RESOURCES', None)
    start = time.perf_counter()
    result = join_pmappings(copy.deepcopy(pm))
    return result, time.perf_counter()-start


def best(data, capacity=None):
    if capacity is not None:
        assert reservation in data.columns, 'GLB resource dimension is missing'
        data = data[data[reservation] <= capacity / max_capacity * (1 + 1e-12)]
    if data.empty:
        return None
    i = (data['Total<SEP>energy'] * data['Total<SEP>latency']).idxmin()
    assert data.loc[i, 'Total<SEP>mapping']() is not None
    return float(data.loc[i, 'Total<SEP>energy'] * data.loc[i, 'Total<SEP>latency'])


pm, make_s = make(build(max_capacity, resource_metrics))
full, full_s = join(pm)
selective, selective_s = join(pm, 'GlobalBuffer')
removed = sorted(set(c for c in full.data.columns if c.startswith('reservation<SEP>')) -
                 set(c for c in selective.data.columns if c.startswith('reservation<SEP>')))
assert removed, 'No fixed resource was eliminated, so this is not a meaningful test'
print('SHARED', json.dumps({'shape':shape,'max_capacity_mib':max_capacity,
    'templates_per_einsum':max_templates,'make_s':make_s,'full_join_s':full_s,
    'selective_join_s':selective_s,'full_rows':len(full.data),'selective_rows':len(selective.data),
    'removed_reservation_columns':removed}), flush=True)

checks = []
for cap in capacities:
    ref, sel = best(full.data, cap), best(selective.data, cap)
    same = (ref is None and sel is None) or (ref is not None and sel is not None and math.isclose(ref, sel, rel_tol=1e-12, abs_tol=1e-20))
    record = {'capacity_mib':cap, 'full_edp':ref, 'selective_edp':sel, 'equal':same}
    checks.append(record)
    print('CAPACITY',json.dumps(record),flush=True)
assert all(c['equal'] for c in checks), 'Selective resource policy changed the shared-search optimum'
assert any(c['full_edp'] is not None for c in checks), 'No capacity produced a valid mapping'

# The initial full and selective runs serve as warmup. Alternate the execution
# order to avoid presenting a single cold/warm comparison as a speedup.
full_times, selective_times = [], []
repeats = int(os.environ.get('COMPARE_REPEATS', '3'))
for iteration in range(repeats):
    if iteration % 2 == 0:
        repeated_full, elapsed_full = join(pm)
        repeated_selective, elapsed_selective = join(pm, 'GlobalBuffer')
    else:
        repeated_selective, elapsed_selective = join(pm, 'GlobalBuffer')
        repeated_full, elapsed_full = join(pm)
    for cap in capacities:
        expected = next(c['full_edp'] for c in checks if c['capacity_mib'] == cap)
        for result in (repeated_full, repeated_selective):
            actual = best(result.data, cap)
            assert ((expected is None and actual is None) or
                    (expected is not None and actual is not None and math.isclose(expected, actual, rel_tol=1e-12, abs_tol=1e-20)))
    full_times.append(elapsed_full)
    selective_times.append(elapsed_selective)
print('TIMINGS',json.dumps({'full_seconds':full_times,'selective_seconds':selective_times,
      'full_median_s':statistics.median(full_times),
      'selective_median_s':statistics.median(selective_times)}),flush=True)

independent_ok = True
for cap in capacities:
    os.environ.pop('AF_VARIABLE_RESOURCES', None)
    try:
        independent_pm, gen_s = make(build(cap, energy_latency))
        independent, run_s = join(independent_pm)
        independent_best = best(independent.data)
        ref = next(c['full_edp'] for c in checks if c['capacity_mib'] == cap)
        same = ((ref is None and independent_best is None) or
                (ref is not None and independent_best is not None and math.isclose(ref, independent_best, rel_tol=1e-12, abs_tol=1e-20)))
        print('INDEPENDENT',json.dumps({'capacity_mib':cap,'independent_edp':independent_best,
              'shared_edp':ref,'equal':same,'make_s':gen_s,'join_s':run_s}),flush=True)
        independent_ok &= same
    except (ValueError, AssertionError) as exc:
        independent_ok = False
        print('INDEPENDENT_ERROR',json.dumps({'capacity_mib':cap,'error':str(exc)}),flush=True)
assert independent_ok, 'At least one independent search disagreed or failed'
