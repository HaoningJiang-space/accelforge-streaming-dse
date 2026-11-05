"""G2 study only: blind pre-evaluation certificates, then retrospective appraisal."""
import argparse
from collections import Counter
from contextlib import ExitStack
from dataclasses import asdict
import hashlib
import importlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np

from research.diagnostics import profile_3mm_search as baseline
from research.diagnostics.pregen_certificates import (
    Bound,Relaxation,architecture_reasons,extract_facts,reference_oracle_dominator,
)
from research.graph_coopt.workload_dag import WorkloadDAG
from research.tracking_audit import common

CASES={
    'native':(common.Case('matmuls','nvdla',(3,256,256)),((16,384),(32,192),(64,96)),(131072,135168)),
    '2mm_holdout':(common.Case('matmuls','nvdla',(2,4,8)),((4,8),(8,4)),(128,256)),
    '3mm_holdout':(common.Case('matmuls','nvdla',(3,8,8)),((4,8),(8,4)),(128,136)),
}
TIERS=('local','architecture','graph')


class CertificateStudy:
    def __init__(self,capacities):
        self.capacities=capacities
        self.target=None
        self.catalogs=[]
        self.facts={}
        self.rows_checked=0
        self.resource_checks=Counter()
        self.active_analysis=False

    def analyze(self,jobs):
        """No G1 file, frontier, Tile result or timing is an argument here."""
        started=time.perf_counter()
        all_jobs=[j for groups in jobs.values()for batch in groups.values()for j in batch]
        facts=[extract_facts(j,str(j.job_id))for j in all_jobs]
        bounds_s=time.perf_counter()-started
        by_id={str(j.job_id):j for j in all_jobs}
        self.facts.update({f.key:f for f in facts})
        sample=all_jobs[0]
        dag=WorkloadDAG.from_workload(sample.spec.workload)
        spatial={(str(n.name),str(s.name)):int(s.fanout)for n in sample.flattened_arch for s in n.spatial}
        register_bits=int(next(n.size for n in sample.flattened_arch if n.name=='Register'))
        records={f.key:dict(native_job_uuid=f.key,einsum=f.einsum,
            target=repr(self.target),template=by_id[f.key].mapping.compact_str(),
            unknown=f.unknown,local_impossible=f.local_impossible,bound=f.bound.record(),
            spatial_min={repr(k):v for k,v in f.spatial_min.items()},evidence=f.evidence,
            targets={})for f in facts}
        start=time.perf_counter()
        local={f.key:['local_interval_contradiction']if f.local_impossible else [] for f in facts}
        local_s=time.perf_counter()-start
        start=time.perf_counter()
        arch={cap:{f.key:architecture_reasons(f,cap*8,register_bits,spatial)for f in facts}
            for cap in self.capacities}
        arch_s=time.perf_counter()-start
        start=time.perf_counter()
        graph=Relaxation(facts,dag.nodes,dag.edges)
        graph_build_s=time.perf_counter()-start
        start=time.perf_counter()
        for cap in self.capacities:
            allowed={k for k,reasons in arch[cap].items()if not reasons}
            for f in facts:
                active=graph.condition(allowed,f.key)
                graph_reasons=list(arch[cap][f.key])
                if not active and not graph_reasons:
                    graph_reasons=['no_relaxed_graph_completion']
                completion=graph.completion_bound(active)
                # Local's T=0 does not assume a particular physical array.
                local_bound=Bound(f.bound.gb_bits,f.bound.register_bits,f.bound.energy)
                records[f.key]['targets'][str(cap)]=dict(
                    local=dict(reject=bool(local[f.key]),reasons=local[f.key],bound=local_bound.record()),
                    architecture=dict(reject=bool(arch[cap][f.key]),reasons=arch[cap][f.key],bound=f.bound.record()),
                    graph=dict(reject=bool(graph_reasons),reasons=graph_reasons,
                        bound=None if completion is None else completion.record(),
                        relaxed_supported_templates=len(active)))
        graph_query_s=time.perf_counter()-start
        decision_payload=json.dumps(records,sort_keys=True)
        # This digest is fixed before the first expensive Job executes.
        catalog=dict(target=repr(self.target),shape=list(self.target[0]),records=records,
            phase_s=dict(common_bound_extraction=bounds_s,local_checks=local_s,
                architecture_checks=arch_s,graph_support_preparation=graph_build_s,
                graph_conditioned_queries=graph_query_s),
            decision_sha256=hashlib.sha256(decision_payload.encode()).hexdigest(),
            data_access='Raw Jobs, evaluated component coefficients, shapes and hard target capacities only; no G1 or final results.',
            unknowns=dict(Counter(f.unknown for f in facts if f.unknown)))
        catalog['total_preanalysis_s']=time.perf_counter()-started
        catalog['phase_s']['common_accounting_remainder']=max(0.,
            catalog['total_preanalysis_s']-sum(catalog['phase_s'].values()))
        self.catalogs.append(catalog)

    def validate_rows(self,job,frame):
        fact=self.facts[str(job.job_id)]
        if fact.unknown or frame.empty:
            return
        if fact.local_impossible:
            raise AssertionError('a locally impossible template generated a model row')
        for resource,lower in (('GlobalBuffer',fact.bound.gb_bits),('Register',fact.bound.register_bits)):
            cols=[c for c in frame if c.startswith(f'reservation<SEP>{resource}<SEP>')]
            if cols:
                observed=np.maximum.reduce([frame[c].to_numpy()for c in cols])
                if (observed<lower).any():
                    raise AssertionError(f'{resource} lower bound exceeds actual native reservation')
                self.resource_checks[resource]+=len(frame)
        # Numerical sanity check of real-arithmetic costs, not a floating point
        # pruning proof. Resource-only decisions above use exact integer bits.
        for col,lower in (('Total<SEP>energy',float(fact.bound.energy)),
            ('Total<SEP>latency',float(fact.bound.latency))):
            if (frame[col].to_numpy()*(1+2e-6)+1e-20<lower).any():
                raise AssertionError(f'optimistic cost exceeds native evaluation: {col}')
        self.rows_checked+=len(frame)

    def __enter__(self):
        self.stack=ExitStack()
        mapper=importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings')
        module=importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_pmappings_from_templates')
        tiles=importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')
        allocate,evaluate=mapper._allocate_jobs,module.make_tile_shapes
        def allocation(jobs):
            self.active_analysis=True
            try:self.analyze(jobs)
            finally:self.active_analysis=False
            return allocate(jobs)
        def checked(job):
            if self.active_analysis:
                raise AssertionError('certificate called expensive Job evaluation')
            result=evaluate(job)
            self.validate_rows(job,result[0])
            return result
        def guarded(function):
            def call(*args,**kwargs):
                if self.active_analysis:
                    raise AssertionError('certificate called model/enumeration')
                return function(*args,**kwargs)
            return call
        self.stack.enter_context(patch.object(mapper,'_allocate_jobs',allocation))
        self.stack.enter_context(patch.object(module,'make_tile_shapes',checked))
        self.stack.enter_context(patch.object(tiles,'run_model',guarded(tiles.run_model)))
        self.stack.enter_context(patch.object(tiles,'get_tile_shape_choices_for_targets',guarded(tiles.get_tile_shape_choices_for_targets)))
        return self

    def __exit__(self,*exc):
        return self.stack.__exit__(*exc)


