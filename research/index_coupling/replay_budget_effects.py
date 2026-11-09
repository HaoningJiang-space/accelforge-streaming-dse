"""Replay established coupling examples at a common buffer budget.

Post-observation effect reporting and projected-cache regression, not a new
prediction or a hardware benchmark. Targets are from CONSTRUCTIVE_RESULTS.md.
Both computation patterns keep their own semantics; no graph rewrite is claimed.
"""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import subprocess

from .constructive_fork import candidates, execute
from .curve_model import curve
from .nest_model import coupling
from .simulate_nest import simulate

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path(__file__).parent
CASES = (((8, 8, 8, 8), 576), ((16, 16, 16, 16), 2304),
         ((32, 4, 32, 16), 3456))


def emit(record):
    print(json.dumps(record, allow_nan=False), flush=True)


def replay():
    reference_path = DIRECTORY / 'results/coupling_sweep.jsonl'
    archived = {tuple(r['shape']): r for r in
                map(json.loads, reference_path.read_text().splitlines())}
    hashes = {name: hashlib.sha256((DIRECTORY / name).read_bytes()).hexdigest()
              for name in ('curve_model.py', 'nest_model.py', 'simulate_nest.py',
                           'constructive_fork.py', 'results/coupling_sweep.jsonl')}
    emit(dict(kind='metadata', commit=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        tracked_dirty=bool(subprocess.check_output(
            ['git', 'diff', '--name-only', 'HEAD'], cwd=ROOT, text=True)),
        source_hashes=hashes, selection='existing constructive focus cases and targets',
        semantics='unit-byte cells; two-level memory; no recomputation',
        purpose='common-budget effect replay, not algorithm speedup'))
    for shape, target in CASES:
        graphs = {name: coupling(*shape, name == 'cross') for name in ('same', 'cross')}
        curves = {name: curve(graph, witness=True) for name, graph in graphs.items()}
        for name, points in curves.items():
            if [list(p[:2]) for p in points] != archived[shape][name + '_wt']:
                raise AssertionError(('archive mismatch', shape, name))
        thresholds = {name: min(c for c, q, _ in p if q <= target)
                      for name, p in curves.items()}
        budget = thresholds['same']
        records = []
        for name, capacity, label in (('same', budget, 'same_common_budget'),
                                      ('cross', budget, 'cross_common_budget'),
                                      ('cross', thresholds['cross'], 'cross_target')):
            row = min((p for p in curves[name] if p[0] <= capacity),
                      key=lambda p: (p[1], p[0]))
            actual = simulate(graphs[name], row[2])
            if not actual['valid'] or (actual['peak'], actual['traffic']) != row[:2]:
                raise AssertionError((shape, label, actual, row[:2]))
            records.append(dict(label=label, budget=capacity, peak=row[0], traffic=row[1],
                                witness=row[2], execution=actual))
        # These plans use a wider, incomplete constructive family. They demonstrate
        # feasibility; their minimum is not a lower bound for all integer tilings.
        wider = {}
        for name in ('same', 'cross'):
            plan = min((p for p in candidates(shape, name == 'cross', all_tiles=True)
                        if p.metrics()['traffic'] <= target),
                       key=lambda p: (p.metrics()['peak'], p.metrics()['traffic']))
            actual = execute(plan)
            if not actual['valid'] or any(actual[k] != plan.metrics()[k]
                                         for k in ('peak', 'traffic', 'reads', 'writes')):
                raise AssertionError((shape, name, plan, actual))
            wider[name] = dict(plan=plan.record(), execution=actual)
        qs, qc = records[0]['traffic'], records[1]['traffic']
        emit(dict(kind='case', shape=shape, target=target, common_budget=budget,
                  recursive_thresholds=thresholds, traffic_premium_bytes=qc-qs,
                  traffic_premium_fraction=(qc-qs)/qs,
                  capacity_premium_fraction=(thresholds['cross']-budget)/budget,
                  reference_curves={k: [p[:2] for p in v] for k, v in curves.items()},
                  replay=records, wider_family=wider, passed=True))
        del curves, graphs, records, wider
        gc.collect()
    emit(dict(kind='summary', cases=len(CASES), recursive_witnesses=3*len(CASES),
              wider_family_executions=2*len(CASES), passed=True))


