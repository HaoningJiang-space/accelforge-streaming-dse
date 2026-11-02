"""Compare sorted numeric Pareto frontiers from independent bounded runs."""
import json
import math
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit('usage: python compare_results.py BASELINE.json STREAM.json')
a, b = [json.loads(Path(p).read_text()) for p in sys.argv[1:]]
for key in ('shape', 'resource_usage', 'max_templates_per_einsum', 'columns'):
    if a[key] != b[key]:
        raise SystemExit(f'different {key}: {a[key]} != {b[key]}')
if a.get('glb_mib', 0.5) != b.get('glb_mib', 0.5):
    raise SystemExit('different GlobalBuffer capacities')
if len(a['values']) != len(b['values']):
    raise SystemExit(f"different frontier sizes: {len(a['values'])} != {len(b['values'])}")
for row_index, (left, right) in enumerate(zip(a['values'], b['values'])):
    if len(left) != len(right):
        raise SystemExit(f'different width in row {row_index}')
    for col, x, y in zip(a['columns'], left, right):
        if not math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-20):
            raise SystemExit(f'mismatch row {row_index}, {col}: {x} != {y}')
print(json.dumps({'rows': len(a['values']), 'frontier_equal': True,
                  'baseline_best_edp': a['best_edp'], 'stream_best_edp': b['best_edp'],
                  'baseline_rss_kib': a['peak_rss_kib'], 'stream_rss_kib': b['peak_rss_kib'],
                  'baseline_join_s': a['join_s'], 'stream_join_s': b['join_s']}))
