"""Summarize repeated one-template runs and plot total cost versus new queries."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def run(directory):
    files = sorted(directory.glob('run[0-9]*.json'))
    runs = [json.loads(p.read_text()) for p in files]
    if len(runs) < 3 or not all(r['summary']['all_match'] for r in runs):
        raise ValueError('at least three complete successful runs required')
    reference = runs[0]
    for r in runs:
        if r['source_sha256'] != reference['source_sha256']:
            raise ValueError('cannot combine measurements from different source files')
        if [q['point'] for q in r['queries']] != [q['point'] for q in reference['queries']]:
            raise ValueError('query sequences must be identical')
        for key in ('stats','unique_cost_rows'):
            if r[key] != reference[key]:
                raise ValueError('logical work changed between repeats')
        if not all(all(q['checks'].values()) for q in r['queries']):
            raise ValueError('an earlier query failed validation')
    curves = {method:np.array([[q['cumulative'][method] for q in r['queries']] for r in runs])
              for method in ('parametric_s','strong_independent_s','direct_physical_s')}
    cached = [json.loads(p.read_text()) for p in sorted(directory.glob('cached[0-9]*.json'))]
    if len(cached) != len(runs) or not all(r.get('all_match') for r in cached):
        raise ValueError('matching cached-baseline process runs required')
    for r,source in zip(cached,files):
        if r['reference_sha256'] != hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError('cached baseline refers to a different reference run')
        if r['source_sha256']['benchmark_parametric_template.py'] != reference['source_sha256']['benchmark_parametric_template.py']:
            raise ValueError('cached baseline used different preparation/enumeration code')
        if [q['point'] for q in r['queries']] != [q['point'] for q in reference['queries']]:
            raise ValueError('cached baseline used a different query sequence')
        if not all(all(q['checks'].values()) for q in r['queries']):
            raise ValueError('cached baseline failed an earlier validation')
    curves['cached_independent_s'] = np.array([[q['cumulative_s'] for q in r['queries']] for r in cached])
    medians = {k:np.median(v,axis=0) for k,v in curves.items()}
    summary = dict(runs=len(runs),queries=len(reference['queries']),source_sha256=reference['source_sha256'],
                   preprocess_s=float(np.median([r['summary']['preprocess_s'] for r in runs])),
                   query_s=float(np.median([r['summary']['query_s'] for r in runs])),
                   totals_s={k:float(v[-1]) for k,v in medians.items()},
                   speedup_vs_strong=float(medians['strong_independent_s'][-1]/medians['parametric_s'][-1]),
                   speedup_vs_cached=float(medians['cached_independent_s'][-1]/medians['parametric_s'][-1]),
                   cached_work=[r['cache_work'] for r in cached],
                   break_even_queries=[r['summary']['measured_break_even'] for r in runs],
                   parametric_work=reference['stats'],unique_cost_rows=reference['unique_cost_rows'],
                   independent_work=reference['summary']['independent_work'],
                   checkpoints=[dict(queries=i,**{k:float(v[i-1]) for k,v in medians.items()})
                                for i in (1,2,4,8,16,32,64) if i<=len(reference['queries'])])
    (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7.2,4.2),layout='constrained')
    x=np.arange(1,len(reference['queries'])+1)
    for key,label,color in [('strong_independent_s','Shared preparation + independent FFM','#b45309'),
                             ('cached_independent_s','Shared preparation + existing prefix/compile cache','#15803d'),
                             ('parametric_s','Parameter regions (preprocessing included)','#0369a1')]:
        ax.plot(x,medians[key],label=label,color=color)
        ax.fill_between(x,curves[key].min(axis=0),curves[key].max(axis=0),color=color,alpha=.15)
    ax.set(xlabel='Number of previously unspecified architecture queries',
           ylabel='Cumulative time (seconds)',title='One fixed MatMul template — three process runs')
    ax.grid(alpha=.2)
    ax.legend(fontsize=9)
    fig.savefig(directory/'query_cost.png',dpi=180)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    run(p.parse_args().directory)
