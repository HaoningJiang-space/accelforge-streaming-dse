"""Single entry point for immutable requests and unified evaluation results."""
import argparse,json,subprocess,sys,time
from pathlib import Path
from .contract import normalize,digest
from .receipts import receipt,capacity_verdict


def read(path):return json.loads(path.read_text()) if path.is_file() else None


def finalize(out,request,wall_seconds,driver_exitcode):
    record=read(out/'result/result.json') or {};launch=read(out/'launch_result.json') or {};audit=read(out/'dma_audit.json') or {}
    result=dict(schema='gemm-evaluation.v1',request_sha256=digest(request),operator_id=request['operator_id'],mapping_id=request['mapping_id'],
        requested_hardware=request['hardware'],process_exitcode=launch.get('process_exitcode'),driver_exitcode=driver_exitcode,
        verdict='rejected',failure_stage=None,checks={},metrics={},costs=dict(evaluation_wall_seconds=wall_seconds,audit_seconds=launch.get('audit_seconds'),phases=record.get('phase_seconds',{})),
        provenance=dict(backend_lock_sha256=record.get('backend_lock_sha256'),file_sha256=record.get('file_sha256',{})))
    checks=result['checks'];checks['execution']=result['process_exitcode']==0;checks['numerical']=record.get('numerical_equal') is True
    checks['dma']=audit.get('timing_accepted') is True
    allocs=[read(p) for p in (out/'result/compiler').glob('*/allocation_manifest.json')]
    rec=None
    try:
        rec=receipt(out/'result',request);result['mapping_receipt']=rec;checks['mapping']=True
    except Exception as e:checks['mapping']=False;result['mapping_error']=str(e)
    alloc=rec['allocation'] if rec else (allocs[0] if len(allocs)==1 else None)
    cap=capacity_verdict(alloc,request['hardware']) if alloc else dict(passed=False,status='missing_allocation_receipt')
    checks['capacity']=cap;result['allocation_receipts']=allocs
    native_files=list((out/'result/logs').glob('*.stats.json'))
    native=read(native_files[0]) if len(native_files)==1 else None;result['native_statistics']=native
    checks['native_statistics']=bool(native and native.get('schema')=='togsim-final.v1' and native.get('completed') is True and native.get('scope')=='cumulative' and native.get('launched_kernels')==1 and native.get('serial_tiles')==request['hardware']['serial_tiles'] and native.get('total_cycles')==audit.get('total_cycles') and native.get('request_bytes')==audit.get('request_bytes') and native.get('dram_channels')==request['hardware']['dram_channels'] and {'read':native.get('read_transactions'),'write':native.get('write_transactions')}==audit.get('observed_transactions') and {'read':native.get('dma_load_instructions'),'write':native.get('dma_store_instructions')}==audit.get('observed_dma'))
    checks['hardware']=record.get('resolved_hardware')==request['hardware'] and record.get('request_sha256')==digest(request)
    if cap['status']=='capacity_exceeded':result['failure_stage']='capacity';result['reason']='capacity_exceeded'
    elif launch.get('status')=='timeout':result['failure_stage']='timeout'
    else:
        for stage in ('hardware','execution','numerical','mapping','native_statistics','dma','capacity'):
            passed=checks[stage].get('passed') if isinstance(checks[stage],dict) else checks[stage]
            if not passed:result['failure_stage']=stage;break
    if result['failure_stage'] is None:
        result['verdict']='accepted';result['metrics']=dict(cycles=native['total_cycles'],dram_read_bytes=native['read_transactions']*native['request_bytes'],dram_write_bytes=native['write_transactions']*native['request_bytes'],useful_bytes=audit['useful_bytes'],sram_required_bytes_per_lane=cap['required_bytes_per_lane'])
    else:result['diagnostic_cycles']=audit.get('total_cycles')
    result['scope']='Pinned plain-GEMM backend; capacity certificate requires serial tiles; no graph/energy/global latency-optimality claim'
    (out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');return result


def evaluate(request_path,out,bundle,source_overlay,seconds=600):
    if out.exists():raise FileExistsError('evaluation output must be fresh')
    start=time.monotonic()
    try:request=normalize(json.loads(request_path.read_text()))
    except (ValueError,KeyError,TypeError) as e:
        out.mkdir(parents=True);r=dict(schema='gemm-evaluation.v1',verdict='rejected',failure_stage='request',reason=str(e),process_exitcode=None,costs=dict(evaluation_wall_seconds=time.monotonic()-start))
        (out/'evaluation.json').write_text(json.dumps(r,indent=2)+'\n');return r
    mapping=request['mapping'];args=[sys.executable,'-u','-m','research.dnn_benchmarks.run_rootless_pilot','--bundle',str(bundle),'--source-overlay',str(source_overlay),'--backend-lock','interfaces_backend_lock.json','--fixed-timing-addresses','--interface-request',str(request_path.resolve()),'--out',str(out),'--mode',mapping['mode'],'--shape',*map(str,request['workload']['shape']),'--seconds',str(seconds)]
    if mapping['mode']=='external':args+=['--tile',*map(str,mapping['tile']+mapping['subtile'])]
    run=subprocess.run(args,cwd=Path(__file__).resolve().parents[3]);return finalize(out,request,time.monotonic()-start,run.returncode)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--source-overlay',type=Path,required=True);p.add_argument('--seconds',type=int,default=600)
    a=p.parse_args();r=evaluate(a.request,a.out.resolve(),a.bundle.resolve(),a.source_overlay.resolve(),a.seconds);print(json.dumps(dict(verdict=r['verdict'],failure_stage=r['failure_stage'])))
    if r['verdict']!='accepted':raise SystemExit(1)

if __name__=='__main__':main()
