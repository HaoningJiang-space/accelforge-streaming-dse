"""Render saved shape/capacity picks and measured whole-grid DSE times."""
import argparse
import json
import math
import statistics
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--picks', type=Path, required=True)
    parser.add_argument('--timings', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    picks_report = json.loads(args.picks.read_text())
    timings = json.loads(args.timings.read_text())
    independent = next(r for r in picks_report['runs'] if r['method'] == 'independent')
    picks = independent['picks']
    assert all(p['ok'] and p['feasible'] for p in picks)
    shapes = [tuple(s) for s in picks_report['config']['shapes']]
    capacities = picks_report['config']['capacities_bytes']
    lookup = {(tuple(p['shape']), p['capacity_bytes']): p for p in picks}
    values = np.array([[lookup[(s, c)]['edp'] for s in shapes] for c in capacities])
    exponent = math.floor(math.log10(values.min()))
    scale = 10.**exponent
    mapping_ids = sorted(set(p['mapping_id'] for p in picks))
    labels = {identity: 'M' + str(i + 1) for i, identity in enumerate(mapping_ids)}
    figure, (ax, bar) = plt.subplots(1, 2, figsize=(12.2, 4.6), gridspec_kw={'width_ratios': [1.4, 1]})
    figure.subplots_adjust(left=.09, right=.97, top=.83, bottom=.21, wspace=.45)
    ax.imshow(values / scale, cmap='Blues', aspect='auto', vmin=0, vmax=values.max() / scale * 1.4)
    for i, c in enumerate(capacities):
        for j, s in enumerate(shapes):
            p = lookup[(s, c)]
            ax.text(j, i, f"{p['edp']/scale:.3f}\n{labels[p['mapping_id']]}", ha='center', va='center', fontsize=11)
        winner = int(np.argmin(values[i]))
        ax.add_patch(Rectangle((winner-.48, i-.48), .96, .96, fill=False, linewidth=2.4, edgecolor='#c1490b'))
    ax.set_xticks(range(len(shapes)), [f'{a} × {b}' for a, b in shapes])
    def capacity_label(c):
        return f'{c//1024} KiB' if c % 1024 == 0 else (f'{(c+1)//1024} KiB − 1 B' if (c+1)%1024 == 0 else f'{c} B')
    ax.set_yticks(range(len(capacities)), [capacity_label(c) for c in capacities])
    ax.set_xlabel(f'Array shape ({math.prod(shapes[0]):,} PEs)')
    ax.set_ylabel('GlobalBuffer capacity')
    ax.set_title(f'Independent-search EDP (×10$^{{{exponent}}}$ J s)\nOutline: best shape at that capacity', fontsize=11)
    names = ('max_frontier', 'local_reuse', 'reuse_frontier')
    measurements = [[r['dse_s'] for r in timings['runs'] if r['repeat'] >= 0 and r['method'] == m] for m in names]
    medians = [statistics.median(v) for v in measurements]
    bar.bar(range(3), medians, color=['#536578', '#8aa6b6', '#226b85'], width=.6)
    for i, (samples, median) in enumerate(zip(measurements, medians)):
        bar.scatter(np.full(len(samples), i), samples, color='#171717', s=18, zorder=3)
        bar.text(i, max(samples) + .025*max(medians), f'{median:.2f} s', ha='center', fontsize=11)
    bar.set_xticks(range(3), ['Per-shape\nmax frontier', 'Reuse within\neach shape', 'Reuse across\nshapes'])
    bar.set_ylabel('Whole-grid DSE wall time (seconds)')
    bar.set_ylim(0, max(map(max, measurements))*1.17)
    bar.set_title('Warm medians; dots show individual runs\nIncludes preparation, search and queries', fontsize=11)
    figure.suptitle(picks_report['config']['workload'], fontsize=14)
    figure.text(.09, .065, 'M labels identify selected mapping structures; they do not count all tied optima.\n'
                'Reconstruction validation is outside timing. Fixed cost model; no wiring, clock or area adjustment.', fontsize=9)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ('.png', '.pdf'):
        figure.savefig(args.output.with_suffix(suffix), dpi=180)
    args.output.with_suffix('.mappings.json').write_text(json.dumps({
        labels[mid]: next({'mapping_id': mid, 'mapping': p['mapping']} for p in picks if p['mapping_id'] == mid)
        for mid in mapping_ids}, indent=2) + '\n')


if __name__ == '__main__':
    main()
