"""Independent fixed-capacity native searches around calibration breakpoints."""
import json
import math
from research.structure_prediction.experiment import ROOT, build, METRICS, E, R, save
from research.tracking_audit import common


def main():
    source=json.loads((ROOT/'results/cal_mm2_4_4.json').read_text())
    curve=source['graph']['points']
    capacities=sorted({max(curve[0]['capacity_bytes'],p['capacity_bytes']-1) for p in curve}
                      | {p['capacity_bytes'] for p in curve})
    common.set_jobs(1)
    rows=[]
    for capacity in capacities:
        spec,_,_=build('cal_mm2_4_4')
        spec.arch.find('GlobalBuffer').size=capacity*8
        spec.model.metrics=spec.mapper.ffm.metrics=common.af.Metrics.ENERGY
        result,stats=common.search(spec)
        best=result.data.sort_values(E).iloc[0]
        expected=min(p['traffic_bytes'] for p in curve if p['capacity_bytes']<=capacity)
        actual=float(best[E])/8
        if not math.isclose(actual,expected,rel_tol=1e-9):
            raise AssertionError((capacity,actual,expected))
        spec.mapping=best['Total<SEP>mapping']()
        spec.model.metrics=spec.mapper.ffm.metrics=METRICS | common.af.Metrics.ACTIONS
        ev=common.evaluate_mapping(spec).data.iloc[0]
        assert ev[R]<=capacity*8 and math.isclose(float(ev[E])/8,expected,rel_tol=1e-9)
        rows.append(dict(capacity_bytes=capacity,reference_traffic_bytes=expected,
                         fresh_search_traffic_bytes=actual,replayed_bytes=float(ev[R])/8,stats=stats))
        save(ROOT/'results/fixed_capacity_check.json',dict(case='cal_mm2_4_4',checks=rows))
        print(capacity,actual,flush=True)


if __name__=='__main__':
    main()
