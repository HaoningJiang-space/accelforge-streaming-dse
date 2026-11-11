"""Bounded end-to-end validation of the repaired plain-GEMM simulation path.

Runs the actual Instruction object-code probe, then eight fresh compiler /
functional / timing invocations and independent DMA ledgers. Requires the pinned
runtime and repaired overlay; never modifies the original source/image.
"""
import argparse,json,os,subprocess,time
from pathlib import Path

CASES=[
 ('heuristic','heuristic',(64,128,32),(16,32,8,8,32,8)),
 ('autotune','autotune',(64,128,32),(16,32,8,8,32,8)),
 ('native_tuple','external',(64,128,32),(64,128,32,64,128,32)),
 ('small_tile','external',(64,128,32),(16,32,8,16,32,8)),
 ('subtile_m','external',(64,128,32),(16,32,8,8,32,8)),
 ('aligned_n','external',(16,256,16),(16,256,16,16,128,16)),
 ('aligned_k','external',(16,32,256),(16,32,256,16,32,128)),
 ('native_repeat','external',(64,128,32),(64,128,32,64,128,32)),
]


def address_probe(bundle,overlay,out,seconds):
    out.mkdir();source=Path(__file__).resolve().parents[2]
    cfg=json.loads((bundle/'config.umoci.json').read_text());cfg['root']['path']=str(bundle/'rootfs')
    cfg['process'].update(terminal=False,cwd='/study',args=['/opt/conda/bin/python','-u','-m','research.dnn_benchmarks.build_address_test','--source','/workspace/PyTorchSim','--out','/experiment/test'])
    for dst,src,mode in [('/study',source,'ro'),('/experiment',out,'rw'),('/workspace/PyTorchSim',overlay,'rw')]:
        cfg['mounts'].append(dict(destination=dst,type='bind',source=str(src),options=['rbind',mode,'nosuid','nodev']))
    oci=out/'oci';oci.mkdir();(oci/'config.json').write_text(json.dumps(cfg))
    runc=['/usr/sbin/runc','--root',str(bundle.parent/'runc-state'),'--rootless','true'];identity=f'graph-address-{os.getpid()}'
    start=time.monotonic();code=None
    with (out/'execution.log').open('x') as stream:
        child=subprocess.Popen(runc+['run','--bundle',str(oci),identity],stdout=stream,stderr=subprocess.STDOUT)
        try:code=child.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            subprocess.run(runc+['kill',identity,'KILL'],stdout=stream,stderr=stream)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        finally:subprocess.run(runc+['delete','--force',identity],stdout=stream,stderr=stream)
    result=json.loads((out/'test/result.json').read_text()) if (out/'test/result.json').exists() else None
    return dict(exitcode=code,wall_seconds=time.monotonic()-start,result=result,passed=code==0 and result is not None and result['failures']==0)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--source-overlay',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=600);a=p.parse_args()
    if a.seconds<=0:p.error('positive timeout required')
    bundle=a.bundle.resolve();overlay=a.source_overlay.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    source=Path(__file__).resolve().parents[2]
    revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    manifest=dict(source_commit=revision,cases=CASES,timeout_seconds=a.seconds,serial=True,seed=0,backend_lock='repaired_backend_lock.json')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    summary=dict(address_probe=address_probe(bundle,overlay,out/'address_test',a.seconds),runs=[],checks={})
    if not summary['address_probe']['passed']:
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');raise SystemExit(1)
    for name,mode,shape,tile in CASES:
        print('START',name,flush=True)
        args=['python3','-u','-m','research.dnn_benchmarks.run_rootless_pilot','--bundle',str(bundle),'--source-overlay',str(overlay),'--out',str(out/name),'--mode',mode,'--shape',*map(str,shape),'--tile',*map(str,tile),'--seconds',str(a.seconds),'--backend-lock','repaired_backend_lock.json','--fixed-timing-addresses']
        code=subprocess.run(args,cwd=source).returncode
        record=dict(case=name,exitcode=code)
        if (out/name/'dma_audit.json').exists():record['audit']=json.loads((out/name/'dma_audit.json').read_text())
        summary['runs'].append(record);(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('END',name,code,flush=True)
    audits={r['case']:r.get('audit',{}) for r in summary['runs']}
    same=('heuristic','autotune','native_tuple','native_repeat')
    summary['checks']['all_numerical_and_dma_pass']=all(r['exitcode']==0 and r.get('audit',{}).get('timing_accepted') for r in summary['runs'])
    summary['checks']['identical_full_tile_cycles']=all(audits[n].get('total_cycles')==audits['native_tuple'].get('total_cycles') for n in same)
    summary['checks']['identical_full_tile_dma_stream']=all(audits[n].get('expected_address_stream_sha256')==audits['native_tuple'].get('expected_address_stream_sha256') for n in same)
    summary['passed']=summary['address_probe']['passed'] and all(summary['checks'].values())
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(passed=summary['passed'],checks=summary['checks'])))
    if not summary['passed']:raise SystemExit(1)

if __name__=='__main__':main()
