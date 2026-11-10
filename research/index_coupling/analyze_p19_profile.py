"""Post-hoc P19 profile analysis; reads saved curves, runs no mapping search.

Reuses P18's exact interval integration, including its inverse-curve area check.
Does not change the frozen P19c width criterion or its failed verdict.
"""
import argparse
import hashlib
import json
from pathlib import Path

from research.index_coupling.analyze_p18_profile import profile
from research.index_coupling.graph.analysis import capacity_for, delta

ROLES = ('kkkkki', 'kkkkii', 'kkkiii')
BASE = 'kkkkkk'


def analyze(path):
    data = path.read_bytes()
    rows = [json.loads(line) for line in data.splitlines()]
    curves = {(tuple(r['shape']), r['roles']): r['points'] for r in rows}
    shapes = sorted({shape for shape, _ in curves})
    assert len(rows) == len(curves) == 32 and len(shapes) == 8
    assert set(curves) == {(s, r) for s in shapes for r in (BASE,) + ROLES}
    result = {'input_sha256': hashlib.sha256(data).hexdigest(),
              'profile_implementation_sha256': hashlib.sha256(
                  Path(__file__).with_name('analyze_p18_profile.py').read_bytes()).hexdigest(),
              'scope': 'Post-hoc; fixed consumer order, divisible power-of-two grammar.',
              'new_mapping_evaluations': 0,
              'frozen_P19c_verdict': 'failed, 0/8; unchanged', 'shapes': []}
    for shape in shapes:
        cv = {r: curves[shape, r] for r in (BASE,) + ROLES}
        q_hi = max(t - p[-1][1] for p in cv.values() for _, t in p)
        profiles = {}
        for role in ROLES:
            p = profile(cv[BASE], cv[role], q_hi)
            refined = profile(cv[BASE], cv[role], q_hi, refined=True)
            for k in ('signed_area', 'positive_area', 'positive_width',
                      'negative_width', 'mean_relative_gap', 'max_gap', 'min_gap'):
                assert p[k] == refined[k], (shape, role, k)
            profiles[role] = p
        # A crossing is checked on the complete union of relevant knots.
        gaps = delta(cv['kkkkii'], cv['kkkiii'])
        result['shapes'].append({'shape': shape, 'profiles': profiles,
                                'b3_vs_b2_crosses': min(d for _, d, _ in gaps) < 0
                                < max(d for _, d, _ in gaps)})
    ps = [s['profiles'] for s in result['shapes']]
    result['summary'] = {
        'shapes': len(ps),
        'signed_area_b1_lt_b2_lt_b3': sum(p[ROLES[0]]['signed_area'] <
            p[ROLES[1]]['signed_area'] < p[ROLES[2]]['signed_area'] for p in ps),
        'b3_wider_positive_domain_than_b2': sum(
            p[ROLES[2]]['positive_width'] > p[ROLES[1]]['positive_width'] for p in ps),
        'b3_higher_mean_relative_gap_than_b2': sum(
            p[ROLES[2]]['mean_relative_gap'] > p[ROLES[1]]['mean_relative_gap'] for p in ps),
        'b3_vs_b2_crossings': sum(s['b3_vs_b2_crosses'] for s in result['shapes']),
    }
    shape = (16, 4, 16, 4)
    cv = {r: curves[shape, r] for r in (BASE,) + ROLES}
    floor = cv[BASE][-1][1]
    result['example'] = {'shape': shape, 'compulsory_traffic': floor,
        'queries': [{'extra_traffic_budget': q, 'total_traffic_budget': q + floor,
                     'capacity': {r: capacity_for(p, q) for r, p in cv.items()}}
                    for q in (448, 1728)]}
    return result, cv


def plot(path, cv):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'pdf.fonttype': 42})
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.1), constrained_layout=True)
    labels = {BASE: 'All same direction', 'kkkkki': 'b = 1',
              'kkkkii': 'b = 2', 'kkkiii': 'b = 3'}
    colors = {BASE: '#667085', 'kkkkki': '#059669',
              'kkkkii': '#2563eb', 'kkkiii': '#d97706'}
    floor = cv[BASE][-1][1]
    qs = sorted({t - p[-1][1] for p in cv.values() for _, t in p})
    for role, p in cv.items():
        x = [q + floor for q in qs]
        y = [capacity_for(p, q) for q in qs]
        axes[0].step(x, y, where='post', label=labels[role], color=colors[role])
        if role != BASE:
            axes[1].step(x, [v - capacity_for(cv[BASE], q) for v, q in zip(y, qs)],
                         where='post', label=labels[role], color=colors[role])
    axes[0].set(xscale='log', xlabel='Allowed total DRAM traffic (B, log scale)',
                ylabel='Required capacity (B)', title='Full inverse curves')
    axes[0].legend(frameon=False, fontsize=9)
    axes[1].set(xlim=(floor, 4000), xlabel='Allowed total DRAM traffic (B)',
                ylabel='Extra capacity over all-same (B)', title='Capacity-gap detail')
    axes[1].annotate('b=3: +128 B\nb=2: +64 B', xy=(1344, 128),
                     xytext=(1800, 106), arrowprops={'arrowstyle': '->', 'color': '#475467'})
    axes[1].annotate('b=3: +0 B\nb=2: +14 B', xy=(2624, 0),
                     xytext=(2900, 42), arrowprops={'arrowstyle': '->', 'color': '#475467'})
    for ax in axes:
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('P19: a larger worst-case gap does not imply a worse curve\n'
                 '(I,J,K,L)=(16,4,16,4); fixed order and power-of-two tiles', fontsize=12)
    fig.savefig(path.with_suffix('.png'), dpi=180)
    fig.savefig(path.with_suffix('.pdf'))
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=Path(__file__).parent / 'results/p19_profile.json')
    args = ap.parse_args()
    result, cv = analyze(Path(__file__).parent / 'results/p19.jsonl')
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    plot(args.output, cv)
    print(json.dumps({'summary': result['summary'], 'example': result['example']}, indent=2))


if __name__ == '__main__':
    main()
