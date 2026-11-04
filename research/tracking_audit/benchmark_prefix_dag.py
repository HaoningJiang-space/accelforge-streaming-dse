"""Isolated, preprocessing-inclusive real-template comparison with the FFM cache."""
import argparse
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

import numpy as np

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse
from research.tracking_audit import benchmark_parametric_template as b
from research.tracking_audit.benchmark_parametric_operator import FAMILY, fingerprint, query_points
from research.tracking_audit.factorized_prefix_dag import FactorizedPrefixRegions


def prepare_index(index):
    """Select a template using structure only; model only that one template."""
    point=tuple(hi for _,hi in FAMILY.ranges)
    case=b.common.Case('matmuls','nvdla',(1,256,256))
    spec=b.build(case,point[:2],point[2],b.common.RU)
    evaluated=spec._spec_eval_expressions(eval_arch=False,eval_non_arch=True)
    jobs=b.pmapper.get_jobs(evaluated,b.common.RU,evaluated.workload.einsum_names,True)
    keys=sorted(json.dumps(b.mapping_structure(j.mapping),sort_keys=True)
                for groups in jobs.values() for group in groups.values() for j in group)
    if len(keys)!=6 or len(set(keys))!=6:
        raise ValueError('expected six distinct single-operator templates')
    return b.prepare(256,point,keys[index])


def run(index,mode,count,output):
    b.common.af.set_n_parallel_jobs(1);b.common.clear_switches()
    b.frontier(np.array([[1.,2.,3.],[2.,1.,2.]]))
    start=time.perf_counter()
    program=prepare_index(index)
    prepared=time.perf_counter()
    compiled=None
    if mode in ('region','dag'):
        context=patch.object(b,'RegionEnumerator',FactorizedPrefixRegions) if mode=='dag' else nullcontext()
        with context:
            compiled=b.CompiledTemplate(program,FAMILY)
    ready=time.perf_counter()
    # Concrete target points do not exist until family compilation is complete.
    points=query_points(count)
    report=dict(template=index,mode=mode,queries=[],prepare_s=prepared-start,
                compile_s=ready-prepared,preprocess_s=ready-start,
                source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                    (Path(__file__),Path(__file__).with_name('factorized_prefix_dag.py'),
                     Path(b.__file__),Path(__file__).with_name('parametric_template.py'),
                     Path(__file__).with_name('benchmark_parametric_operator.py'),
                     Path(__file__).resolve().parents[2]/'accelforge/mapper/FFM/_make_pmappings/make_pmappings_from_templates/enumeration_reuse.py')})
    if compiled is not None:
        report['compilation']=compiled.engine.stats
    pending=[];total=0.
    context=EnumerationReuse() if mode=='cached' else nullcontext()
    with context as reuse:
        for i,point in enumerate(points):
            target=reuse.target(point) if reuse else nullcontext()
            with target:
                start=time.perf_counter()
                if compiled is not None:
                    choices,front=compiled.query(point)
                    pick=compiled.best_mapping(point)
                else:
                    choices,_=b.oracle(program,b.instantiate_objectives(program,point))
                    costs=b.selected_costs(program,choices)
                    front=b.frontier(costs)
                    pick=b.reconstruct_best(program,choices,costs)
                elapsed=time.perf_counter()-start
            total += elapsed
            report['queries'].append(dict(point=point,cumulative_s=report['preprocess_s']+total,
                choices=fingerprint(choices,program.kwargs['symbols']),frontier=front.tolist()))
            if i in {0,1,2,3,63,127,191,255}:
                pending.append((i,point,pick))
        if reuse:
            report['cache_work']=dict(reuse.stats)
    report['total_s']=report['preprocess_s']+total
    report['search_peak_rss_gib']=b.common.peak_rss_gb()['main']
    output.parent.mkdir(parents=True,exist_ok=True)
    b.save(output,report)
    case=b.common.Case('matmuls','nvdla',(1,256,256))
    for i,point,pick in pending:
        report['queries'][i]['reconstruction']=b.validate_selected(case,point,pick)
        b.save(output,report)
    report['all_sampled_reconstructions_valid']=all(report['queries'][i]['reconstruction']['ok']
                                                    and report['queries'][i]['reconstruction']['exact_gb_match']
                                                    for i,_,_ in pending)
    b.save(output,report)
    if not report['all_sampled_reconstructions_valid']:
        raise AssertionError('a sampled Mapping failed reconstruction')
    print(json.dumps(dict(template=index,mode=mode,total_s=report['total_s'],
                          preprocess_s=report['preprocess_s'],queries=count)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--template',type=int,choices=(1,3),required=True)
    p.add_argument('--mode',choices=('region','dag','cached'),required=True)
    p.add_argument('--queries',type=int,default=256)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.queries<=0:p.error('positive query count required')
    run(a.template,a.mode,a.queries,a.output)