def summarize(study,frontiers):
    result={}
    for tier in TIERS:
        members=whole=oracle_members=0
        for catalog in study.catalogs:
            x,y=catalog['shape']
            for record in catalog['records'].values():
                choices=[t[tier]for t in record['targets'].values()]
                whole+=all(t['reject']for t in choices)
                members+=sum(t['reject']for t in choices)
                for cap,target in record['targets'].items():
                    data=target[tier]['bound']
                    if data is None:continue
                    from fractions import Fraction
                    bound=Bound(data['gb_bits'],data['register_bits'],
                        Fraction(data['energy_rational']),Fraction(data['latency_rational']))
                    oracle_members+=reference_oracle_dominator(bound,frontiers[f'{x},{y},{cap}'])is not None
        common_s=sum(c['phase_s']['common_bound_extraction']+c['phase_s']['local_checks']+
            c['phase_s']['common_accounting_remainder']for c in study.catalogs)
        tier_s=common_s
        if tier in ('architecture','graph'):
            tier_s+=sum(c['phase_s']['architecture_checks']for c in study.catalogs)
        if tier=='graph':
            tier_s+=sum(c['phase_s']['graph_support_preparation']+c['phase_s']['graph_conditioned_queries']for c in study.catalogs)
        result[tier]=dict(certified_target_members=members,certified_whole_shared_jobs=whole,
            same_pipeline_preanalysis_s=tier_s,
            posthoc_free_reference_incumbent_dominance_screen=oracle_members,
            cost_screen_is_not_a_rejection_certificate=True)
    return result


def appraise_g1(study,g1):
    """Evaluation only, called after the pre-generation decisions are immutable."""
    lookup={(t['target'],t['einsum'],t['template']):t for t in g1['tasks']}
    if len(lookup)!=len(g1['tasks']):
        raise AssertionError('ambiguous G1 template match')
    records=[]
    for catalog in study.catalogs:
        for r in catalog['records'].values():
            t=lookup[(r['target'],r['einsum'],r['template'])]
            records.append((r,t))
    result={}
    for tier in TIERS:
        removed={t['id']for r,t in records if all(v[tier]['reject']for v in r['targets'].values())}
        credited=[t for _,t in records if t['id']in removed]
        if any(t['has_final_descendant']for t in credited):
            raise AssertionError('certificate would remove a returned final witness')
        # Check target-member exclusions against every returned source as well.
        for point,edges in g1['final_sources'].items():
            x,y,cap=map(int,point.split(','))
            used={tile.split(':tile:')[0]for edge in edges for tile in edge['tile_ids']}
            for r,t in records:
                if r['target']==repr(((x,y),tuple(study.capacities))) and t['id']in used:
                    if r['targets'][str(cap)][tier]['reject']:
                        raise AssertionError('certificate would remove a returned member witness')
        batches=[b for b in g1['batches']if set(b['task_ids'])<=removed]
        gross=sum(t['evaluation_s']for t in credited)+sum(b['non_job_s']for b in batches)
        stages=Counter(t['observed_stage_class']for t in credited)
        result[tier]=dict(whole_jobs=len(removed),whole_batches=len(batches),
            no_local_join_rows=stages['no_local_join_rows'],
            join_input_no_final_descendant=stages['join_rows_no_final_descendant'],
            retained_frontier_jobs=stages['frontier_descendant'],
            g1_posthoc_gross_credit_s=gross)
    return result


