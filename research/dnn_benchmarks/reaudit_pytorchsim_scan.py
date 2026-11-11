"""Re-audit archived runs into a new directory; retain every original outcome."""
import argparse,hashlib,json,time
from pathlib import Path
from .audit_repaired_dma import audit


def reaudit(root,out):
    out.mkdir(parents=True,exist_ok=False);rows=[]
    for result in sorted(root.glob('*/result/result.json')):
        run=result.parent.parent;name=run.name;record=json.loads(result.read_text())
        old=json.loads((run/'dma_audit.json').read_text()) if (run/'dma_audit.json').exists() else {}
        row=dict(case=name,shape=record['shape'],mode=record['mode'],old_timing_accepted=old.get('timing_accepted'),old_observed_transactions=old.get('observed_transactions'))
        started=time.monotonic()
        try:
            corrected=audit(run)
            (out/(name+'.json')).write_text(json.dumps(corrected,indent=2)+'\n')
            row.update(timing_accepted=corrected['timing_accepted'],expected_transactions=corrected['expected_transactions'],observed_transactions=corrected['observed_transactions'],total_cycles=corrected['total_cycles'],interval_records=corrected['statistics']['ignored_interval_records'])
        except Exception as e:row.update(timing_accepted=False,error=f'{type(e).__name__}: {e}')
        row['audit_seconds']=time.monotonic()-started
        row['log_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (result.parent/'logs').glob('*.log')}
        rows.append(row);print(json.dumps(row),flush=True)
    summary=dict(runs=len(rows),passed=sum(r['timing_accepted'] for r in rows),corrected_false_rejections=sum(r['old_timing_accepted'] is False and r['timing_accepted'] for r in rows),rows=rows)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runs',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=reaudit(a.runs,a.out)
    if not r['runs'] or r['passed']!=r['runs']:raise SystemExit(1)
