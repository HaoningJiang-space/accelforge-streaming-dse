"""Same-case native search diagnosis. Frozen backends; no optimizer changes."""
import argparse
from contextlib import ExitStack,nullcontext
import gc
import hashlib
import importlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import platform
import importlib.metadata
from unittest.mock import patch

from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build,validate_pick
from research.tracking_audit.generation_profile import GenerationPhases
from research.joint_search.validation import WorkCounter
from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse
from accelforge.mapper.FFM._pareto_df.capacity_membership import is_membership_col
from accelforge.mapper.FFM._pareto_df.df_convention import col_used_in_pareto
from accelforge.mapper.FFM._pareto_df.pareto import makepareto

ROOT=common.ROOT
CASE=common.Case('matmuls','nvdla',(3,256,256))
SHAPES=((16,384),(32,192),(64,96));CAPACITIES=(131072,135168)
VARIANTS=('independent_el','cached_el','independent_ru','cached_ru','events_ru')


class ProfileWork(WorkCounter):
    def __enter__(self):
        super().__enter__()
        cls=importlib.import_module('accelforge.mapper.FFM._join_pmappings.pmapping_dataframe').PmappingDataframe
        original=cls.make_pareto
        self.counts.update(frame_pareto_calls=0,frame_pareto_input_rows=0,frame_pareto_output_rows=0,
            largest_pareto_input_rows=0)
        def pareto(frame,*args,**kwargs):
            n=len(frame.data);self.counts['frame_pareto_calls']+=1
            self.counts['frame_pareto_input_rows']+=n
            self.counts['largest_pareto_input_rows']=max(n,self.counts['largest_pareto_input_rows'])
            result=original(frame,*args,**kwargs)
            self.counts['frame_pareto_output_rows']+=len(frame.data)
            return result
        self.stack.enter_context(patch.object(cls,'make_pareto',pareto))
        return self


def numeric_frontier(frame,resource):
    cols=sorted(c for c in frame if c in ('Total<SEP>energy',common.LATENCY)or
        (resource and c.startswith('reservation_bits<SEP>')))
    data=frame[cols].drop_duplicates().sort_values(cols).reset_index(drop=True)
    # Column-wise conversion preserves integer bits, unlike mixed iterrows().
    return dict(columns=cols,values={c:[int(v)if data[c].dtype.kind in 'iu'else float(v)
        for v in data[c]]for c in cols})


class SearchPhases(GenerationPhases):
    """Additional nested observations; exclusive remainders are additive."""
    def __init__(self):
        super().__init__(common)
        df=importlib.import_module('accelforge.mapper.FFM._join_pmappings.pmapping_dataframe')
        self.targets.extend([
            (df.PmappingDataframe,'merge_next','numeric_join'),
            (df.PmappingDataframe,'_prepare_join_plan','join_plan'),
            (df.PmappingDataframe,'_prepare_column_operations','join_column_program'),
            (df.PmappingDataframe,'adjust_reservations','reservation_adjust'),
            (df.PmappingDataframe,'free_to_loop_index','scope_release'),
            (df.PmappingDataframe,'limit_capacity','capacity_filter'),
            (df.PmappingDataframe,'make_pareto','frame_pareto'),
            (df,'makepareto','frame_pareto_kernel'),
        ])


