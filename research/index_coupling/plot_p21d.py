"""Frozen P21d counterexample and independent accounting discrepancy."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.hashsalt']='p21d'
import matplotlib.pyplot as plt
from research.index_coupling.graph.analysis import traffic_at


def main(directory):
    records={arm:json.loads((directory/f'00_{arm}.json').read_text())
             for arm in ('structural','unrestricted')}
    diagnostics=json.loads((directory/'diagnostics.json').read_text())
    mismatch=next(r for r in diagnostics['accounting_mismatches'] if r['case']==7)
    actual_x=mismatch['execution']['writes']['X']
    duplicate_x=mismatch['model_ledger']['writes']['X']-actual_x
    fig,axes=plt.subplots(1,2,figsize=(10.8,4.1))
    for arm,label,color,style in (('structural','Frozen structural cuts','#d87015','--'),
                                  ('unrestricted','Unrestricted curve','#1261a0','-')):
        points=records[arm]['points'];xs=range(3,27)
        axes[0].step(xs,[traffic_at(c,points) for c in xs],where='post',
                     color=color,linestyle=style,label=label,linewidth=2)
        axes[0].scatter([4],[traffic_at(4,points)],color=color,s=22,zorder=5)
    axes[0].set(xlabel='Capacity (unit-byte elements)',ylabel='DRAM transfers',
                title='Valid counterexample: (8,2,4), depth 4')
    axes[0].legend(frameon=False,fontsize=8)
    axes[0].annotate('C=4: 336 versus 328',xy=(4,336),xytext=(8,355),
                     arrowprops=dict(arrowstyle='->',color='#555555'),fontsize=9)
    axes[1].bar([0],[actual_x],color='#1261a0',label='One final X write')
    axes[1].bar([0],[duplicate_x],bottom=[actual_x],color='#d87015',label='Duplicate nested charge')
    axes[1].bar([1],[actual_x],color='#1261a0')
    axes[1].set(xticks=[0,1],xticklabels=['Model ledger','Cell execution'],ylabel='X write transfers',
                title='Separate validity failure: (4,8,2), reads X',ylim=(0,80))
    axes[1].legend(frameon=False,fontsize=8,loc='upper right')
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.15)
    fig.suptitle('P21d: keep a structural counterexample separate from an accounting defect',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.93))
    fig.savefig(directory/'findings.png',dpi=180)
    path=directory/'findings.svg'
    fig.savefig(path,metadata={'Date':None})
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    main(parser.parse_args().directory)
