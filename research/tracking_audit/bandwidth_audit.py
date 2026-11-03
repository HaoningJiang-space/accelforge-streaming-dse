"""Time and strictly validate one shared search across GlobalBuffer bandwidths.

usage: bandwidth_audit.py PARAMS FACTORS [--cap MIB] [--workload W] [--arch A]
                          [--repeats N] [--jobs N] [--no-warmup]

  PARAMS    comma-separated parameters of the workload (see capacity_audit.py)
  FACTORS   comma-separated GlobalBuffer latency scales, e.g. 0.25,0.5,1,2
            (0.5 = twice the bandwidth); applied as the component's latency_scale
  --cap     GlobalBuffer capacity in MiB, the same for every scenario (default 4)

Variants:
  indep   one ENERGY|LATENCY search per factor on the architecture with that scale
  shared  one ENERGY|LATENCY search with AF_LATENCY_SCALES=GlobalBuffer:<factors>,
          which adds one latency objective per factor; each factor's pick minimizes
          energy times its own latency column

Every pick is re-evaluated on the architecture with its factor (common.check_pick).
Quality compares the variants at the same factor only (a different bandwidth is not
a superset of feasible mappings). RUN lines record each search's stats, including
rows_front, the size of the final Pareto front: the shared front grows with the number
of factors because each adds an objective.

Exit status as capacity_audit.py: 2 invalid pick, 5 suboptimal, 3 inconsistent, 0 ok.
"""
import argparse
import json
import math
import statistics
import sys
import time

import common
from accelforge.mapper.FFM._pareto_df.df_convention import scaled_latency2col

VARIANTS = ('indep', 'shared')


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('params')
    p.add_argument('factors')
    p.add_argument('--cap', type=float, default=4.0)
    p.add_argument('--workload', default=common.DEFAULT_CASE.workload, choices=common.WORKLOADS)
    p.add_argument('--arch', default=common.DEFAULT_CASE.arch, choices=common.ARCHES)
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--jobs', type=int, default=1)
    p.add_argument('--no-warmup', action='store_true')
    a = p.parse_args(argv)
    try:
        a.case = common.Case.parse(a.workload, a.arch, a.params)
        a.factors = [float(x) for x in a.factors.split(',')]
    except ValueError as error:
        p.error(f'bad parameters or factors: {error}')
    if any(not math.isfinite(f) or f <= 0 for f in a.factors) or len(set(a.factors)) != len(a.factors):
        p.error('factors must be finite, positive and distinct')
    if not math.isfinite(a.cap) or a.cap <= 0:
        p.error('cap must be finite and positive')
    if a.repeats < 1 or not 1 <= a.jobs <= common.MAX_JOBS:
        p.error(f'repeats must be >= 1 and jobs must be in [1, {common.MAX_JOBS}]')
    return a


def latency_column(factor):
    """Latency objective of the shared search for `factor` (1 is the unscaled one)."""
    return common.LATENCY if factor == 1 else scaled_latency2col('GlobalBuffer', factor)


def run_variant(variant, case, cap, factors):
    """Yield (factor, data, latency_col, stats) per factor."""
    if variant == 'indep':
        for f in factors:
            res, st = common.search(common.build(case, cap, common.EL, gb_latency_scale=f))
            yield f, res.data, common.LATENCY, st
    elif variant == 'shared':
        scaled = [f for f in factors if f != 1]
        gen_env = {'AF_LATENCY_SCALES': 'GlobalBuffer:' + ','.join(map(repr, scaled))} if scaled else None
        res, st = common.search(common.build(case, cap, common.EL), gen_env)
        for f in factors:
            yield f, res.data, latency_column(f), st
    else:
        raise ValueError(f'unknown variant {variant}')


def run(a):
    case, cap, factors = a.case, a.cap, a.factors
    if not a.no_warmup:
        t0 = time.perf_counter()
        list(run_variant('shared', case, cap, factors))
        print('WARMUP', json.dumps({'seconds': time.perf_counter() - t0}), flush=True)

    times = {v: [] for v in VARIANTS}
    history = {v: {f: [] for f in factors} for v in VARIANTS}
    for r in range(a.repeats):
        order = VARIANTS[r % 2:] + VARIANTS[:r % 2]
        for v in order:
            t0 = time.perf_counter()
            picks, stats = {}, []
            for f, data, col, st in run_variant(v, case, cap, factors):
                picks[f] = (common.best_row(data, col), col)
                if st not in stats:
                    stats.append(st)
            times[v].append(time.perf_counter() - t0)
            records = []
            for f in factors:
                row, col = picks[f]
                rec = (common.check_pick(case, cap, row, latency_col=col, gb_latency_scale=f)
                       if row is not None else {'cap_mib': cap, 'ok': False, 'error': 'no row fits'})
                rec['factor'] = f
                history[v][f].append(rec)
                records.append(rec)
            print('RUN', json.dumps({'repeat': r, 'variant': v, 'seconds': times[v][-1], 'stats': stats,
                                     'picks': records}), flush=True)

    quality, any_invalid, all_consistent = common.summarize_quality(history, VARIANTS, factors, monotone=False)
    any_suboptimal = any(q['suboptimal'] for q in quality.values())
    median = {v: statistics.median(t) for v, t in times.items()}
    summary = {'case': str(case), 'cap_mib': cap, 'factors': factors, 'repeats': a.repeats, 'jobs': a.jobs,
               'all_picks_valid': not any_invalid, 'all_repeats_consistent': all_consistent,
               'all_picks_best_known': not any_suboptimal,
               'all_min_usage_checks_completed': all(
                   'min_usage_shortfall' in rec and not rec.get('min_usage_shortfall_error')
                   for by_factor in history.values() for recs in by_factor.values() for rec in recs),
               'median_seconds': median, 'seconds': times, 'quality': quality,
               'speedup_vs_indep': {v: median['indep'] / t for v, t in median.items()}}
    return summary, 2 if any_invalid else 5 if any_suboptimal else 0 if all_consistent else 3


def main(argv=None):
    a = parse_args(argv)
    print('CONFIG', json.dumps(common.effective_config(a.case, args=vars(a)), default=str), flush=True)
    common.set_jobs(a.jobs)
    try:
        summary, status = run(a)
    finally:
        common.shutdown_workers()
    summary['peak_rss_gb'] = common.peak_rss_gb()
    print('SUMMARY', json.dumps(summary), flush=True)
    return status


if __name__ == '__main__':
    sys.exit(main())
