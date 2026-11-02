"""Check final-frontier breakpoints against exhaustive capacity queries."""
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
from accelforge.mapper.FFM._join_pmappings.capacity_breakpoints import build_capacity_breakpoints

root = Path(__file__).resolve().parents[2]
source = Path(os.environ.get('FRONTIER_FILE', root/'research/streaming_join/results/tag1_fullshape_selective.json'))
record = json.loads(source.read_text())
data = pd.DataFrame(record['values'], columns=record['columns'])
reservation = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'
scale = int(record['glb_mib'] * 1024 * 1024)
breakpoints = build_capacity_breakpoints(data, reservation, scale)
queries = {0, scale, 2*1024*1024, 4*1024*1024}
for r in data[reservation]:
    b = float(r)*scale
    if b.is_integer():
        queries.update([max(0, int(b)-1), int(b), int(b)+1])
for capacity in sorted(queries):
    filtered = data[data[reservation] <= capacity/scale]
    answer = breakpoints.query(capacity)
    if filtered.empty:
        assert answer is None
    else:
        assert answer is not None
        expected = float((filtered['Total<SEP>energy']*filtered['Total<SEP>latency']).min())
        assert answer[0] == expected, (capacity, answer, expected)
        assert data.iloc[answer[1]][reservation] <= capacity/scale
print('BREAKPOINT_AUDIT', json.dumps({'frontier_rows':len(data), 'breakpoint_count':len(breakpoints.edps),
    'queries_checked':len(queries), 'capacity_scale_bytes':scale, 'all_exact':True,
    'breakpoints':[{'capacity_bytes':float(r)*scale,'edp':float(e),'source_row':int(p)}
                   for r,e,p in zip(breakpoints.requirements,breakpoints.edps,breakpoints.positions)]}))
