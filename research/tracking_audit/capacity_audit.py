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

Exit status: 0 if every pick of every repeat is valid and each variant's EDP is the same
across repeats; 2 if any pick was invalid; 3 if only the repeat consistency failed.
"""
import argparse
import json
import statistics
import sys
import time

import common

p = argparse.ArgumentParser()
p.add_argument('shape')
p.add_argument('caps')
p.add_argument('variants')
p.add_argument('--repeats', type=int, default=1)
p.add_argument('--jobs', type=int, default=1)
p.add_argument('--no-warmup', action='store_true',
               help='skip the untimed warm-up search (JIT compilation, caches)')
p.add_argument('ablations', nargs='*')
a = p.parse_args()
shape = [int(x) for x in a.shape.split(',')]
caps = [float(x) for x in a.caps.split(',')]
variants = a.variants.split(',')
if set(variants) - set(common.VARIANTS) or a.repeats < 1:
    raise SystemExit(f'variants must be from {common.VARIANTS}, repeats >= 1')
ablations = common.parse_ablations(a.ablations)
print('CONFIG', json.dumps(common.effective_config(args=vars(a))), flush=True)
common.set_jobs(a.jobs)

if not a.no_warmup:
    # The first search in a process pays numba compilation and cache warm-up, which
    # would otherwise be charged to whichever variant runs first.
    t0 = time.perf_counter()
    common.search(common.build(shape, max(caps), common.RU),
                  {'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer'},
                  {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'}, ablations=ablations)
    print('WARMUP', json.dumps({'seconds': time.perf_counter() - t0}), flush=True)

times = {v: [] for v in variants}
history = {v: {cap: [] for cap in caps} for v in variants}  # every repeat's check record
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
        for cap, row in rows.items():
            rec = (common.check_pick(shape, cap, row) if row is not None
                   else {'cap_mib': cap, 'ok': False, 'error': 'no row fits'})
            history[v][cap].append(rec)
            records.append(rec)
        print('RUN', json.dumps({'repeat': r, 'variant': v, 'seconds': times[v][-1], 'stats': stats,
                                 'picks': records, 'main_peak_rss_gb': common.peak_rss_gb()['main']}),
              flush=True)

common.shutdown_workers()


quality, any_invalid, all_consistent = common.summarize_quality(history, variants, caps)
median = {v: statistics.median(t) for v, t in times.items()}
summary = {'shape': shape, 'caps': caps, 'repeats': a.repeats, 'jobs': a.jobs, 'ablations': ablations,
           'all_picks_valid': not any_invalid, 'all_repeats_consistent': all_consistent,
           'median_seconds': median, 'seconds': times, 'quality': quality,
           'peak_rss_gb': common.peak_rss_gb()}
if 'indep' in median:
    summary['speedup_vs_indep'] = {v: median['indep'] / t for v, t in median.items()}
print('SUMMARY', json.dumps(summary), flush=True)
sys.exit(2 if any_invalid else 0 if all_consistent else 3)
