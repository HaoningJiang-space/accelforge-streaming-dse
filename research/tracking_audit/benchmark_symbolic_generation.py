"""Benchmark shared generation against an explicitly selected checkout.

Use separate processes with the same PYTHONHASHSEED and thread limits for each
checkout. Run zero has cold case-specific symbolic caches; later runs are warm.
Validation and numeric-frontier serialization are outside the search timer.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument('--workload', default='glu')
    p.add_argument('--arch', default='nvdla')
    p.add_argument('--params', default='64,128,256')
    p.add_argument('--caps', default='0.03125,0.0625,0.25')
    p.add_argument('--factors', default='0.25,1,4,16')
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--prefix-bytes', type=int, default=0,
                   help='per-template prefix cache payload budget; 0 is the reference')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.repo = a.repo.resolve()
    sys.path[:0] = [str(a.repo), str(a.repo / 'research/tracking_audit')]
    import common
    from accelforge.mapper.FFM._pareto_df.df_convention import scaled_latency2col

    case = common.Case.parse(a.workload, a.arch, a.params)
    caps, factors = [float(x) for x in a.caps.split(',')], [float(x) for x in a.factors.split(',')]
    if a.repeats < 1 or a.prefix_bytes < 0 or any(not math.isfinite(x) or x <= 0 for x in caps + factors):
        p.error('repeats must be positive and capacities/factors finite and positive')
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    # Initialize numerical libraries on a different, tiny workload.
    common.search(common.build(common.Case('matmuls', 'nvdla', (1, 4, 8)), .125, common.EL))
    env = {**common.capacity_fractions_env(caps), 'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer'}
    env['AF_ENUMERATION_PREFIX_BYTES'] = str(a.prefix_bytes)
    enumeration_stats = {}
    original_make = common.make_pmappings

    def measured_make(*args, **kwargs):
        pm = original_make(*args, **kwargs)
        enumeration_stats.clear()
        measured = [getattr(j, 'enumeration_stats', {})
                    for jobs in pm.einsum2jobs.values() for j in jobs]
        enumeration_stats['templates_with_targets'] = sum(bool(s) for s in measured)
        for key in ('requests', 'expansions', 'hits', 'requested_rows', 'expanded_rows', 'evictions'):
            enumeration_stats[key] = sum(s.get(key, 0) for s in measured)
        enumeration_stats['max_template_payload_bytes'] = max(
            (s.get('peak_payload_bytes', 0) for s in measured), default=0)
        return pm

    common.make_pmappings = measured_make
    scaled = [f for f in factors if f != 1]
    if scaled:
        env['AF_LATENCY_SCALES'] = 'GlobalBuffer:' + ','.join(map(repr, scaled))
    report = {'case': str(case), 'caps': caps, 'factors': factors, 'jobs': 1,
              'prefix_bytes': a.prefix_bytes,
              'python': platform.python_version(),
              'pythonhashseed': os.environ.get('PYTHONHASHSEED'),
              'commit': subprocess.check_output(['git', '-C', str(a.repo), 'rev-parse', 'HEAD'], text=True).strip(),
              'diff': subprocess.check_output(['git', '-C', str(a.repo), 'diff', '--', 'accelforge'], text=True),
              'runs': [], 'frontiers': {}}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    for repeat in range(a.repeats):
        result, timing = common.search(common.build(case, max(caps), common.RU), env,
                                       {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'})
        numeric = result.data.select_dtypes(include='number')
        columns = sorted(numeric.columns)
        numeric = numeric[columns].drop_duplicates().sort_values(columns).reset_index(drop=True)
        frontier = {'columns': columns, 'values': numeric.values.tolist()}
        digest = hashlib.sha256(json.dumps(frontier, sort_keys=True).encode()).hexdigest()
        report['frontiers'].setdefault(digest, frontier)
        report['runs'].append({'repeat': repeat, **timing, 'search_s': timing['make_s'] + timing['join_s'],
                               'enumeration': dict(enumeration_stats),
                               'numeric_frontier_sha256': digest})
        a.output.write_text(json.dumps(report, indent=2))
        print('BENCHMARK', json.dumps(report['runs'][-1]), flush=True)
    picks = []
    for cap in caps:
        fits = common.rows_for_capacity(result.data, cap, max(caps))
        for factor in factors:
            col = common.LATENCY if factor == 1 else scaled_latency2col('GlobalBuffer', factor)
            row = common.best_row(fits, col)
            pick = common.check_pick(case, cap, row, latency_col=col, gb_latency_scale=factor)
            pick['factor'] = factor
            picks.append(pick)
    report['picks'] = picks
    report['all_picks_valid'] = all(pick['ok'] for pick in picks)
    report['numeric_frontier_stable'] = len({r['numeric_frontier_sha256'] for r in report['runs']}) == 1
    report['peak_rss_gb'] = common.peak_rss_gb()
    a.output.write_text(json.dumps(report, indent=2))
    return 0 if report['all_picks_valid'] and report['numeric_frontier_stable'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
