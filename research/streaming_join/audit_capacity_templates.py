"""Compare generated template structures across capacity settings (not tile coverage)."""
import hashlib
import json
import os
from pathlib import Path
import sys


def no_children(event, args):
    if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
        raise RuntimeError('Child processes disabled: ' + event)


sys.addaudithook(no_children)
import accelforge as af
from accelforge.mapper.FFM._make_pmappings.make_pmappings import get_jobs

af.set_n_parallel_jobs(1)
root = Path(__file__).resolve().parents[2]
shape = [int(x) for x in os.getenv('COMPARE_SHAPE', '512,1024,2048').split(',')]
capacities = [float(x) for x in os.getenv('COMPARE_CAPACITIES_MIB', '2,4,8').split(',')]
max_templates = int(os.getenv('COMPARE_MAX_TEMPLATES', '2'))
metrics = af.Metrics.ENERGY | af.Metrics.LATENCY
results = {}
for capacity in capacities:
    spec = af.Spec.from_yaml(root/'examples/arches/tpu_v4i.yaml', root/'research/streaming_join/glu_tag1.yaml',
                             jinja_parse_data=dict(zip(('M', 'G', 'C'), shape)))
    spec.arch.find('GlobalBuffer').size = capacity * 1024 * 1024 * 8
    spec.mapper.ffm.max_pmapping_templates_per_einsum = max_templates
    spec = spec._spec_eval_expressions(eval_arch=False, eval_non_arch=True)
    jobs = get_jobs(spec, metrics, spec.workload.einsum_names, True)
    records = {}
    for name, groups in jobs.items():
        ids = []
        for group in groups.values():
            for job in group:
                # Compact node descriptions identify this experiment's ordered templates,
                # but do not capture all fields, constraints, or tile shapes.
                payload = json.dumps([(type(n).__name__, n.compact_str()) for n in job.mapping.nodes], separators=(',', ':'))
                ids.append(hashlib.sha256(payload.encode()).hexdigest())
        records[str(name)] = sorted(ids)
    results[str(capacity)] = records
    print('CAPACITY_TEMPLATES', json.dumps({'capacity_mib': capacity, 'templates': records}), flush=True)
reference = results[str(max(capacities))]
covered = {cap: {name: all(ids.count(x) <= reference.get(name, []).count(x) for x in set(ids))
                 for name, ids in rec.items()} for cap, rec in results.items()}
print('TEMPLATE_AUDIT', json.dumps({'shape': shape, 'templates_per_einsum': max_templates,
    'capacities_mib': capacities, 'template_ids': results, 'multiset_covered_by_max': covered,
    'scope': 'ordered_compact_node_descriptions_only_not_all_fields_constraints_or_tiles'}))
