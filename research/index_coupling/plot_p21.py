"""Publication-style static P21 comparison; reads saved results only."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research.index_coupling.graph.analysis import traffic_at


def main(directory):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharex=True)
    for ax, index, title in zip(axes, (6, 7), ('P21a: H does not read X', 'P21b: H reads X')):
        data = json.loads((directory / f'case_{index:02d}.json').read_text())['result']['interfaces'][0]
        curves = data['curves']
        hi = max(c for p in curves.values() for c, q in p) + 2
        xs = list(range(3, hi + 1))
        for key, label, color, style in (
                ('coarse', 'Capacity-only prediction', '#d87015', '--'),
                ('actual', 'Exact fixed-boundary curve', '#1261a0', '-'),
                ('unrestricted', 'Unrestricted fusion', '#737373', ':')):
            ax.step(xs, [traffic_at(c, curves[key]) for c in xs], where='post',
                    label=label, color=color, linestyle=style, linewidth=2)
        ax.scatter([c for c, q in curves['predicted']], [q for c, q in curves['predicted']],
                   facecolors='none', edgecolors='#1261a0', s=44, zorder=5,
                   label='Conditional-interface prediction')
        ax.set_title(title, loc='left', fontsize=11, weight='bold')
        ax.set_xlabel('Buffer capacity (unit-byte elements)')
        ax.grid(alpha=.15)
        ax.spines[['top', 'right']].set_visible(False)
    axes[0].set_ylabel('DRAM traffic (unit-byte transfers)')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=2, frameon=False, fontsize=9)
    fig.suptitle('10 operators; (I, K, L) = (2, 2, 4); serial, no recomputation', fontsize=11)
    fig.tight_layout(rect=(0, .17, 1, .95))
    fig.savefig(directory / 'curves.png', dpi=180)
    fig.savefig(directory / 'curves.svg')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    main(parser.parse_args().directory)
