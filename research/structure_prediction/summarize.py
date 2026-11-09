"""Summarize completed cases only; generate reproducible scientific figures."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).parent


def main():
    records=[]
    for path in sorted((ROOT/'results').glob('*.json')):
        r=json.loads(path.read_text())
        if r.get('phase')=='complete':
            records.append(r)
    rows=[]
    fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
    for ax,r in zip(axes.flat,records):
        row=dict(case=r['case'],plateau_bytes=r['graph']['points'][-1]['capacity_bytes'],
                 first_measured_fusion_benefit_bytes=r['first_measured_fusion_benefit_bytes'],
                 local_search_seconds=sum(c['search_seconds'] for c in r['local_curves']),
                 graph_search_seconds=r['graph']['search_seconds'],evaluation=r['evaluation'])
        rows.append(row)
        right=max(r[k]['points'][-1]['capacity_bytes'] for k in ('graph','materialized'))*1.1
        for name,label in [('graph','Graph'),('materialized','Materialized')]:
            curve=r[name]['points']
            ax.step([p['capacity_bytes'] for p in curve]+[right],
                    [p['traffic_bytes'] for p in curve]+[curve[-1]['traffic_bytes']],where='post',label=label)
        for name,color in [('P1','tab:green'),('P2','tab:red')]:
            ax.axvline(r['predictions'][name]['plateau_bytes'],color=color,ls=':',label=name+' plateau')
        ax.set(title=r['case'],xlabel='GlobalBuffer capacity (bytes)',ylabel='DRAM traffic (bytes)')
        ax.grid(alpha=.2)
    axes.flat[0].legend(fontsize=8)
    fig.savefig(ROOT/'results/curves.png',dpi=160)
    fig.savefig(ROOT/'results/curves.svg')
    svg=ROOT/'results/curves.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    held=[r for r in rows if r['case'].startswith('held_')]
    aggregate={}
    for name in ('P0','P1','P2'):
        es=[r['evaluation'][name] for r in held]
        matched=sum(e['breakpoints']['matched'] for e in es)
        aggregate[name]=dict(heldout_count=len(es),
            mean_absolute_plateau_error=sum(e['absolute_relative_error'] for e in es)/len(es),
            breakpoint_micro_precision=matched/sum(e['breakpoints']['predicted_count'] for e in es),
            breakpoint_micro_recall=matched/sum(e['breakpoints']['actual_count'] for e in es))
    (ROOT/'results/summary.json').write_text(json.dumps(dict(cases=rows,heldout=aggregate),indent=2)+'\n')
    for r in rows:
        print(r['case'],r['plateau_bytes'],[r['evaluation'][n]['plateau_prediction'] for n in ('P0','P1','P2')],
              round(r['local_search_seconds'],2),round(r['graph_search_seconds'],2))
    print(json.dumps(aggregate,indent=2))


if __name__=='__main__':
    main()
