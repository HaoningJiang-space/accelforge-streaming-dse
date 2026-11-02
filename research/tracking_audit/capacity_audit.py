"""Time and strictly validate capacity-sweep search variants.

usage: capacity_audit.py M,G,C CAP1,CAP2,... VARIANTS [--repeats N] [--jobs N] [--no-warmup]
                         [ABLATION=MEM[,MEM] ...]

  VARIANTS   comma-separated subset of indep,var,push (see common.py)
  CAPs       GlobalBuffer capacities in MiB; shared variants search once at the largest
  ABLATION   AF_ABL_SKIP_BIG_ENOUGH or AF_ABL_SKIP_PMAPPING_ONLY, applied to every search
  --jobs     AccelForge worker processes (default 1 = serial, at most common.MAX_JOBS);
             compare times only between runs with the same --jobs

An untimed warm-up search runs first. Each repeat runs every variant in rotated order.
Search time excludes validation. For
every capacity, the best-EDP pick is re-evaluated at that exact capacity (common.check_pick).

Output: one `RUN` JSON line per variant and repeat, then one `SUMMARY` line with median
times, speedups over indep, per-capacity best EDP of each variant, the best valid EDP
known at that capacity (any valid pick at a capacity <= it), and which variants were
invalid or suboptimal against it.
Exit status: 0 if every pick is valid, 2 if any pick is invalid.
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
picks = {v: {} for v in variants}  # variant -> cap -> check record (last repeat)
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
        for cap, row in rows.items():
            picks[v][cap] = (common.check_pick(shape, cap, row) if row is not None
                             else {'cap_mib': cap, 'ok': False, 'error': 'no row fits'})
        print('RUN', json.dumps({'repeat': r, 'variant': v, 'seconds': times[v][-1], 'stats': stats,
                                 'picks': list(picks[v].values()),
                                 'main_peak_rss_gb': common.peak_rss_gb()['main']}),
              flush=True)

common.shutdown_workers()
median = {v: statistics.median(t) for v, t in times.items()}
quality = {}
for cap in caps:
    edps = {v: picks[v][cap].get('edp') for v in variants}
    # A mapping valid at a smaller capacity is also valid here (same architecture otherwise),
    # so the best known valid EDP takes every variant's valid picks at caps <= cap.
    valid = [picks[v][c]['edp'] for v in variants for c in caps if c <= cap and picks[v][c]['ok']]
    best = min(valid) if valid else None
    quality[str(cap)] = {
        'edp': edps,
        'best_valid_edp': best,
        'invalid': [v for v in variants if not picks[v][cap]['ok']],
        'suboptimal': [v for v in variants if picks[v][cap]['ok'] and best is not None
                       and picks[v][cap]['edp'] > best * (1 + 1e-6)],
    }
summary = {'shape': shape, 'caps': caps, 'repeats': a.repeats, 'jobs': a.jobs, 'ablations': ablations,
           'median_seconds': median, 'quality': quality, 'peak_rss_gb': common.peak_rss_gb()}
if 'indep' in median:
    summary['speedup_vs_indep'] = {v: median['indep'] / t for v, t in median.items()}
print('SUMMARY', json.dumps(summary), flush=True)
sys.exit(2 if any(q['invalid'] for q in quality.values()) else 0)
