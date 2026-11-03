"""Time and strictly validate one shared search over a (capacity, bandwidth) grid.

usage: grid_audit.py PARAMS CAPS FACTORS [--workload W] [--arch A] [--repeats N]
                     [--jobs N] [--no-warmup]

  PARAMS    comma-separated parameters of the workload (see capacity_audit.py)
  CAPS      comma-separated GlobalBuffer capacities in MiB
  FACTORS   comma-separated GlobalBuffer latency scales (0.5 = twice the bandwidth)

Variants:
  indep   one ENERGY|LATENCY search per grid point (len(CAPS) * len(FACTORS) searches)
  shared  one search at the largest capacity with RESOURCE_USAGE, GlobalBuffer kept
          variable in generation and join (the capacity_audit `push` variant), and
          AF_LATENCY_SCALES for the factors; each grid point's pick is the lowest
          energy times that factor's latency among rows that fit its capacity

Every pick is re-evaluated at its capacity and scale (common.check_pick). The best
known EDP at a grid point includes valid picks at the same scale and any capacity not
larger (they fit too); a different scale is not comparable.

Exit status as capacity_audit.py: 2 invalid pick, 5 suboptimal, 3 inconsistent, 0 ok.
"""
import argparse
from collections import deque
import itertools
import json
import math
import statistics
import sys
import time

import common
from bandwidth_audit import latency_column

VARIANTS = ('indep', 'shared')


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('params')
    p.add_argument('caps')
    p.add_argument('factors')
    p.add_argument('--workload', default=common.DEFAULT_CASE.workload, choices=common.WORKLOADS)
    p.add_argument('--arch', default=common.DEFAULT_CASE.arch, choices=common.ARCHES)
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--jobs', type=int, default=1)
    p.add_argument('--no-warmup', action='store_true')
    a = p.parse_args(argv)
    try:
        a.case = common.Case.parse(a.workload, a.arch, a.params)
        a.caps = [float(x) for x in a.caps.split(',')]
        a.factors = [float(x) for x in a.factors.split(',')]
    except ValueError as error:
        p.error(f'bad parameters, capacities or factors: {error}')
    for name, xs in (('capacities', a.caps), ('factors', a.factors)):
        if any(not math.isfinite(x) or x <= 0 for x in xs) or len(set(xs)) != len(xs):
            p.error(f'{name} must be finite, positive and distinct')
    if a.repeats < 1 or not 1 <= a.jobs <= common.MAX_JOBS:
        p.error(f'repeats must be >= 1 and jobs must be in [1, {common.MAX_JOBS}]')
    return a


def run_variant(variant, case, caps, factors):
    """Yield ((cap, factor), data, latency_col, stats) per grid point."""
    if variant == 'indep':
        for cap, f in itertools.product(caps, factors):
            res, st = common.search(common.build(case, cap, common.EL, gb_latency_scale=f))
            yield (cap, f), res.data, common.LATENCY, st
    elif variant == 'shared':
        maxcap = max(caps)
        gen_env = {'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer', **common.capacity_fractions_env(caps)}
        scaled = [f for f in factors if f != 1]
        if scaled:
            gen_env['AF_LATENCY_SCALES'] = 'GlobalBuffer:' + ','.join(map(repr, scaled))
        res, st = common.search(common.build(case, maxcap, common.RU), gen_env,
                                {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'})
        for cap in caps:
            fits = common.rows_for_capacity(res.data, cap, maxcap)
            for f in factors:
                yield (cap, f), fits, latency_column(f), st
    else:
        raise ValueError(f'unknown variant {variant}')


def run(a):
    case, caps, factors = a.case, a.caps, a.factors
    points = list(itertools.product(caps, factors))
    if not a.no_warmup:
        t0 = time.perf_counter()
        # Consume and release query slices instead of keeping the whole grid's
        # DataFrames alive at once during warmup.
        deque(run_variant('shared', case, caps, factors), maxlen=0)
        print('WARMUP', json.dumps({'seconds': time.perf_counter() - t0}), flush=True)

    times = {v: [] for v in VARIANTS}
    history = {v: {pt: [] for pt in points} for v in VARIANTS}
    for r in range(a.repeats):
        order = VARIANTS[r % 2:] + VARIANTS[:r % 2]
        for v in order:
            t0 = time.perf_counter()
            picks, stats = {}, []
            for pt, data, col, st in run_variant(v, case, caps, factors):
                picks[pt] = (common.best_row(data, col), col)
                if st not in stats:
                    stats.append(st)
            times[v].append(time.perf_counter() - t0)
            records = []
            for cap, f in points:
                row, col = picks[(cap, f)]
                rec = (common.check_pick(case, cap, row, latency_col=col, gb_latency_scale=f)
                       if row is not None else {'cap_mib': cap, 'ok': False, 'error': 'no row fits'})
                rec['factor'] = f
                history[v][(cap, f)].append(rec)
                records.append(rec)
            print('RUN', json.dumps({'repeat': r, 'variant': v, 'seconds': times[v][-1], 'stats': stats,
                                     'picks': records}), flush=True)

    quality, any_invalid, all_consistent = common.summarize_quality(
        history, VARIANTS, points, fits=lambda c, key: c[1] == key[1] and c[0] <= key[0])
    any_suboptimal = any(q['suboptimal'] for q in quality.values())
    median = {v: statistics.median(t) for v, t in times.items()}
    summary = {'case': str(case), 'caps': caps, 'factors': factors, 'repeats': a.repeats, 'jobs': a.jobs,
               'all_picks_valid': not any_invalid, 'all_repeats_consistent': all_consistent,
               'all_picks_best_known': not any_suboptimal,
               'all_min_usage_checks_completed': all(
                   'min_usage_shortfall' in rec and not rec.get('min_usage_shortfall_error')
                   for by_point in history.values() for recs in by_point.values() for rec in recs),
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
