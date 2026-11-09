"""Post-score diagnostic: independently replay the worst missing reference plans.

Does not change the frozen constructor family or count a repaired outcome.
"""
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from .curve_model import curve
from .nest_model import coupling
from .simulate_nest import simulate
from .run_tiled_fork import build

if __name__=='__main__':
    rows=[json.loads(x) for x in Path(sys.argv[1]).read_text().splitlines()]
    print(json.dumps(dict(kind='metadata',commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                         post_observation=True)),flush=True)
    for source in ('archived','fresh'):
        row=max((r for r in rows if r['kind']=='case' and r['source']==source),
                key=lambda r:r['scores']['tiles_scoped_retention']['worst_traffic_excess'])
        cap=row['scores']['tiles_scoped_retention']['worst_capacity']
        g=coupling(*row['shape'],row['cross']); t=perf_counter()
        points=curve(g,witness=True,max_capacity=cap)
        c,q,w=points[-1]
        actual=simulate(g,w)
        assert actual['peak']==c and actual['traffic']==q
        plans,_,_,_=build(row['shape'],row['cross'],False,'tiles_scoped_retention')
        p=min((p for p in plans if p.metrics()['peak']<=cap),key=lambda p:p.metrics()['traffic'])
        print(json.dumps(dict(kind='miss',source=source,shape=row['shape'],cross=row['cross'],capacity=cap,
                             seconds=perf_counter()-t,reference_peak=c,reference_traffic=q,
                             reference_witness=w,execution=actual,constructor=p.record())),flush=True)
