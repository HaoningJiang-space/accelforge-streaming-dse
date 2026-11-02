"""Dump one pick in detail: the FFM row, its reconstructed mapping, and a re-evaluation.

usage: trace_pick.py M,G,C CAP VARIANT [--jobs N] [--eval-cap MIB] [ABLATION=MEM[,MEM] ...]

Runs VARIANT (indep searches only at CAP; var/push search at --eval-cap, default 4 MiB, and
filter to CAP), takes the best-EDP row that fits CAP, and prints:
  ROW       every non-callable column of that row
  MAPPING   the reconstructed mapping (str)
  EVAL      re-evaluation of the mapping at --eval-cap with RESOURCE_USAGE and ACTIONS,
            i.e. with enough capacity to succeed, listing all Total, reservation and
            energy columns
  STRICT    common.check_pick at CAP
Used to compare what FFM scored against what the reconstructed mapping actually does.
"""
import argparse
import copy
import json

import common

p = argparse.ArgumentParser()
p.add_argument('shape')
p.add_argument('cap', type=float)
p.add_argument('variant', choices=common.VARIANTS)
p.add_argument('--jobs', type=int, default=1)
p.add_argument('--eval-cap', type=float, default=4.0)
p.add_argument('ablations', nargs='*')
a = p.parse_args()
shape = [int(x) for x in a.shape.split(',')]
ablations = common.parse_ablations(a.ablations)
common.set_jobs(a.jobs)

caps = [a.cap] if a.variant == 'indep' else [a.cap, a.eval_cap]
data = next(d for c, d, _ in common.run_variant(a.variant, shape, caps, ablations) if c == a.cap)
row = common.best_row(data)
if row is None:
    raise SystemExit('no row fits')


def plain(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)


print('ROW', json.dumps({c: plain(row[c]) for c in row.index if not callable(row[c])}), flush=True)
mapping = row['Total<SEP>mapping']()
print('MAPPING', json.dumps(str(mapping)), flush=True)

metrics = common.RU | common.af.Metrics.ACTIONS
spec = common.build(shape, a.eval_cap, metrics)
spec.model.metrics = metrics
spec.mapping = copy.deepcopy(mapping)
common.clear_switches()
try:
    ev = common.evaluate_mapping(spec).data
    cols = [c for c in ev.columns if c != 'Total<SEP>mapping'
            and (c.startswith(('Total<SEP>', 'reservation<SEP>', 'energy<SEP>')))]
    print('EVAL', json.dumps({c: plain(ev[c].iloc[0]) for c in cols}), flush=True)
except Exception as e:
    print('EVAL_ERROR', json.dumps(f'{type(e).__name__}: {e}'[:500]), flush=True)
print('STRICT', json.dumps(common.check_pick(shape, a.cap, row)), flush=True)
common.shutdown_workers()
