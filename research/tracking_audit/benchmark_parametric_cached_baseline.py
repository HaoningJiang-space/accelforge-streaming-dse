"""Stronger online baseline: prepared FFM plus existing cross-query pure-op cache.

The archived region result supplies only the query sequence to the timed search.
Its answers are read outside timers for validation, never to guide enumeration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse
from research.tracking_audit import benchmark_parametric_template as b
from research.tracking_audit.parametric_template import Box


def run(reference_path,output):
    reference = json.loads(reference_path.read_text())
    b.common.af.set_n_parallel_jobs(1)
    b.common.clear_switches()
    b.frontier(np.array([[1.,2.,3.],[2.,1.,2.]]))
    family = Box(tuple(tuple(v) for v in reference['family']))
    case = b.common.Case('matmuls','nvdla',(1,256,256))
    t0 = time.perf_counter()
    program = b.prepare(256,tuple(hi for lo,hi in family.ranges))
    prepare_s = time.perf_counter()-t0
    if hashlib.sha256(program.template_key.encode()).hexdigest() != reference['template_id']:
        raise ValueError('reference does not use the benchmark template')
    report = dict(config=b.common.effective_config(case), prepare_s=prepare_s,
                  reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),
                  source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (Path(__file__),Path(b.__file__))}, queries=[])
    validation_inputs = []
    total, cost_rows = 0.,0
    with EnumerationReuse() as reuse:
        for record in reference['queries']:
            point = tuple(record['point'])
            with reuse.target(point):
                t0 = time.perf_counter()
                choices,_ = b.oracle(program,b.instantiate_objectives(program,point))
                costs = b.selected_costs(program,choices)
                front = b.frontier(costs)
                pick = b.reconstruct_best(program,choices,costs)
                elapsed = time.perf_counter()-t0
            total += elapsed
            cost_rows += len(choices)
            # Validation cannot populate the timed cache with evaluated models.
            validation_inputs.append((point,choices,front,pick,record))
            report['queries'].append(dict(point=point,query_s=elapsed,cumulative_s=prepare_s+total,
                                           rows=len(choices),cache_work=dict(reuse.stats)))
        report['cache_work'] = dict(reuse.stats)
    report.update(cost_rows=cost_rows,total_s=prepare_s+total)
    b.save(output,report)
    for i,(point,choices,front,pick,record) in enumerate(validation_inputs):
        regions = [r for r in reference['regions'] if any(
            Box(tuple(tuple(v) for v in box)).contains((point[0],point[1],point[2]*8))
            for box in r['boxes'])]
        expected = np.array(regions[0]['choices']) if regions else np.empty((0,len(program.kwargs['symbols'])))
        checks = dict(tiles=np.array_equal(b.canonical_choices(choices),b.canonical_choices(expected)),
                      frontier=np.array_equal(front,np.array(record['frontier']).reshape(-1,3)))
        validation = b.validate_selected(case,point,pick)
        checks['reconstruction'] = validation['ok'] and validation['exact_gb_match']
        report['queries'][i].update(checks=checks,reconstruction=validation)
        b.save(output,report)
        if not all(checks.values()):
            raise AssertionError(f'cached baseline mismatch at {point}')
    report['all_match'] = True
    b.save(output,report)
    print(json.dumps(dict(total_s=report['total_s'],prepare_s=prepare_s,cost_rows=cost_rows,
                         cache_work=report['cache_work'],all_match=True)),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    run(a.reference,a.output)
