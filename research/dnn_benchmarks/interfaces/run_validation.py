"""Execute the frozen interface acceptance/rejection cases sequentially."""
import argparse,json
from pathlib import Path
from .evaluate import evaluate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--source-overlay',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);plan=json.loads(Path(__file__).with_name('validation_plan.json').read_text())
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');rows=[]
    for case in plan['cases']:
        path=out/(case['name']+'.request.json');path.write_text(json.dumps(case['request'],indent=2)+'\n')
        print('START',case['name'],flush=True);r=evaluate(path,out/case['name'],a.bundle.resolve(),a.source_overlay.resolve())
        passed=r['verdict']==case['expected_verdict'] and r['failure_stage']==case['expected_failure_stage']
        rows.append(dict(case=case['name'],expected_verdict=case['expected_verdict'],expected_failure_stage=case['expected_failure_stage'],verdict=r['verdict'],failure_stage=r['failure_stage'],check_passed=passed,metrics=r.get('metrics',{})))
        (out/'summary.json').write_text(json.dumps(dict(cases=len(rows),passed=sum(x['check_passed'] for x in rows),rows=rows),indent=2)+'\n');print('END',rows[-1],flush=True)
    if not all(x['check_passed'] for x in rows):raise SystemExit(1)

if __name__=='__main__':main()
