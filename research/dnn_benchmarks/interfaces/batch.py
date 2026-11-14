"""Budget-accounted serial candidate evaluation; preserve distinct full mappings.

The wall budget is an admission budget: no new candidate starts after it expires.
An in-flight compilation/audit may finish beyond the deadline, and is charged.
"""
import argparse,json,math,time
from pathlib import Path
from .contract import normalize,digest
from .evaluate import evaluate


def run_batch(requests,out,bundle,source_overlay,wall_budget_seconds=None,evaluator=evaluate):
    if not requests:raise ValueError('empty candidate set')
    normalized=[normalize(r) for r in requests]
    common=lambda r:(r['operator_id'],digest(r['workload']),digest(r['hardware']))
    if len({common(r) for r in normalized})!=1:raise ValueError('candidate comparison requires the same operator, workload and hardware')
    if len({r['mapping_id'] for r in normalized})!=len(normalized):raise ValueError('unique candidate mapping IDs required')
    if wall_budget_seconds is not None and (not math.isfinite(wall_budget_seconds) or wall_budget_seconds<=0):raise ValueError('positive finite wall budget required')
    out.mkdir(parents=True,exist_ok=False);(out/'requests.json').write_text(json.dumps(normalized,indent=2)+'\n')
    start=time.monotonic();rows=[];best=None
    summary=dict(schema='gemm-candidate-batch.v1',submitted=len(normalized),attempted=0,not_started=len(normalized),wall_budget_seconds=wall_budget_seconds,elapsed_seconds=0,best_observed=None,rows=rows)
    for i,r in enumerate(normalized):
        elapsed=time.monotonic()-start
        if wall_budget_seconds is not None and elapsed>=wall_budget_seconds:break
        path=out/f'request_{i:04d}.json';path.write_text(json.dumps(r,indent=2)+'\n')
        timeout=min(600,max(1,math.ceil(wall_budget_seconds-elapsed))) if wall_budget_seconds else 600
        result=evaluator(path,out/f'candidate_{i:04d}',bundle,source_overlay,seconds=timeout)
        if result['verdict']=='accepted' and (best is None or result['metrics']['cycles']<best['cycles']):best=dict(mapping_id=r['mapping_id'],cycles=result['metrics']['cycles'])
        rows.append(dict(mapping_id=r['mapping_id'],request_sha256=digest(r),verdict=result['verdict'],failure_stage=result['failure_stage'],cumulative_wall_seconds=time.monotonic()-start,costs=result.get('costs'),best_observed=best.copy() if best else None))
        summary=dict(schema='gemm-candidate-batch.v1',submitted=len(normalized),attempted=len(rows),not_started=len(normalized)-len(rows),wall_budget_seconds=wall_budget_seconds,budget_scope='admission deadline; in-flight work charged through completion',elapsed_seconds=time.monotonic()-start,best_observed=best,rows=rows,optimality='best among accepted evaluated candidates only; no capacity/traffic-based pruning')
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    summary['elapsed_seconds']=time.monotonic()-start
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--requests',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--source-overlay',type=Path,required=True);p.add_argument('--wall-budget-seconds',type=float)
    a=p.parse_args();r=run_batch(json.loads(a.requests.read_text()),a.out.resolve(),a.bundle.resolve(),a.source_overlay.resolve(),a.wall_budget_seconds);print(json.dumps(dict(attempted=r['attempted'],best_observed=r['best_observed'])))

if __name__=='__main__':main()
