"""Benchmark shared generation against an explicitly selected checkout.

Use separate processes with the same PYTHONHASHSEED and thread limits for each
checkout. Run zero has cold case-specific symbolic caches; later runs are warm.
Validation and numeric-frontier serialization are outside the search timer.
"""
import argparse
from contextlib import nullcontext
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
    p.add_argument('--pareto-bytes', type=int, default=0,
                   help='per-template exact Pareto cache payload budget; 0 disables reuse')
    p.add_argument('--target-mode', choices=('independent', 'events'), default='independent')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--phases', action='store_true', help='serial phase timers (diagnostic)')
    p.add_argument('--cprofile', action='store_true', help='save detailed profiles; times are profiled')
    a = p.parse_args()
    a.repo = a.repo.resolve()
    sys.path[:0] = [str(a.repo), str(a.repo / 'research/tracking_audit')]
    import common
    from generation_profile import GenerationPhases
    from accelforge.mapper.FFM._pareto_df.df_convention import scaled_latency2col

    case = common.Case.parse(a.workload, a.arch, a.params)
    caps, factors = [float(x) for x in a.caps.split(',')], [float(x) for x in a.factors.split(',')]
    if a.repeats < 1 or min(a.prefix_bytes, a.pareto_bytes) < 0 or any(not math.isfinite(x) or x <= 0 for x in caps + factors):
        p.error('repeats must be positive and capacities/factors finite and positive')
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    # Initialize numerical libraries on a different, tiny workload.
    common.search(common.build(common.Case('matmuls', 'nvdla', (1, 4, 8)), .125, common.EL))
    env = {**common.capacity_fractions_env(caps), 'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer'}
    env['AF_ENUMERATION_PREFIX_BYTES'] = str(a.prefix_bytes)
    env['AF_ENUMERATION_PARETO_BYTES'] = str(a.pareto_bytes)
    env['AF_TARGET_ENUMERATION'] = a.target_mode
    enumeration_stats = {}
    pareto_stats = {}
    target_stats = {}
    model_cache_stats = {}
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
        pareto_stats.clear()
        pruned = [getattr(j, 'enumeration_pareto_stats', {})
                  for jobs in pm.einsum2jobs.values() for j in jobs]
        for key in ('requests', 'computations', 'hits', 'requested_rows', 'computed_rows', 'evictions'):
            pareto_stats[key] = sum(s.get(key, 0) for s in pruned)
        pareto_stats['max_template_payload_bytes'] = max(
            (s.get('peak_payload_bytes', 0) for s in pruned), default=0)
        shared = [getattr(j, 'target_enumeration_stats', {})
                  for jobs in pm.einsum2jobs.values() for j in jobs]
        target_stats.clear()
        target_stats['supported_templates'] = sum(s.get('supported', 0) for s in shared)
        target_stats['fallback_templates'] = sum(bool(s) and not s.get('supported', 0) for s in shared)
        for key in ('state_expansions', 'expanded_rows', 'target_expansions', 'target_expanded_rows',
                    'value_evaluations', 'target_value_evaluations', 'capacity_partitions',
                    'capacity_masks', 'pareto_calls', 'target_pareto_calls', 'state_merges'):
            target_stats[key] = sum(s.get(key, 0) for s in shared)
        for key in ('peak_cohorts', 'peak_state_rows', 'peak_state_bytes'):
            target_stats['max_template_' + key] = max((s.get(key, 0) for s in shared), default=0)
        import importlib
        model_cache_stats.clear()
        for module, name in (
            ('accelforge.frontend._workload_isl._symbolic', '_parse_projection_expr'),
            ('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes', '_prepare_rank_projection'),
            ('accelforge.model._looptree.reuse.symbolic.symbolic', '_maximum_stat'),
        ):
            function = getattr(importlib.import_module(module), name, None)
            if function is not None:
                model_cache_stats[name] = function.cache_info()._asdict()
        return pm

    common.make_pmappings = measured_make
    scaled = [f for f in factors if f != 1]
    if scaled:
        env['AF_LATENCY_SCALES'] = 'GlobalBuffer:' + ','.join(map(repr, scaled))
    report = {'case': str(case), 'caps': caps, 'factors': factors, 'jobs': 1,
              'phase_timers': a.phases, 'cprofile': a.cprofile,
              'prefix_bytes': a.prefix_bytes,
              'pareto_bytes': a.pareto_bytes,
              'target_mode': a.target_mode,
              'python': platform.python_version(),
              'pythonhashseed': os.environ.get('PYTHONHASHSEED'),
              'commit': subprocess.check_output(['git', '-C', str(a.repo), 'rev-parse', 'HEAD'], text=True).strip(),
              'diff': subprocess.check_output(['git', '-C', str(a.repo), 'diff', '--', 'accelforge'], text=True),
              'runs': [], 'frontiers': {}}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    for repeat in range(a.repeats):
        phases = GenerationPhases(common) if a.phases else nullcontext()
        spec = common.build(case, max(caps), common.RU)
        if a.cprofile:
            import cProfile
            profiler = cProfile.Profile()
            profiler.enable()
        with phases:
            result, timing = common.search(spec, env, {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'})
        if a.cprofile:
            profiler.disable()
            profiler.dump_stats(str(a.output.with_suffix(f'.run{repeat}.prof')))
        numeric = result.data.select_dtypes(include='number')
        columns = sorted(numeric.columns)
        numeric = numeric[columns].drop_duplicates().sort_values(columns).reset_index(drop=True)
        frontier = {'columns': columns, 'values': numeric.values.tolist()}
        digest = hashlib.sha256(json.dumps(frontier, sort_keys=True).encode()).hexdigest()
        report['frontiers'].setdefault(digest, frontier)
        report['runs'].append({'repeat': repeat, **timing, 'search_s': timing['make_s'] + timing['join_s'],
                               'enumeration': dict(enumeration_stats),
                               'enumeration_pareto': dict(pareto_stats),
                               'target_enumeration': dict(target_stats),
                               'model_caches_cumulative': dict(model_cache_stats),
                               'phases': phases.snapshot() if a.phases else None,
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
