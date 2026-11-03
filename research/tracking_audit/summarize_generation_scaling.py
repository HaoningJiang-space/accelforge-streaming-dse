"""Compare saved K curves only after exact frontiers and query validation agree."""
import argparse
import json
from pathlib import Path
import statistics


def compare(reference, changed):
    for key in ('case', 'caps', 'factors', 'jobs', 'python', 'pythonhashseed', 'phase_timers'):
        if reference.get(key) != changed.get(key):
            raise ValueError(f'incomparable {key}')
    if reference.get('cprofile') or changed.get('cprofile'):
        raise ValueError('cProfile times are diagnostic, not a speed comparison')
    signatures = []
    for data in (reference, changed):
        if not data.get('all_picks_valid') or not data.get('numeric_frontier_stable'):
            raise ValueError('candidate validation failed or incomplete')
        if len(data['runs']) < 2:
            raise ValueError('a cold and at least one warm run are required')
        signatures.append({run['numeric_frontier_sha256'] for run in data['runs']})
    if signatures[0] != signatures[1] or len(signatures[0]) != 1:
        raise ValueError('complete numeric frontiers differ')
    a, b = reference['runs'], changed['runs']
    warm_a, warm_b = statistics.mean(r['search_s'] for r in a[1:]), statistics.mean(r['search_s'] for r in b[1:])
    return dict(cold_reference_s=a[0]['search_s'], cold_changed_s=b[0]['search_s'],
                warm_reference_s=warm_a, warm_changed_s=warm_b, warm_speedup=warm_a / warm_b,
                warm_runs=[len(a)-1, len(b)-1], exact_frontier=True, all_picks_valid=True,
                frontier_sha256=next(iter(signatures[0])),
                reference_phases=a[-1].get('phases'), changed_phases=b[-1].get('phases'),
                pareto_reuse=b[-1].get('enumeration_pareto'),
                reference_rss_gb=reference['peak_rss_gb'], changed_rss_gb=changed['peak_rss_gb'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--changed', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    names = {f.name for f in a.reference.glob('*-k*.json')}
    if not names or names != {f.name for f in a.changed.glob('*-k*.json')}:
        p.error('both directories must contain the same complete set of K reports')
    report = {}
    for name in sorted(names):
        ref = json.loads((a.reference / name).read_text())
        changed = json.loads((a.changed / name).read_text())
        report[name] = compare(ref, changed)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    for name, row in report.items():
        print(f"{name}: {row['warm_reference_s']:.3f} -> {row['warm_changed_s']:.3f} s, "
              f"{row['warm_speedup']:.3f}x; exact frontier and validated picks")


if __name__ == '__main__':
    main()
