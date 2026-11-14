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
    binary=directory/'validation_binary'
    if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest()!=allocation['binary_sha256']:raise ValueError('allocation receipt binary mismatch')
    assemblies=list(directory.glob('c*.s'))
    if len(assemblies)!=1 or hashlib.sha256(assemblies[0].read_bytes()).hexdigest()!=allocation['assembly_sha256']:raise ValueError('allocation receipt assembly mismatch')
    return dict(schema='gemm-mapping-receipt.v1',operator_id=request['operator_id'],mapping_id=request['mapping_id'],selected_tile=selected,
        loop_order=['M','N','K'],compiler_source_sha256=hashlib.sha256(sources[0].read_bytes()).hexdigest(),tog_sha256=hashlib.sha256(kernel.read_bytes()).hexdigest(),allocation=allocation)


def capacity_verdict(allocation,hardware):
    fields=('static_extent_bytes_per_lane','kernel_stack_bytes_per_lane','required_bytes_per_lane','static_object_bytes_per_lane','alignment_padding_bytes_per_lane')
    if any(type(allocation.get(k)) is not int or allocation[k]<0 for k in fields):return dict(passed=False,status='invalid_allocation_receipt')
    buffers=allocation.get('buffers',[])
    if not buffers or any(type(b.get('bytes_per_lane')) is not int or b['bytes_per_lane']<=0 or type(b.get('offset_bytes')) is not int or b['offset_bytes']<0 or b.get('copies')!=1 or b.get('lifetime')!='entire_kernel' for b in buffers):return dict(passed=False,status='invalid_allocation_receipt')
    buffers=sorted(buffers,key=lambda b:b['offset_bytes'])
    valid=(allocation['required_bytes_per_lane']==allocation['static_extent_bytes_per_lane']+allocation['kernel_stack_bytes_per_lane'] and sum(b['bytes_per_lane'] for b in buffers)==allocation['static_object_bytes_per_lane'] and allocation['static_object_bytes_per_lane']+allocation['alignment_padding_bytes_per_lane']==allocation['static_extent_bytes_per_lane'] and buffers[-1]['offset_bytes']+buffers[-1]['bytes_per_lane']<=allocation['static_extent_bytes_per_lane'] and all(a['offset_bytes']+a['bytes_per_lane']<=b['offset_bytes'] for a,b in zip(buffers,buffers[1:])))
    if not valid:return dict(passed=False,status='invalid_allocation_receipt')
    known=allocation.get('schema')=='pytorchsim-allocation.v1' and allocation.get('plain_gemm_scope') is True
    matches=allocation.get('capacity_bytes_per_lane')==hardware['sram_bytes_per_lane'] and allocation.get('lanes')==hardware['lanes']
    required=allocation.get('required_bytes_per_lane')
    fits=type(required) is int and required<=hardware['sram_bytes_per_lane']
    if not matches:return dict(passed=False,status='configuration_mismatch')
    if not fits:return dict(passed=False,status='capacity_exceeded',required_bytes_per_lane=required)
    if not known or not hardware['serial_tiles']:return dict(passed=False,status='capacity_not_certified',required_bytes_per_lane=required)
    return dict(passed=True,status='pass',required_bytes_per_lane=required,capacity_bytes_per_lane=hardware['sram_bytes_per_lane'],basis='ELF extent plus kernel stack; serial tiles; pinned plain-GEMM backend')
