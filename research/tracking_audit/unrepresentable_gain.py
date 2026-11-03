"""Estimate what the conservative unrepresentable-template filter costs.

usage: unrepresentable_gain.py PARAMS CAP [--workload W] [--arch A] [--metrics el|ru]
                               [--jobs N]

By default make_pmappings skips templates that keep a copy of a fusable tensor above a
fused loop (Compatibility.has_copy_above_fused_loops): joined with templates lacking
the copy, they rebuild into a mapping different from the one scored. This runs

  conservative  the default search at CAP
  restored      the same search with AF_ABL_ALLOW_UNREPRESENTABLE=1

and re-evaluates every row of the restored search's final front as the mapping it
actually rebuilds into (common.strict_evaluate at CAP). It reports how many rows were
scored differently from their rebuilt mapping, how many rebuilt mappings fit, and the
best re-evaluated EDP against the conservative pick.

This is an estimate, not a bound: the restored search pruned with possibly wrong
scores, so a correctly represented fusion could also reach mappings that are not on
its front. --metrics ru keeps resource tradeoffs on the front (more rows to check).
"""
import argparse
import json
import math
import sys

import numpy as np

import common


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('params')
    p.add_argument('cap', type=float)
    p.add_argument('--workload', default=common.DEFAULT_CASE.workload, choices=common.WORKLOADS)
    p.add_argument('--arch', default=common.DEFAULT_CASE.arch, choices=common.ARCHES)
    p.add_argument('--metrics', default='el', choices=('el', 'ru'))
    p.add_argument('--jobs', type=int, default=1)
    a = p.parse_args(argv)
    a.case = common.Case.parse(a.workload, a.arch, a.params)
    if not math.isfinite(a.cap) or a.cap <= 0 or not 1 <= a.jobs <= common.MAX_JOBS:
        p.error('cap must be finite and positive; jobs in [1, MAX_JOBS]')
    return a


def rebuilt_costs(case, cap, data):
    """Per row: reported EDP and the re-evaluation of the mapping it rebuilds into."""
    out = []
    for i in range(len(data)):
        row = data.iloc[i]
        energy, latency = float(row['Total<SEP>energy']), float(row[common.LATENCY])
        rec = {'reported_edp': energy * latency}
        try:
            mapping = row['Total<SEP>mapping']()
            ev = common.strict_evaluate(case, cap, mapping)
            rec['edp'] = ev['edp']
            rec['min_usage_shortfall'] = common.spatial_usage_shortfalls(case, mapping)
            rec['matches'] = all(abs(ev[k] - v) <= 1e-6 * v for k, v in
                                 (('energy', energy), ('latency', latency)))
        except Exception as e:  # does not fit, or cannot be rebuilt/evaluated
            rec['error'] = f'{type(e).__name__}: {str(e)[:120]}'
        out.append(rec)
    return out


def main(argv=None):
    a = parse_args(argv)
    metrics = common.RU if a.metrics == 'ru' else common.EL
    print('CONFIG', json.dumps(common.effective_config(a.case, args=vars(a)), default=str), flush=True)
    common.set_jobs(a.jobs)
    try:
        cons, cons_stats = common.search(common.build(a.case, a.cap, common.EL))
        cons_pick = common.check_pick(a.case, a.cap, common.best_row(cons.data))
        rest, rest_stats = common.search(common.build(a.case, a.cap, metrics),
                                         ablations={'AF_ABL_ALLOW_UNREPRESENTABLE': '1'})
        rows = rebuilt_costs(a.case, a.cap, rest.data)
    finally:
        common.shutdown_workers()
    fitting = [r['edp'] for r in rows if 'edp' in r]
    best = min(fitting) if fitting else None
    best_row = next((r for r in rows if r.get('edp') == best), None)
    cons_edp = cons_pick['reevaluated']['edp'] if cons_pick.get('ok') else None
    summary = {
        'case': str(a.case), 'cap_mib': a.cap, 'metrics': a.metrics,
        'conservative': {'stats': cons_stats, 'ok': cons_pick['ok'], 'edp': cons_edp},
        'restored': {'stats': rest_stats, 'rows': len(rows),
                     'scored_as_rebuilt': sum(bool(r.get('matches')) for r in rows),
                     'scored_differently': sum(r.get('matches') is False for r in rows),
                     'rebuild_or_fit_failed': sum('error' in r for r in rows),
                     'best_rebuilt_edp': best, 'best_row': best_row},
        'restored_better_by': (None if best is None or cons_edp is None
                               else float(np.float64(cons_edp) / best - 1)),
        'row_details': rows[:10],
    }
    print('SUMMARY', json.dumps(summary), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
