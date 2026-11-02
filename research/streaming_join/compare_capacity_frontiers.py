"""Compare per-capacity optima from full and selective resource frontiers."""
import json
import math
import sys
from pathlib import Path

if len(sys.argv) != 4:
    raise SystemExit('usage: python compare_capacity_frontiers.py FULL.json SELECTIVE.json CAPACITIES_MIB')
a, b = [json.loads(Path(p).read_text()) for p in sys.argv[1:3]]
capacities = [float(x) for x in sys.argv[3].split(',')]
for key in ('shape', 'resource_usage', 'max_templates_per_einsum', 'glb_mib'):
    if a.get(key) != b.get(key):
        raise SystemExit(f'different {key}: {a.get(key)} != {b.get(key)}')

def best(data, cap):
    cols = data['columns']
    g = cols.index('reservation<SEP>GlobalBuffer<SEP>0<SEP>right')
    e = cols.index('Total<SEP>energy')
    t = cols.index('Total<SEP>latency')
    candidates = [r[e]*r[t] for r in data['values'] if r[g] <= cap/data['glb_mib']*(1+1e-12)]
    return min(candidates) if candidates else None

mismatches = 0
for cap in capacities:
    if cap > a['glb_mib']:
        raise SystemExit(f'capacity {cap} exceeds shared-search capacity')
    x, y = best(a, cap), best(b, cap)
    if x is None and y is None:
        status = 'no_candidate_in_either'
    elif x is None or y is None or not math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-20):
        status = 'mismatch'
        mismatches += 1
    else:
        status = 'equal'
    print(json.dumps({'capacity_mib':cap,'full_edp':x,'selective_edp':y,'status':status}))
if mismatches:
    raise SystemExit(f'{mismatches} capacity mismatches')
