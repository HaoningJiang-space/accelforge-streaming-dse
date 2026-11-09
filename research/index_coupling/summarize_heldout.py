"""Summarize frozen held-out records; no model evaluation."""
from collections import Counter
import json
from pathlib import Path
import statistics
import sys
from .validate_constructive import MODES


def summarize(path):
    records=[json.loads(x) for x in path.read_text().splitlines()]
    rows=[r for r in records if r['kind']=='case']
    output={'cases':len(rows),'errors':[r for r in records if r['kind']=='error'],'sets':{}}
    for source in ('archived','fresh','all'):
        cases=[r for r in rows if source=='all' or r['source']==source]
        out={}
        for mode in MODES:
            budgets=sum(r['scores'][mode]['integer_budgets'] for r in cases)
            counts=Counter(); knots=Counter(); worst=[]; ratios=[]
            for r in cases:
                s=r['scores'][mode]; counts.update(s['integer_counts']); knots.update(s['knot_counts'])
                worst.append(dict(shape=r['shape'],cross=r['cross'],excess=s['worst_traffic_excess'],capacity=s['worst_capacity']))
                if r['reference_samples']:
                    ratios.append(statistics.median(r['reference_samples'])/r['medians'][mode])
            worst.sort(key=lambda w:w['excess'],reverse=True)
            within5=counts['within5']/budgets if budgets else None
            maxloss=worst[0]['excess'] if worst else None
            out[mode]=dict(instances=len(cases),integer_budgets=budgets,
                          integer_counts=dict(counts),knot_counts=dict(knots),within5=within5,
                          worst=worst[:8],all_instances_within10=sum(w['excess']<=.1+1e-12 for w in worst),
                          sum_median_constructor_seconds=sum(r['medians'][mode] for r in cases),
                          median_reference_to_constructor_ratio=statistics.median(ratios) if ratios else None,
                          quality_gate=bool(budgets and not counts['uncovered'] and maxloss<=.1+1e-12 and within5>=.9),
                          timing_gate=all(x>=2 for x in ratios) if ratios else None)
        output['sets'][source]=out
    fresh=[r for r in rows if r['source']=='fresh']
    output['fresh_reference_sum_medians_seconds']=sum(statistics.median(r['reference_samples']) for r in fresh)
    return output

if __name__=='__main__':
    print(json.dumps(summarize(Path(sys.argv[1])),indent=2,allow_nan=False))
