"""Inspect a shared-vs-independent capacity discrepancy under bounded execution."""
import copy
import json
import os
from pathlib import Path
import sys
import traceback


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
os.environ.pop('AF_VARIABLE_RESOURCES', None)
shape = [64,128,256]
max_capacity, small_capacity = 0.5, 0.03125
energy_latency = af.Metrics.ENERGY | af.Metrics.LATENCY
resource_metrics = energy_latency | af.Metrics.RESOURCE_USAGE
reservation = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'


def build(capacity, metrics):
    spec = af.Spec.from_yaml(root/'examples/arches/tpu_v4i.yaml', root/'research/streaming_join/glu_tag1.yaml',
        jinja_parse_data=dict(zip(('M','G','C'), shape)))
    spec.arch.find('GlobalBuffer').size = capacity * 1024 * 1024 * 8
    spec.mapper.ffm.metrics = metrics
    spec.mapper.ffm.max_pmapping_templates_per_einsum = 1
    return spec


def search(spec):
    return join_pmappings(make_pmappings(spec, print_number_of_pmappings=False))


def describe(label, row):
    energy, latency = float(row['Total<SEP>energy']), float(row['Total<SEP>latency'])
    fields = {c:float(row[c]) for c in row.index if c.startswith('reservation<SEP>')}
    print('ROW', json.dumps({'label':label,'energy':energy,'latency':latency,
         'edp':energy*latency,'reservations':fields}), flush=True)


def best(data):
    idx = (data['Total<SEP>energy'] * data['Total<SEP>latency']).idxmin()
    return data.loc[idx]


full = search(build(max_capacity, resource_metrics))
full_best = best(full.data)
small_view = full.data[full.data[reservation] <= small_capacity/max_capacity*(1+1e-12)]
describe('shared_unfiltered_best', full_best)
describe('shared_filtered_best', best(small_view))
small_spec = build(small_capacity, energy_latency)
independent = search(small_spec)
independent_best = best(independent.data)
describe('independent_best', independent_best)

# Tag 1.0 itself documents that reconstructed mappings may not be evaluable.
try:
    local_spec = copy.deepcopy(small_spec)
    local_spec.model.metrics = resource_metrics
    local_spec.mapping = independent_best['Total<SEP>mapping']()
    evaluated = evaluate_mapping(local_spec, flattened_arches=independent.flattened_arches,
                                 evaluated_specs=independent.evaluated_specs)
    cols = [c for c in evaluated.data.columns if c.startswith('Total<SEP>') or c.startswith('reservation<SEP>')]
    print('REEVALUATED',json.dumps({'rows':len(evaluated.data),'columns':cols,
        'values':evaluated.data[cols].astype(float).to_numpy().tolist()}),flush=True)
except Exception as exc:
    print('REEVALUATION_ERROR',json.dumps({'type':type(exc).__name__,'message':str(exc)}),flush=True)
    traceback.print_exc()