def plot(input_path, output_dir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows = [json.loads(s) for s in Path(input_path).read_text().splitlines()]
    records = [r for r in rows if r['kind'] == 'case']
    if len(records) != len(CASES) or not all(r['passed'] for r in records):
        raise ValueError('three complete replay cases required')
    if rows[-1] != dict(kind='summary', cases=3, recursive_witnesses=9,
                        wider_family_executions=6, passed=True):
        raise ValueError('successful replay summary required')
    colors = dict(same='#16688b', cross='#b14b26')
    fig, axes = plt.subplots(1, 3, figsize=(12.8, 4.6))
    for ax, r in zip(axes, records):
        for name in ('same', 'cross'):
            points = r['reference_curves'][name]
            xs, ys = zip(*points)
            ax.step(xs, ys, where='post', color=colors[name], lw=2,
                    label='Aligned' if name == 'same' else 'Crossed')
        s, c = r['recursive_thresholds']['same'], r['recursive_thresholds']['cross']
        target = r['target']
        ax.hlines(target, s, c, color='#444444', linestyles='dotted', lw=1)
        ax.scatter([s, c], [target, target], c=[colors['same'], colors['cross']], zorder=4)
        ax.annotate('', xy=(c, target*.84), xytext=(s, target*.84),
                    arrowprops=dict(arrowstyle='<->', color='#444444'))
        ax.text((s+c)/2, target*.73, f'{s} -> {c} B ({c/s:.2f}x)', ha='center', fontsize=9)
        wider = r['wider_family']['cross']['execution']
        if wider['peak'] < c:
            ax.scatter([wider['peak']], [wider['traffic']], marker='D', s=45,
                       facecolors='white', edgecolors=colors['cross'], zorder=5,
                       label='Wider-family witness')
        fixed = r['replay'][:2]
        ax.text(.04, .97, f'At {s} B: {fixed[0]["traffic"]} vs {fixed[1]["traffic"]} B\n'
                f'Crossed traffic +{100*r["traffic_premium_fraction"]:.1f}%',
                transform=ax.transAxes, va='top', fontsize=10,
                bbox=dict(boxstyle='round,pad=.4', facecolor='white', alpha=.9, edgecolor='#dddddd'))
        ax.set_title('I,J,K,L = ' + ','.join(map(str, r['shape'])), fontsize=11)
        ax.set_xlabel('Buffer capacity (unit-byte cells)')
        ax.set_yscale('log', base=2)
        ax.set_xlim(0, max(p[0] for p in r['reference_curves']['cross'])*1.08)
        ax.set_ylim(min(p[1] for p in r['reference_curves']['same'])*.72,
                    max(p[1] for p in r['reference_curves']['cross'])*1.75)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8, loc='upper right', bbox_to_anchor=(1, .79))
    axes[0].set_ylabel('Total DRAM traffic (modeled bytes, log scale)')
    fig.suptitle('Index coupling changes the capacity needed for the same traffic target', fontsize=13)
    fig.text(.5, .015, 'Solid curves: exact within the recursive tile grammar. '
             'Marker: executable wider-family plan, not a global optimum. '
             'All three cases were selected in earlier work.', ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .055, 1, .93))
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for suffix in ('png', 'svg'):
        fig.savefig(output / ('common_budget_effects.' + suffix), dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='mode', required=True)
    commands.add_parser('replay')
    plotting = commands.add_parser('plot')
    plotting.add_argument('input')
    plotting.add_argument('output')
    args = parser.parse_args()
    if args.mode == 'replay':
        replay()
    else:
        plot(args.input, args.output)
