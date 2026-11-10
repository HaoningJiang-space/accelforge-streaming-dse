"""Static plots from the exploratory cut controls, with no solver execution."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.hashsalt'] = 'p21-cuts'
import matplotlib.pyplot as plt
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.run_p21 import frontier


def main(directory):
    r=json.loads((directory/'case_7.json').read_text())['result']
    tail=json.loads((directory/'tail_7.json').read_text())['result']
    original=json.loads((directory.parent/'p21/case_07.json').read_text())['result']['interfaces'][0]
    five=frontier(r['menu_union']+tail['menu_union'])
    fig,axes=plt.subplots(1,2,figsize=(11,4.3))
    xs=range(3,31)
    for points,label,color,style in (
            (r['frozen'],'Frozen interface','#888888',':'),
            (r['output_resident_lifted'],'Output retention + outer loops','#8056a3','--'),
            (r['menu_union'],'Four cut families','#d87015','--'),
            (r['unrestricted'],'Unrestricted curve','#1261a0','-')):
        axes[0].step(xs,[traffic_at(c,points) for c in xs],where='post',label=label,
                     color=color,linestyle=style,linewidth=1.8)
    axes[0].scatter([c for c,q in five],[q for c,q in five],facecolors='none',
                    edgecolors='#1261a0',s=36,label='Five-family envelope',zorder=5)
    axes[0].set(xlabel='Whole-graph capacity C',ylabel='DRAM traffic Q',
                title='Moving cuts closes the remaining gap')
    cold,resident=original['children']['cold'][1],original['children']['resident'][1]
    ys=range(3,23)
    axes[1].step(ys,[traffic_at(c,cold)-traffic_at(c,resident) for c in ys],
                 where='post',color='#1261a0',linewidth=2,label='Residency value V_X(c)')
    axes[1].axhline(original['s'],color='#d87015',linestyle='--',label='One compulsory X read (s = 4)')
    axes[1].set(xlabel='H local capacity c',ylabel='Traffic saved by resident X',
                title='Residency value is capacity dependent',ylim=(0,18))
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
        ax.grid(alpha=.15)
        ax.legend(fontsize=8,frameon=False,loc='upper right')
    fig.suptitle('Exploratory P21 follow-up: (I,K,L) = (2,2,4), 10 operators, H reads X',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.93))
    fig.savefig(directory/'analysis.png',dpi=180)
    svg=directory/'analysis.svg'
    fig.savefig(svg,metadata={'Date':None})
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    main(parser.parse_args().directory)
