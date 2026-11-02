"""Warm, alternate and compare independent vs shared capacity DSE.

Runs one process with child creation disabled. Invoke under a hard address-space
limit, external timeout, and single-threaded numerical libraries.
"""
import copy
import gc
import json
import math
import os
from pathlib import Path
import resource
import statistics
import sys
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
shape = [int(x) for x in os.environ.get('COMPARE_SHAPE', '512,1024,2048').split(',')]
capacities = [float(x) for x in os.environ.get('COMPARE_CAPACITIES_MIB', '2,4,8').split(',')]
max_capacity = max(capacities)
max_templates = int(os.environ.get('COMPARE_MAX_TEMPLATES', '2'))
repeats = int(os.environ.get('COMPARE_REPEATS', '3'))
assert repeats > 0
energy_latency = af.Metrics.ENERGY | af.Metrics.LATENCY
resource_metrics = energy_latency | af.Metrics.RESOURCE_USAGE
reservation = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'


def build(capacity, metrics):
    spec = af.Spec.from_yaml(root/'examples/arches/tpu_v4i.yaml', root/'research/streaming_join/glu_tag1.yaml',
        jinja_parse_data=dict(zip(('M','G','C'),shape)))
    spec.arch.find('GlobalBuffer').size = capacity * 1024 * 1024 * 8
    spec.mapper.ffm.metrics = metrics
    spec.mapper.ffm.max_pmapping_templates_per_einsum = max_templates
    return spec


def best(data, cap=None):
    if cap is not None:
        assert reservation in data.columns
        data = data[data[reservation] <= cap/max_capacity*(1+1e-12)]
    if data.empty:
        raise ValueError(f'no candidate for capacity {cap}')
    i = (data['Total<SEP>energy'] * data['Total<SEP>latency']).idxmin()
    assert data.loc[i, 'Total<SEP>mapping']() is not None
    return float(data.loc[i, 'Total<SEP>energy'] * data.loc[i, 'Total<SEP>latency'])


def independent():
    os.environ.pop('AF_VARIABLE_RESOURCES', None)
    start=time.perf_counter()
    edps=[]
    for cap in capacities:
        spec=build(cap, energy_latency)
        pm=make_pmappings(spec, print_number_of_pmappings=False)
        result=join_pmappings(pm)
        edps.append(best(result.data))
        del result, pm, spec
        gc.collect()
    return edps,time.perf_counter()-start


def shared():
    os.environ.pop('AF_VARIABLE_RESOURCES', None)
    start=time.perf_counter()
    spec=build(max_capacity, resource_metrics)
    pm=make_pmappings(spec, print_number_of_pmappings=False)
    os.environ['AF_VARIABLE_RESOURCES']='GlobalBuffer'
    result=join_pmappings(pm)
    edps=[best(result.data, cap) for cap in capacities]
    rows=len(result.data)
    os.environ.pop('AF_VARIABLE_RESOURCES', None)
    del result,pm,spec
    gc.collect()
    return edps,time.perf_counter()-start,rows

# Both paths are warmed before the recorded runs.
warm_independent,warm_independent_s=independent()
warm_shared,warm_shared_s,warm_rows=shared()
assert all(math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-20) for x,y in zip(warm_independent,warm_shared)), (warm_independent,warm_shared)
print('WARMUP',json.dumps({'independent_s':warm_independent_s,'shared_s':warm_shared_s,
    'edps':warm_shared,'shared_rows':warm_rows}),flush=True)
independent_times,shared_times=[],[]
for i in range(repeats):
    if i%2==0:
        a,ta=independent()
        b,tb,rows=shared()
    else:
        b,tb,rows=shared()
        a,ta=independent()
    assert len(a)==len(b)==len(capacities)
    assert all(math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-20) for x,y in zip(a,b)), (a,b)
    independent_times.append(ta)
    shared_times.append(tb)
    print('TRIAL',json.dumps({'index':i,'independent_s':ta,'shared_s':tb,'edps':b,'shared_rows':rows}),flush=True)
print('DSE',json.dumps({'shape':shape,'capacities_mib':capacities,'templates_per_einsum':max_templates,
    'independent_seconds':independent_times,'shared_seconds':shared_times,
    'independent_median_s':statistics.median(independent_times),'shared_median_s':statistics.median(shared_times),
    'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    'all_edps_equal':True,'fixed_bandwidth':True}),flush=True)
