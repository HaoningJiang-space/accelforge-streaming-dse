"""Plot sampled native results; connectors are not a continuous cost model."""
import json
import math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research.motivation.summarize import summarize


def main():
    root=Path(__file__).with_name('results')
    records=[json.loads((root/f'{name}.json').read_text())
             for name in ('2mm_grid','2mm_threshold','2mm_edge')]
    unique={}
    for report in records:
        for row in report['points']:
            key=(tuple(row['shape']),row['capacity_bytes'],row['mode'])
            if key in unique:
                assert math.isclose(unique[key]['edp'],row['edp'],rel_tol=1e-9)
            unique[key]=row
    fig,axes=plt.subplots(2,1,figsize=(9,7),constrained_layout=True)
    for shape,color in zip(((2,8),(4,4),(8,2)),('tab:blue','tab:orange','tab:green')):
        for mode,style in (('graph','-'),('materialized','--')):
            rows=sorted((r for (s,c,m),r in unique.items() if s==shape and m==mode),key=lambda r:r['capacity_bytes'])
            axes[0].plot([r['capacity_bytes'] for r in rows],[r['edp']*1e14 for r in rows],
                         style,marker='o',markersize=3,color=color,linewidth=1,
                         label=f'{shape[0]}x{shape[1]} {mode}')
    axes[0].set(ylabel='Native EDP (1e-14 J s)',title='2mm: identical graph, different shape-dependent thresholds')
    axes[0].legend(fontsize=8,ncol=2)
    # Only compare capacities for which all three architectures were measured.
    capacities=sorted({r['capacity_bytes'] for report in records[:2] for r in report['points']})
    combined=dict(case=records[0]['case'],capacities=capacities,shapes=records[0]['shapes'],
                  points=[r for r in unique.values() if r['capacity_bytes'] in capacities])
    summary=summarize(combined)['capacities']
    assert all(r['status']=='ok' for r in summary)
    axes[1].plot(capacities,[100*r['best_tie_regret'] for r in summary],'o-',label='Strict materialized winner, then graph remap')
    axes[1].plot(capacities,[100*r['near_tie_shortlists'][0]['best_after_graph_remap'] for r in summary],
                 's--',label='Materialized 1% shortlist, then graph remap')
    axes[1].set(xlabel='GlobalBuffer capacity (bytes)',ylabel='Architecture regret (%)')
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=.2)
        for cap in (176,208):
            ax.axvline(cap,color='gray',linestyle=':',linewidth=.8)
    fig.suptitle('Small INT8 native FFM pilot, 16 PEs; sampled points, connectors only guide the eye',fontsize=10)
    fig.savefig(root/'pilot.svg')
    svg=root/'pilot.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    fig.savefig(root/'pilot.png',dpi=150)
    plt.close(fig)


if __name__=='__main__':
    main()
