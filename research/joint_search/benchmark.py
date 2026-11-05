"""Serial fresh-process comparisons for the six-point Stage 0–2 gate."""
import argparse
from dataclasses import asdict
import gc
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

import pandas as pd
from pandas.testing import assert_frame_equal

from research.tracking_audit import common
from .joint_optimizer import search_2mm
from .validation import gate_domain, reference, capacity_events, frontier, validate_sources, WorkCounter

VARIANTS=('independent','cached','capacity_events','joint')


def execute(variant,case,domain):
    if variant=='joint':
        with WorkCounter() as counter:
            outputs,details=search_2mm(case,domain)
        work=counter.counts
        work['model_rows']=sum(s['model_rows'] for s in details['enumeration'])
        work['model_templates']=len(details['enumeration'])
        return outputs,dict(details=details,work=work)
    if variant=='capacity_events':
        outputs,details,cache=capacity_events(case,domain)
        counts=[d['work'] for d in details]
    else:
        outputs,by_point,_,cache=reference(case,domain,cached=variant=='cached')
        details=[dict(architecture=asdict(p),**d) for p,d in by_point.items()]
        counts=[d['work'] for d in details]
    work={k:max(d[k] for d in counts) if k=='largest_pair_frame' else sum(d[k] for d in counts)
          for k in counts[0]}
    return outputs,dict(details=details,work=work,cache=cache)


def worker(args):
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    case=common.Case('matmuls','nvdla',(2,16,16)); domain=gate_domain()
    expected=json.loads(args.audit.read_text())
    if expected['status']!='complete':
        raise ValueError('complete frozen reference required for verification only')
    start=time.perf_counter()
    warm,unused=execute(args.variant,case,domain)
    cold_s=time.perf_counter()-start
    del warm,unused
    gc.collect()
    start=time.perf_counter()
    outputs,stats=execute(args.variant,case,domain)
    search_s=time.perf_counter()-start
    # Fresh process high-water before any source verification. This includes
    # interpreter/imports and one cold full search; it is not incremental RSS.
    process_peak=common.peak_rss_gb()['main']
    checks=[]
    for p,record in zip(domain.points,expected['points']):
        if asdict(p)!=record['architecture']:
            raise AssertionError('frozen reference uses a different domain/order')
        actual=frontier(outputs[p])
        target=pd.DataFrame(record['quality']['vectors']).reindex(columns=actual.columns)
        target=target.sort_values(list(target)).reset_index(drop=True)
        assert_frame_equal(actual,target,check_exact=True,check_dtype=False)
        validations=validate_sources(case,p,outputs[p])
        checks.append(dict(architecture=asdict(p),exact_full_etr_frontier=True,
            mapping_ids=sorted(common.mapping_identity(row['Total<SEP>mapping']()) for _,row in outputs[p].iterrows()),
            source_instances=len(validations),all_sources_valid=all(v['ok']for v in validations)))
    report=dict(status='complete',variant=args.variant,cold_search_s=cold_s,
        warm_search_s=search_s,process_peak_rss_gib_before_validation=process_peak,
        stats=stats,checks=checks,
        frozen_reference_sha256=hashlib.sha256(args.audit.read_bytes()).hexdigest(),
        source_sha256={str(p.relative_to(common.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in Path(__file__).parent.glob('*.py')})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(variant=args.variant,cold_s=cold_s,warm_s=search_s,
        rss_gib=process_peak,work=stats['work'])),flush=True)


def matrix(args):
    args.output.mkdir(parents=True,exist_ok=True)
    reports=[]
    for repeat in range(args.repeats):
        order=VARIANTS if repeat%2==0 else VARIANTS[::-1]
        for variant in order:
            output=args.output/f'{variant}_{repeat+1}.json'
            log=args.output/f'{variant}_{repeat+1}.log'
            command=[sys.executable,'-m','research.joint_search.benchmark','--variant',variant,
                     '--audit',str(args.audit),'--output',str(output)]
            with log.open('w')as stream:
                done=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
            if done.returncode:
                raise RuntimeError(f'{variant} failed; inspect {log}')
            record=json.loads(output.read_text());reports.append(record)
            print(variant,repeat+1,record['warm_search_s'],record['stats']['work'],flush=True)
    summary=dict(status='complete',repeats=args.repeats,variants={},
        protocol='Fresh process per trial, one cold full search then one warmed full search. Every search constructs candidates from scratch; no candidate cache survives warmup. Preparation, generation, Join, queries included. Validation outside timer.',
        consumer_requirements_enabled=False)
    for variant in VARIANTS:
        rows=[r for r in reports if r['variant']==variant]
        summary['variants'][variant]=dict(
            cold_search_median_s=statistics.median(r['cold_search_s']for r in rows),
            warm_search_median_s=statistics.median(r['warm_search_s']for r in rows),
            process_peak_rss_median_gib=statistics.median(r['process_peak_rss_gib_before_validation']for r in rows),
            work_by_repeat=[r['stats']['work']for r in rows],
            all_full_frontiers_equal=all(c['exact_full_etr_frontier']for r in rows for c in r['checks']),
            all_sources_valid=all(c['all_sources_valid']for r in rows for c in r['checks']))
    base=summary['variants']['cached']['warm_search_median_s']
    joint=summary['variants']['joint']['warm_search_median_s']
    summary['joint_vs_cached_warm_speedup']=base/joint
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--variant',choices=VARIANTS)
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--audit',type=Path,default=Path(__file__).parent/'results/stage02/audit.json')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.repeats<1:
        raise ValueError('positive repeat count required')
    worker(args)if args.variant else matrix(args)


if __name__=='__main__':
    main()
