"""Selected compiled mapping and allocation receipts, bound to artifact hashes."""
import hashlib,json,re
from pathlib import Path
from ..mapping_contract import FIELDS


def receipt(result_dir,request):
    traces=list((result_dir/'logs').glob('*.trace'))
    if len(traces)!=1:raise ValueError('requires one selected invocation')
    entries=traces[0].read_text().strip().splitlines()
    if len(entries)!=1 or not entries[0].startswith('LAUNCH_KERNEL,'):raise ValueError('unexpected execution graph')
    graph=entries[0].split(',')[4]
    kernel=result_dir/graph.removeprefix('/experiment/result/');directory=kernel.parent
    sources=[p for p in directory.glob('*.mlir') if '// TILE_M =' in p.read_text()]
    if len(sources)!=1:raise ValueError('ambiguous selected GEMM source')
    code=sources[0].read_text()
    fields={key:int(value) for key,value in re.findall(r'//\s*(TILE_[MNK]|SUB_TILE_[MNK])\s*=\s*(\d+)',code)}
    if set(fields)!=set(FIELDS):raise ValueError('incomplete compiled six-field receipt')
    loops=re.findall(r'affine.for %index([012]) = 0 to (\d+) step (\d+)',code)
    if loops!=[(str(i),str(n),str(fields[FIELDS[i]])) for i,n in enumerate(request['workload']['shape'])]:raise ValueError('compiled loop order/extent differs')
    selected=[fields[f] for f in FIELDS]
    if request['mapping']['mode']=='external' and selected!=request['mapping']['tile']+request['mapping']['subtile']:raise ValueError('compiled mapping changed')
    allocation=json.loads((directory/'allocation_manifest.json').read_text())
    return dict(schema='gemm-mapping-receipt.v1',operator_id=request['operator_id'],mapping_id=request['mapping_id'],selected_tile=selected,
        loop_order=['M','N','K'],compiler_source_sha256=hashlib.sha256(sources[0].read_bytes()).hexdigest(),tog_sha256=hashlib.sha256(kernel.read_bytes()).hexdigest(),allocation=allocation)


def capacity_verdict(allocation,hardware):
    known=allocation.get('schema')=='pytorchsim-allocation.v1' and allocation.get('plain_gemm_scope') is True
    matches=allocation.get('capacity_bytes_per_lane')==hardware['sram_bytes_per_lane'] and allocation.get('lanes')==hardware['lanes']
    required=allocation.get('required_bytes_per_lane')
    fits=type(required) is int and required<=hardware['sram_bytes_per_lane']
    if not matches:return dict(passed=False,status='configuration_mismatch')
    if not fits:return dict(passed=False,status='capacity_exceeded',required_bytes_per_lane=required)
    if not known or not hardware['serial_tiles']:return dict(passed=False,status='capacity_not_certified',required_bytes_per_lane=required)
    return dict(passed=True,status='pass',required_bytes_per_lane=required,capacity_bytes_per_lane=hardware['sram_bytes_per_lane'],basis='ELF extent plus kernel stack; serial tiles; pinned plain-GEMM backend')
