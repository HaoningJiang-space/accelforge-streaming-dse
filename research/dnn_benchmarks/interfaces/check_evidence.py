"""Recheck live receipts and reject corrupted evidence without modifying originals."""
import argparse,json,shutil
from pathlib import Path
from .evaluate import finalize


def shadow(original,dest):
    dest.mkdir(parents=True);(dest/'result/compiler').mkdir(parents=True)
    for name in ('request.json','launch_result.json','dma_audit.json'):
        if (original/name).is_file():shutil.copyfile(original/name,dest/name)
    for name in ('result.json','hardware.yml'):
        if (original/'result'/name).is_file():shutil.copyfile(original/'result'/name,dest/'result'/name)
    if (original/'result/logs').is_dir():shutil.copytree(original/'result/logs',dest/'result/logs')
    for manifest in (original/'result/compiler').glob('*/allocation_manifest.json'):
        directory=dest/'result/compiler'/manifest.parent.name;directory.mkdir()
        for path in manifest.parent.iterdir():
            target=directory/path.name
            if path.name=='allocation_manifest.json':shutil.copyfile(path,target)
            else:target.symlink_to(path.resolve(),target_is_directory=path.is_dir())


def check(original,out):
    out.mkdir(parents=True,exist_ok=False);plan=json.loads((original/'plan.json').read_text());rows=[]
    for case in plan['cases']:
        if case['expected_failure_stage']=='request':continue
        source=original/case['name'];dest=out/case['name'];shadow(source,dest)
        request=json.loads((source/'request.json').read_text());r=finalize(dest,request,0,0)
        rows.append(dict(case=case['name'],passed=r['verdict']==case['expected_verdict'] and r['failure_stage']==case['expected_failure_stage']))
    source=original/'full_serial_1k';request=json.loads((source/'request.json').read_text())
    for fault in ('missing_native','truncated_native','wrong_native_counts','wrong_capacity_total','wrong_hardware'):
        dest=out/fault;shadow(source,dest);native=next((dest/'result/logs').glob('*.stats.json'))
        if fault=='missing_native':native.unlink()
        elif fault=='truncated_native':native.write_text('{"schema":')
        elif fault=='wrong_native_counts':
            v=json.loads(native.read_text());v['read_transactions']+=1;native.write_text(json.dumps(v))
        elif fault=='wrong_capacity_total':
            m=next((dest/'result/compiler').glob('*/allocation_manifest.json'));v=json.loads(m.read_text());v['required_bytes_per_lane']=0;m.write_text(json.dumps(v))
        else:
            h=dest/'result/hardware.yml';h.write_text(h.read_text().replace('vpu_spad_size_bytes_per_lane: 1024','vpu_spad_size_bytes_per_lane: 2048'))
        r=finalize(dest,request,0,0);rows.append(dict(case=fault,passed=r['verdict']=='rejected' and not r['metrics'],failure_stage=r['failure_stage']))
    result=dict(checks=len(rows),passed=sum(r['passed'] for r in rows),rows=rows)
    (out/'check_summary.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--original',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=check(a.original.resolve(),a.out.resolve());print(json.dumps(r))
    if r['checks']!=r['passed']:raise SystemExit(1)