def execute(variant,profile=False,capture=None,forensics=None):
    if variant not in VARIANTS:raise ValueError('unknown diagnostic variant')
    resource=variant.endswith('_ru');metrics=common.RU if resource else common.EL
    cached=variant.startswith('cached')or variant=='events_ru'
    outputs={};stats=[];cache_stats=None
    with ExitStack()as stack:
        reuse=stack.enter_context(EnumerationReuse())if cached else None
        if forensics is not None:stack.enter_context(forensics)
        counter=stack.enter_context(ProfileWork(capture))if profile else None
        phases=stack.enter_context(SearchPhases())if profile else None
        for shape in SHAPES:
            for capacity in ((max(CAPACITIES),)if variant=='events_ru'else CAPACITIES):
                env=None
                if variant=='events_ru':
                    env={'AF_TARGET_ENUMERATION':'events','AF_CAPACITY_MEMBERSHIP':'bitset',
                        'AF_GENERATION_CAPACITY_FRACTIONS':'GlobalBuffer:'+','.join(repr(c/capacity)for c in CAPACITIES),
                        'AF_GENERATION_CAPACITY_BITS':'GlobalBuffer:'+','.join(str(c*8)for c in CAPACITIES)}
                label=(shape,capacity)if variant!='events_ru'else(shape,CAPACITIES)
                if forensics is not None:forensics.target=label
                with reuse.target(label)if reuse else nullcontext():
                    spec=build(CASE,shape,capacity,metrics)
                    result,timing=common.search(spec,gen_env=env)
                stats.append(dict(shape=shape,capacity_bytes=capacity,**timing))
                for cap in CAPACITIES if variant=='events_ru'else (capacity,):
                    frame=result.data
                    if variant=='events_ru':
                        frame=common.rows_for_capacity(frame,cap/2**20,capacity/2**20).copy()
                        frame=frame.drop(columns=[c for c in frame if is_membership_col(c)])
                        frame['capacity_reference_bits<SEP>GlobalBuffer']=cap*8
                        for c in frame:
                            if c.startswith('reservation<SEP>GlobalBuffer<SEP>'):
                                frame[c]=frame[c.replace('reservation<SEP>','reservation_bits<SEP>')]/(cap*8)
                        columns=[c for c in frame.select_dtypes(include='number')if col_used_in_pareto(c)]
                        frame=makepareto(frame,columns=columns)
                    outputs[(*shape,cap)]=frame
        if reuse:cache_stats=dict(reuse.stats)
        details=dict(searches=stats,cache=cache_stats)
        if profile:details.update(work=dict(counter.counts),phases=phases.snapshot())
    return outputs,details


def snapshots(outputs,resource):
    return {','.join(map(str,key)):numeric_frontier(frame,resource)for key,frame in outputs.items()}


def worker(args):
    common.af.set_n_parallel_jobs(1);common.clear_switches();resource=args.variant.endswith('_ru')
    start=time.perf_counter();cold,_=execute(args.variant);cold_s=time.perf_counter()-start
    cold_front=snapshots(cold,resource);del cold;gc.collect()
    start=time.perf_counter();warm,details=execute(args.variant);warm_s=time.perf_counter()-start
    fronts=snapshots(warm,resource)
    if cold_front!=fronts:raise AssertionError('cold/warm numerical frontier differs')
    peak=common.peak_rss_gb()['main']
    profiled=None
    if args.profile:
        start=time.perf_counter()
        observed,profiled=execute(args.variant,profile=True)
        profiled['instrumented_total_s']=time.perf_counter()-start
        if snapshots(observed,resource)!=fronts:raise AssertionError('profiling changed the numerical frontier')
        del observed
    forensic=None
    if args.forensic:
        from .search_repetition import RepetitionAudit
        audit=RepetitionAudit();observed,_=execute(args.variant,forensics=audit)
        if snapshots(observed,resource)!=fronts:raise AssertionError('repetition tracing changed the numerical frontier')
        forensic=audit.summary();del observed
    validations=[]
    for (x,y,cap),frame in warm.items():
        row=common.best_row(frame)
        if row is None:raise AssertionError('empty physical target')
        valid=validate_pick(CASE,(x,y),cap,row)
        if not valid['ok']:raise AssertionError('selected source failed replay')
        validations.append(dict(shape=[x,y],capacity_bytes=cap,energy=valid['energy'],
            latency=valid['latency'],edp=valid['edp'],gb_bytes=valid['gb_bytes'],mapping_id=valid['mapping_id']))
    report=dict(status='complete',variant=args.variant,metrics='EL|RESOURCE_USAGE'if resource else'EL',
        cold_search_s=cold_s,warm_search_s=warm_s,process_peak_rss_gib_before_profile_validation=peak,
        cold_warm_frontiers_equal=True,frontiers=fronts,selections=validations,details=details,profile=profiled,
        forensics=forensic,
        protocol='Fresh process. Cold and warm full searches create fresh candidates/cache scopes. Imports outside timers; build/generation/Join/queries inside. Profiling and source validation outside timers.',
        native_changes=False,workers=1,pareto_tolerance=float(
            importlib.import_module('accelforge.mapper.FFM._pareto_df.pareto').TOLERANCE))
    files=[Path(__file__),Path(__file__).with_name('search_repetition.py'),
        ROOT/'research/tracking_audit/generation_profile.py',
        ROOT/'accelforge/mapper/FFM/_make_pmappings/make_pmappings_from_templates/enumeration_reuse.py']
    report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(variant=args.variant,cold_s=cold_s,warm_s=warm_s,
        work=None if profiled is None else profiled['work'])),flush=True)


