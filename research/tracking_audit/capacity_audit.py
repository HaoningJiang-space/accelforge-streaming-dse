"""Time and strictly validate capacity-sweep search variants.

usage: capacity_audit.py M,G,C CAP1,CAP2,... VARIANTS [--repeats N] [--jobs N] [--no-warmup]
                         [ABLATION=VALUE ...]

  VARIANTS   comma-separated subset of indep,var,push (see common.py)
  CAPs       GlobalBuffer capacities in MiB; shared variants search once at the largest
  ABLATION   one of common.ABLATIONS, applied to every search
  --jobs     AccelForge worker processes (default 1 = serial, at most common.MAX_JOBS);
             compare times only between runs with the same --jobs

Output: a `CONFIG` line (commit, template limit, inherited switches, arguments), an
untimed `WARMUP` search, one `RUN` line per variant and repeat (variants rotate order
across repeats; search time excludes validation), then a `SUMMARY`.

Every pick of every repeat is validated with common.check_pick and kept. The summary
reports, per capacity: each variant's EDP, whether it was the same in every repeat, the
best valid EDP known at that capacity (any valid pick at a capacity <= it, since a
mapping that fits a smaller GlobalBuffer fits a larger one), and which variants were
invalid in any repeat, suboptimal, or short of a spatial min_usage.

Exit status, most severe first: 2 if any pick was invalid (including a min_usage check
that did not complete); 5 if any variant missed the best valid EDP known at some
capacity; 3 if a variant's EDP differed across repeats; otherwise 0. A min_usage
shortfall alone does not fail the run: FFM keeps the best attainable usage when no
choice reaches the minimum.
"""
import argparse
import json
import math
import statistics
import sys
import time

import common

def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('shape')
    p.add_argument('caps')
    p.add_argument('variants')
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--jobs', type=int, default=1)
    p.add_argument('--no-warmup', action='store_true',
                   help='skip the untimed warm-up search (JIT compilation, caches)')
    p.add_argument('ablations', nargs='*')
    a = p.parse_intermixed_args(argv)
    try:
        a.shape = [int(x) for x in a.shape.split(',')]
        a.caps = [float(x) for x in a.caps.split(',')]
    except ValueError:
        p.error('shape must contain integers and capacities must contain numbers')
    a.variants = a.variants.split(',')
    if len(a.shape) != 3 or any(x <= 0 for x in a.shape):
        p.error('shape must be exactly three positive integers: M,G,C')
    if any(not math.isfinite(x) or x <= 0 for x in a.caps) or len(set(a.caps)) != len(a.caps):
        p.error('capacities must be finite, positive and distinct')
    if set(a.variants) - set(common.VARIANTS) or len(set(a.variants)) != len(a.variants):
        p.error(f'variants must be distinct members of {common.VARIANTS}')
    if a.repeats < 1 or not 1 <= a.jobs <= common.MAX_JOBS:
        p.error(f'repeats must be >= 1 and jobs must be in [1, {common.MAX_JOBS}]')
    try:
        a.ablations = common.parse_ablations(a.ablations)
    except SystemExit as error:
        p.error(str(error))
    return a


def run(a):
    """Run the experiment; worker cleanup is owned by main(), including on failure."""
    shape, caps, variants, ablations = a.shape, a.caps, a.variants, a.ablations
    if not a.no_warmup:
        # Do not charge first-use compilation to whichever variant runs first.
        t0 = time.perf_counter()
        common.search(common.build(shape, max(caps), common.RU),
                      {'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer'},
                      {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'}, ablations=ablations)
        print('WARMUP', json.dumps({'seconds': time.perf_counter() - t0}), flush=True)

    times = {v: [] for v in variants}
    history = {v: {cap: [] for cap in caps} for v in variants}
    for r in range(a.repeats):
        order = variants[r % len(variants):] + variants[:r % len(variants)]
        for v in order:
            t0 = time.perf_counter()
            rows, stats = {}, []
            for cap, data, st in common.run_variant(v, shape, caps, ablations):
                rows[cap] = common.best_row(data)
                if st not in stats:
                    stats.append(st)
            times[v].append(time.perf_counter() - t0)
            records = []
            for cap in caps:
                row = rows.get(cap)
                rec = (common.check_pick(shape, cap, row) if row is not None
                       else {'cap_mib': cap, 'ok': False, 'error': 'no row fits'})
                history[v][cap].append(rec)
                records.append(rec)
            print('RUN', json.dumps({'repeat': r, 'variant': v, 'seconds': times[v][-1], 'stats': stats,
                                     'picks': records, 'main_peak_rss_gb': common.peak_rss_gb()['main']}),
                  flush=True)

    quality, any_invalid, all_consistent = common.summarize_quality(history, variants, caps)
    median = {v: statistics.median(t) for v, t in times.items()}
    summary = {'shape': shape, 'caps': caps, 'repeats': a.repeats, 'jobs': a.jobs, 'ablations': ablations,
               'all_picks_valid': not any_invalid, 'all_repeats_consistent': all_consistent,
               'all_min_usage_checks_completed': all(
                   'min_usage_shortfall' in rec and not rec.get('min_usage_shortfall_error')
                   for by_cap in history.values() for recs in by_cap.values() for rec in recs),
               'all_min_usage_satisfied': not any(
                   q['invalid'] or q['min_usage_shortfall'] for q in quality.values()),
               'median_seconds': median, 'seconds': times, 'quality': quality}
    if 'indep' in median:
        summary['speedup_vs_indep'] = {v: median['indep'] / t for v, t in median.items()}
    any_suboptimal = any(q['suboptimal'] for q in quality.values())
    summary['all_picks_best_known'] = not any_suboptimal
    return summary, 2 if any_invalid else 5 if any_suboptimal else 0 if all_consistent else 3


def main(argv=None):
    a = parse_args(argv)
    print('CONFIG', json.dumps(common.effective_config(args=vars(a))), flush=True)
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