def worker(args):
    case,shapes,caps=CASES[args.case]
    common.af.set_n_parallel_jobs(1);common.clear_switches()
    with patch.object(baseline,'CASE',case),patch.object(baseline,'SHAPES',shapes),patch.object(baseline,'CAPACITIES',caps):
        warm,_=baseline.execute('events_ru')
        expected=baseline.snapshots(warm,True)
        del warm
        study=CertificateStudy(caps)
        actual,_=baseline.execute('events_ru',forensics=study)
        fronts=baseline.snapshots(actual,True)
    if fronts!=expected:
        raise AssertionError('observer changed complete RU frontiers')
    if args.case=='native':
        ref=common.ROOT/'research/diagnostics/results/search_cost_3mm/events_ru_1.json'
        if fronts!=json.loads(ref.read_text())['frontiers']:
            raise AssertionError('native fronts differ from frozen reference')
    # Freeze/check decision content before looking at any retrospective labels.
    for c in study.catalogs:
        if hashlib.sha256(json.dumps(c['records'],sort_keys=True).encode()).hexdigest()!=c['decision_sha256']:
            raise AssertionError('pre-generation decisions changed after evaluation')
    levels=summarize(study,fronts)
    g1_appraisal=None
    if args.case=='native':
        path=common.ROOT/f'research/diagnostics/results/generation_provenance_3mm/trial_{args.g1_trial}.json'
        g1_appraisal=appraise_g1(study,json.loads(path.read_text()))
        for tier in TIERS:
            g1_appraisal[tier]['net_projection_before_unimplemented_engine_overhead_s']=(
                g1_appraisal[tier]['g1_posthoc_gross_credit_s']-levels[tier]['same_pipeline_preanalysis_s'])
    report=dict(status='complete',case=args.case,complete_frontiers_equal=True,
        frontiers=fronts,tiers=levels,g1_appraisal=g1_appraisal,catalogs=study.catalogs,
        generated_model_rows_checked=study.rows_checked,resource_row_checks=dict(study.resource_checks),
        actual_jobs_skipped=0,search_decisions_modified=False,
        total_observed_preanalysis_s=sum(c['total_preanalysis_s']for c in study.catalogs),
        cost_scope='Real-arithmetic lower-bound candidates and FREE POST-HOC incumbent screen only; no floating-point dominance pruning certificate.',
        source_sha256={str(p.relative_to(common.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__),Path(__file__).with_name('pregen_certificates.py'))})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(case=args.case,tiers=levels,model_rows=study.rows_checked,
        unknowns=[c['unknowns']for c in study.catalogs])),flush=True)


def matrix(args):
    args.output.mkdir(parents=True,exist_ok=True)
    reports=[]
    jobs=[('native',i+1)for i in range(args.repeats)]+[('2mm_holdout',1),('3mm_holdout',1)]
    for case,repeat in jobs:
        file=args.output/f'{case}_{repeat}.json'
        env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
            NUMBA_NUM_THREADS='1',PYTHONHASHSEED='0')
        command=[sys.executable,'-m','research.diagnostics.pregen_certificate_study','--worker',
            '--case',case,'--g1-trial',str(repeat),'--output',str(file)]
        with file.with_suffix('.log').open('w')as log:
            done=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env)
        if done.returncode:raise RuntimeError(f'certificate study failed; see {file.with_suffix(".log")}')
        report=json.loads(file.read_text());reports.append(report)
        print(json.dumps(dict(case=case,repeat=repeat,tiers=report['tiers'])),flush=True)
    native=[r for r in reports if r['case']=='native']
    result=dict(status='complete',native_repeats=args.repeats,
        per_run=[dict(case=r['case'],tiers=r['tiers'],appraisal=r['g1_appraisal'],
            generated_model_rows_checked=r['generated_model_rows_checked'],
            total_observed_preanalysis_s=r['total_observed_preanalysis_s'])for r in reports],
        median_native_tier_cost_s={t:statistics.median(r['tiers'][t]['same_pipeline_preanalysis_s']for r in native)for t in TIERS},
        all_frontiers_equal=True,all_jobs_executed=True,
        scope='Feasibility of a specified cheap relaxation only; not all possible pre-generation certificates. No new optimizer or online pruning.')
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--worker',action='store_true')
    p.add_argument('--case',choices=CASES,default='native')
    p.add_argument('--g1-trial',type=int,choices=(1,2,3),default=1)
    p.add_argument('--repeats',type=int,choices=(1,2,3),default=3)
    args=p.parse_args()
    worker(args)if args.worker else matrix(args)


if __name__=='__main__':main()
