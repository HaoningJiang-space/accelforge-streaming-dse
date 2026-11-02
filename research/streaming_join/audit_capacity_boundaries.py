"""Re-evaluate independently and shared-selected mappings at capacity boundaries.

The default tests 2 and 3 MiB +/- one byte on the recorded GLU setup.
Use an external timeout and address-space limit on shared systems.
"""
import copy
import json
import math
import os
from pathlib import Path
import sys


def no_children(event, args):
    if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
        raise RuntimeError('Child processes disabled: ' + event)


sys.addaudithook(no_children)
import accelforge as af
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings
from accelforge.model.main import evaluate_mapping

root = Path(__file__).resolve().parents[2]
af.set_n_parallel_jobs(1)
os.environ.pop('AF_STREAMING_JOIN_PAIRS', None)
os.environ.pop('AF_INCREMENTAL_PARETO', None)
os.environ.pop('AF_VARIABLE_RESOURCES', None)
shape = [int(x) for x in os.getenv('COMPARE_SHAPE', '512,1024,2048').split(',')]
max_bytes = 8 * 1024 * 1024
boundaries = [int(x) for x in os.getenv('COMPARE_BOUNDARIES_BYTES', '2097152,3145728').split(',')]
templates = int(os.getenv('COMPARE_MAX_TEMPLATES', '2'))
energy_latency = af.Metrics.ENERGY | af.Metrics.LATENCY
resource_metrics = energy_latency | af.Metrics.RESOURCE_USAGE
reservation = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'


def build(size_bytes, metrics):
    spec = af.Spec.from_yaml(root/'examples/arches/tpu_v4i.yaml', root/'research/streaming_join/glu_tag1.yaml',
                             jinja_parse_data=dict(zip(('M','G','C'), shape)))
    spec.arch.find('GlobalBuffer').size = size_bytes * 8
    spec.mapper.ffm.metrics = metrics
    spec.mapper.ffm.max_pmapping_templates_per_einsum = templates
    return spec


def search(spec):
    return join_pmappings(make_pmappings(spec, print_number_of_pmappings=False))


def get_best(df):
    if df.empty:
        return None
    return df.loc[(df['Total<SEP>energy'] * df['Total<SEP>latency']).idxmin()]


def reevaluate(row, size_bytes):
    result = {'status': 'not_attempted'}
    try:
        spec = build(size_bytes, resource_metrics)
        spec.model.metrics = resource_metrics
        spec.mapping = copy.deepcopy(row['Total<SEP>mapping']())
        evaluated = evaluate_mapping(spec).data
        if len(evaluated) != 1:
            return {'status':'unexpected_rows', 'rows': len(evaluated)}
        erow = evaluated.iloc[0]
        expected_e, expected_t = float(row['Total<SEP>energy']), float(row['Total<SEP>latency'])
        actual_e, actual_t = float(erow['Total<SEP>energy']), float(erow['Total<SEP>latency'])
        resources = {str(c): float(erow[c]) for c in evaluated.columns if c.startswith('reservation<SEP>')}
        cost_equal = (math.isclose(expected_e, actual_e, rel_tol=1e-6, abs_tol=1e-20) and
                      math.isclose(expected_t, actual_t, rel_tol=1e-6, abs_tol=1e-20))
        valid = all(v <= 1 + 1e-12 for v in resources.values())
        result = {'status': 'ok' if cost_equal and valid else 'mismatch', 'ffm_energy':expected_e,
                  'ffm_latency':expected_t, 'model_energy':actual_e, 'model_latency':actual_t,
                  'cost_equal_1e-6':cost_equal, 'resources':resources, 'resources_valid':valid}
    except Exception as exc:
        result = {'status':'error', 'exception':type(exc).__name__, 'message':str(exc)}
    return result


# Selective shared search at max capacity, preserving the GLB trade-off.
os.environ['AF_VARIABLE_RESOURCES'] = 'GlobalBuffer'
shared = search(build(max_bytes, resource_metrics))
os.environ.pop('AF_VARIABLE_RESOURCES', None)
print('SHARED', json.dumps({'rows':len(shared.data), 'max_bytes':max_bytes}), flush=True)
all_results=[]
for boundary in boundaries:
    for delta in (-1,0,1):
        size_bytes=boundary+delta
        selected = get_best(shared.data[shared.data[reservation] <= size_bytes/max_bytes])
        item={'boundary_bytes':boundary, 'delta_bytes':delta, 'capacity_bytes':size_bytes}
        try:
            independent = search(build(size_bytes, energy_latency))
            independent_best = get_best(independent.data)
            if selected is None or independent_best is None:
                item.update(status='missing_candidate', shared_available=selected is not None,
                            independent_available=independent_best is not None)
            else:
                a = float(selected['Total<SEP>energy']*selected['Total<SEP>latency'])
                b = float(independent_best['Total<SEP>energy']*independent_best['Total<SEP>latency'])
                item.update(status='compared', shared_edp=a, independent_edp=b,
                            edp_equal=math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-20),
                            shared_reservation_at_max=float(selected[reservation]),
                            shared_model=reevaluate(selected,size_bytes),
                            independent_model=reevaluate(independent_best,size_bytes))
        except Exception as exc:
            item.update(status='error', exception=type(exc).__name__, message=str(exc))
        all_results.append(item)
        # Each case is emitted immediately, even if a later run is interrupted.
        print('BOUNDARY_CASE', json.dumps(item), flush=True)
print('BOUNDARY_AUDIT', json.dumps({'shape':shape, 'templates_per_einsum':templates,
    'fixed_bandwidth':True, 'cases':all_results}), flush=True)

if any(case.get('status') != 'compared' or not case.get('edp_equal') or
       case.get('shared_model', {}).get('status') != 'ok' or
       case.get('independent_model', {}).get('status') != 'ok' for case in all_results):
    raise SystemExit('At least one boundary case failed or could not be checked')