def matrix(args):
    args.output.mkdir(parents=True,exist_ok=True);reports=[]
    for repeat in range(args.repeats):
        order=VARIANTS if repeat%2==0 else VARIANTS[::-1]
        for variant in order:
            path=args.output/f'{variant}_{repeat+1}.json';log=path.with_suffix('.log')
            command=[sys.executable,'-m','research.diagnostics.profile_3mm_search','--variant',variant,
                '--output',str(path)]
            if repeat==0:command+=['--profile']
            if repeat==0 and variant in ('cached_ru','events_ru'):command+=['--forensic']
            env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_NUM_THREADS='1',PYTHONHASHSEED='0')
            with log.open('w')as stream:done=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,env=env)
            if done.returncode:raise RuntimeError(f'{variant} failed; see {log}')
            r=json.loads(path.read_text());reports.append(r)
            print(json.dumps(dict(variant=variant,repeat=repeat+1,cold_s=r['cold_search_s'],warm_s=r['warm_search_s'])),flush=True)
            (args.output/'progress.json').write_text(json.dumps(dict(status='in_progress',finished=len(reports)),indent=2)+'\n')
    summary=dict(status='complete',repeats=args.repeats,variants={},comparisons={},
        environment=dict(python=sys.version,platform=platform.platform(),
            packages={name:importlib.metadata.version(name)for name in ('numpy','pandas','sympy','numba','pydantic')},
            numeric_threads=1,workers=1),
        exclusions={'region_compiler':'Single-MatMul/template only; no native 3mm Fusion search.',
            'shared_architecture_generator':'Frozen adapter requires 2mm and dyadic extents; this case has 3mm and 16x384/32x192/64x96.'})
    for variant in VARIANTS:
        rows=[r for r in reports if r['variant']==variant];first=rows[0]
        if not all(r['frontiers']==first['frontiers']for r in rows):raise AssertionError('repeat frontier changed')
        summary['variants'][variant]=dict(cold_median_s=statistics.median(r['cold_search_s']for r in rows),
            warm_median_s=statistics.median(r['warm_search_s']for r in rows),
            cold_runs_s=[r['cold_search_s']for r in rows],warm_runs_s=[r['warm_search_s']for r in rows],
            all_repeats_frontiers_equal=True,profile=first['profile'],forensics=first['forensics'])
    for actual,ref in (('cached_el','independent_el'),('cached_ru','independent_ru'),('events_ru','independent_ru')):
        a=next(r for r in reports if r['variant']==actual);b=next(r for r in reports if r['variant']==ref)
        summary['comparisons'][actual+'_vs_'+ref]=dict(exact_numeric_frontiers_equal=a['frontiers']==b['frontiers'])
    summary['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__),ROOT/'research/tracking_audit/generation_profile.py',ROOT/'research/joint_search/validation.py')}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--variant',choices=VARIANTS);p.add_argument('--profile',action='store_true')
    p.add_argument('--forensic',action='store_true')
    p.add_argument('--repeats',type=int,default=3);args=p.parse_args()
    if args.repeats<1:raise ValueError('positive trial count required')
    worker(args)if args.variant else matrix(args)


if __name__=='__main__':main()
