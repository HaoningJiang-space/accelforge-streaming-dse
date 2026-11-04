"""Compare whole-operator runs, refusing candidate or full-frontier mismatches."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from research.tracking_audit.parametric_template import Box


def logical_stats(stats):
    return {k:v for k,v in stats.items() if not k.endswith('_s') and k!='templates'} | {
        'templates':[{k:v for k,v in t.items() if not k.endswith('_s')} for t in stats['templates']]}


def run(directory):
    modes = ('regions','independent','cached')
    runs = {m:[json.loads(p.read_text()) for p in sorted(directory.glob(f'{m}[0-9]*.json'))] for m in modes}
    if any(len(v)!=3 for v in runs.values()):
        raise ValueError('exactly three completed process runs per method required')
    base = runs['regions'][0]
    points = [q['point'] for q in base['queries']]
    for mode,group in runs.items():
        for r in group:
            if not r.get('all_picks_valid') or r['mode']!=mode or r['source_sha256']!=base['source_sha256']:
                raise ValueError('incomplete validation or different code')
            if r['template_ids']!=base['template_ids'] or [q['point'] for q in r['queries']]!=points:
                raise ValueError('different template set or query sequence')
            if mode=='regions' and logical_stats(r['compilation'])!=logical_stats(base['compilation']):
                raise ValueError('region workload changed between repeats')
            for q,ref in zip(r['queries'],base['queries']):
                if q['candidates']!=ref['candidates'] or not np.array_equal(q['frontier'],ref['frontier']):
                    raise ValueError(f'{mode} complete candidate/frontier mismatch at {q["point"]}')
                if not q['validation']['ok'] or not q['validation']['exact_gb_match']:
                    raise ValueError('an earlier selected source failed re-evaluation')
    curves = {mode:np.array([[q['cumulative_s'] for q in r['queries']] for r in group]) for mode,group in runs.items()}
    medians = {m:np.median(v,axis=0) for m,v in curves.items()}
    counts = [1,4,16,32,64,128,256]
    work = {m:{k:sum(q['work'].get(k,0) for q in runs[m][0]['queries'])
               for k in ('state_expansion_requests','expanded_row_requests','cost_rows')}
            for m in ('independent','cached')}
    work['cached']['actual_cache_work'] = runs['cached'][0]['cache_work']
    comp = base['compilation']
    ends = np.cumsum([t['cost_rows'] for t in comp['templates']])
    winners,present = Counter(),Counter()
    for q in base['queries']:
        matches = [r for r in base['regions'] if any(
            Box(tuple(tuple(v) for v in box)).contains(q['point']) for box in r['boxes'])]
        if len(matches)!=1:
            raise ValueError('saved terminal regions do not uniquely cover a query')
        region = matches[0]
        f = np.array(region['frontier'])
        if not len(f):
            continue
        i = int(np.argmin(f[:,0]*f[:,1]))
        winners[int(np.searchsorted(ends,region['ids'][i],side='right'))] += 1
        for t in set(int(np.searchsorted(ends,source,side='right')) for source in region['ids']):
            present[t] += 1
    work['regions'] = {key:sum(t[key] for t in comp['templates']) for key in
                       ('state_expansions','expanded_rows','pareto_calls','value_evaluations','cost_rows')}
    summary = dict(queries=len(points),runs_per_mode=3,all_complete_frontiers_and_candidates_match=True,
        medians_s={m:float(v[-1]) for m,v in medians.items()},
        preprocess_s={m:[r['preprocess_s'] for r in group] for m,group in runs.items()},
        peak_rss_gib={m:[r['search_peak_rss_gib'] for r in group] for m,group in runs.items()},
        speedup_at_end={m:float(medians[m][-1]/medians['regions'][-1]) for m in ('independent','cached')},
        paired_break_even={m:[next((i+1 for i,(a,b) in enumerate(zip(curves['regions'][j],curves[m][j])) if a<=b),None)
                              for j in range(3)] for m in ('independent','cached')},
        checkpoints=[dict(queries=n,**{m:float(v[n-1]) for m,v in medians.items()}) for n in counts if n<=len(points)],
        work=work,logical_compilation=logical_stats(comp),source_sha256=base['source_sha256'])
    summary['selected_template_counts'] = dict(sorted(winners.items()))
    summary['frontier_template_presence'] = dict(sorted(present.items()))
    summary['tie_caveat'] = 'Counts use the compiled stable source-ID tie rule; they do not establish exclusive optimality.'
    (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7.4,4.4),layout='constrained')
    x=np.arange(1,len(points)+1)
    for m,label,color in [('regions','All-template regions (preprocessing included)','#0369a1'),
                           ('independent','Prepared per-query FFM','#b45309'),
                           ('cached','Prepared FFM + existing cache','#15803d')]:
        ax.plot(x,medians[m],label=label,color=color)
        ax.fill_between(x,curves[m].min(axis=0),curves[m].max(axis=0),color=color,alpha=.15)
    ax.set(xlabel='Previously unspecified architecture queries',ylabel='Cumulative search + reconstruction (s)',
           title='All six MatMul templates — three separate process runs per method')
    ax.grid(alpha=.2)
    ax.legend(fontsize=9)
    fig.savefig(directory/'query_cost.png',dpi=180)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('work','logical_compilation')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    run(p.parse_args().directory)
