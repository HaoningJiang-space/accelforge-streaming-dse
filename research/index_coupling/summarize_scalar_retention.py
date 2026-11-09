"""Summarize theorem checks, wider-grammar quality and matched-family timings."""
from collections import Counter
import json
from pathlib import Path
import sys

from .run_scalar_retention import MODES


def read(path): return [json.loads(x) for x in path.read_text().splitlines()]


def summary(root):
    rows=read(root/'cases.jsonl'); cases=[r for r in rows if r['kind']=='case']
    result=dict(cases=len(cases),errors=[r for r in rows if r['kind']=='error'],quality={})
    for source in ('regression','fresh','all'):
        selected=[r for r in cases if source=='all' or r['source']==source]; out={}
        for m in MODES:
            counts=Counter(); worst=[]; budgets=0
            for r in selected:
                s=r['scores'][m];counts.update(s['integer_counts']);budgets+=s['integer_budgets']
                worst.append(dict(shape=r['shape'],cross=r['cross'],excess=s['worst_traffic_excess'],capacity=s['worst_capacity']))
            worst.sort(key=lambda r:r['excess'],reverse=True)
            fraction=counts['within5']/budgets
            out[m]=dict(instances=len(selected),budgets=budgets,counts=dict(counts),within5=fraction,
                        worst=worst[:5],within10_cases=sum(w['excess']<=.1+1e-12 for w in worst),
                        median_build_seconds_sum=sum(r['medians'][m] for r in selected),
                        gate=not counts['uncovered'] and worst[0]['excess']<=.1+1e-12 and fraction>=.9)
        result['quality'][source]=out
    v=read(root/'validation.jsonl'); checks=[r for r in v if r['kind']=='proof_check']
    result['proof']=dict(shapes=len(checks),equalities=sum(r['equalities'] for r in checks),
                         capacity_queries=sum(r['queries'] for r in checks),all_pass=all(r['passed'] for r in checks),
                         raw_integer_plans=sum(x['raw'] for r in checks for x in r['counts'] if x['all_integer']),
                         compressed_integer_plans=sum(x['compressed'] for r in checks for x in r['counts'] if x['all_integer']),
                         independent=[r for r in v if r['kind']=='independent_validation'])
    if (root/'benchmark.jsonl').exists():
        b=[r for r in read(root/'benchmark.jsonl') if r['kind']=='benchmark']; result['benchmark']={}
        for n in (1,8,64,512):
            group=[r for r in b if r['queries']==n]
            result['benchmark'][n]=dict(cases=len(group),sum_medians={m:sum(r['medians'][m] for r in group)
                for m in ('brute_cached','compressed_cached','direct')})
    if (root/'audit.jsonl').exists():
        a=[r for r in read(root/'audit.jsonl') if r['kind']=='execution']
        result['audit']=dict(plans=len(a),all_valid=all(r['execution']['valid'] for r in a),
                             steps=sum(r['execution']['steps'] for r in a))
    return result

if __name__=='__main__': print(json.dumps(summary(Path(sys.argv[1])),indent=2,allow_nan=False))
