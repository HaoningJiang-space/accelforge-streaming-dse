"""Run an isolated, bounded GEMM check in a verified user-owned OCI bundle."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--mode',choices=('heuristic','autotune','external'),required=True)
    p.add_argument('--seconds',type=int,default=600)
    p.add_argument('--shape',type=int,nargs=3,default=(64,128,32))
    p.add_argument('--tile',type=int,nargs=6,default=(16,32,8,8,32,8))
    p.add_argument('--diagnostic-allow-n-split',action='store_true')
    a=p.parse_args();bundle=a.bundle.resolve();out=a.out.resolve()
    if a.seconds<=0:p.error('positive timeout required')
    out.mkdir(parents=True,exist_ok=False)
    source=Path(__file__).resolve().parents[2]
    base=bundle/'config.umoci.json'
    cfg=json.loads((base if base.exists() else bundle/'config.json').read_text())
    cfg['root']['path']=str(bundle/'rootfs')
    cfg['process'].update(terminal=False,cwd='/study',args=[
        '/opt/conda/bin/python','-u','-m','research.dnn_benchmarks.pytorchsim_gemm_pilot',
        '--source','/workspace/PyTorchSim','--out','/experiment/result','--mode',a.mode,
        '--shape',*map(str,a.shape),'--tile',*map(str,a.tile)])
    if a.diagnostic_allow_n_split:cfg['process']['args'].append('--diagnostic-allow-n-split')
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','MAX_JOBS','NUMEXPR_NUM_THREADS'):
        cfg['process']['env']=[x for x in cfg['process']['env'] if not x.startswith(name+'=')]+[name+'=1']
    cfg['mounts'] += [dict(destination='/study',type='bind',source=str(source),options=['rbind','ro','nosuid','nodev']),
                      dict(destination='/experiment',type='bind',source=str(out),options=['rbind','rw','nosuid','nodev'])]
    run_bundle=out/'oci';run_bundle.mkdir()
    (run_bundle/'config.json').write_text(json.dumps(cfg,indent=2)+'\n')
    state=bundle.parent/'runc-state';identity=f'graph-gemm-{os.getpid()}'
    runc=['/usr/sbin/runc','--root',str(state),'--rootless','true']
    started=time.monotonic();status='running'
    with (out/'execution.log').open('x') as stream:
        child=subprocess.Popen(runc+['run','--bundle',str(run_bundle),identity],stdout=stream,stderr=subprocess.STDOUT)
        try:
            code=child.wait(timeout=a.seconds);status='exited'
        except subprocess.TimeoutExpired:
            subprocess.run(runc+['kill',identity,'KILL'],stdout=stream,stderr=stream)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            code=child.returncode;status='timeout'
        finally:subprocess.run(runc+['delete','--force',identity],stdout=stream,stderr=stream)
    (out/'launch_result.json').write_text(json.dumps(dict(status=status,exitcode=code,mode=a.mode,
        wall_seconds=time.monotonic()-started,timeout_seconds=a.seconds),indent=2)+'\n')
    if code or status!='exited':raise SystemExit(1)


if __name__=='__main__':main()
