"""Explicit capabilities and deterministic request validation."""
import hashlib,json
from ..mapping_contract import FIELDS,canonical_request,check_execution_scope

HARDWARE=dict(lanes=128,cores=1,systolic_arrays_per_core=2,sram_bytes_per_lane=131072,
              core_freq_mhz=940,dram_profile='HBM2_TPUv3',dram_channels=16,serial_tiles=True)
CAPABILITIES=dict(schema='pytorchsim-capabilities.v1',workloads=['plain_gemm'],dtypes=['float32'],
    layouts=['row_major_contiguous'],loop_orders=[['M','N','K']],lanes=[128],cores=[1],
    subtile_split_rule='N/K split factors must be lane-group aligned; M may split',
    tail_tiles=False,bias=False,graph_fusion=False,strict_external=True,
    capacity_certificate='pinned compiler ELF+kernel-stack; serialized tiles only')


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def exact_keys(value,allowed,required=()):
    if not isinstance(value,dict) or set(value)-set(allowed) or set(required)-set(value):
        raise ValueError('missing or unknown request fields')


def normalize(request):
    exact_keys(request,('schema','operator_id','mapping_id','workload','mapping','hardware'),('schema','operator_id','mapping_id','workload','mapping'))
    if request['schema']!='gemm-evaluation-request.v1':raise ValueError('unsupported request schema')
    for key in ('operator_id','mapping_id'):
        if not isinstance(request[key],str) or not request[key].strip():raise ValueError('nonempty identity required')
    w=dict(request['workload']);exact_keys(w,('kind','shape','dtype','layout'),('kind','shape','dtype','layout'))
    if w['kind']!='plain_gemm' or w['dtype']!='float32' or w['layout']!='row_major_contiguous':raise ValueError('unsupported workload capability')
    shape=w['shape']
    if not isinstance(shape,list) or len(shape)!=3 or any(type(n) is not int or n<=0 for n in shape):raise ValueError('positive M,N,K required')
    m=dict(request['mapping']);exact_keys(m,('mode','tile','subtile','loop_order','strict'),('mode','loop_order','strict'))
    if m['mode'] not in ('external','heuristic','autotune') or m['strict'] is not True or m['loop_order']!=['M','N','K']:raise ValueError('unsupported mapping mode/order or fallback policy')
    raw_hw=request.get('hardware',{});exact_keys(raw_hw,HARDWARE);hw={**HARDWARE,**raw_hw}
    for key in ('lanes','cores','systolic_arrays_per_core','sram_bytes_per_lane','core_freq_mhz','dram_channels'):
        if type(hw[key]) is not int or hw[key]<=0:raise ValueError('positive integer hardware fields required')
    size=hw['sram_bytes_per_lane']
    if size<512 or size&(size-1) or size>1048576:raise ValueError('SRAM bytes/lane must be a power of two from 512 to 1048576')
    if hw['lanes']!=128 or hw['cores']!=1 or hw['systolic_arrays_per_core'] not in (1,2) or hw['dram_profile']!='HBM2_TPUv3' or hw['dram_channels']!=16 or type(hw['serial_tiles']) is not bool:raise ValueError('unsupported hardware capability')
    if m['mode']=='external':
        if set(m)!= {'mode','tile','subtile','loop_order','strict'}:raise ValueError('external mapping requires all six tile fields')
        if any(not isinstance(m[k],list) or len(m[k])!=3 for k in ('tile','subtile')):raise ValueError('three tile/subtile dimensions required')
        values=dict(zip(FIELDS,m['tile']+m['subtile']));canonical_request(shape,values);check_execution_scope(values,lanes=hw['lanes'])
    elif 'tile' in m or 'subtile' in m:raise ValueError('native modes cannot accept an external tile')
    return dict(schema=request['schema'],operator_id=request['operator_id'],mapping_id=request['mapping_id'],workload=w,mapping=m,hardware=hw)


def config_overrides(hw):
    return dict(vpu_num_lanes=hw['lanes'],num_cores=hw['cores'],num_systolic_array_per_core=hw['systolic_arrays_per_core'],
        vpu_spad_size_bytes_per_lane=hw['sram_bytes_per_lane'],vpu_spad_size_kb_per_lane=max(1,hw['sram_bytes_per_lane']//1024),
        core_freq_mhz=hw['core_freq_mhz'],dram_channels=hw['dram_channels'],interface_serial_tiles=hw['serial_tiles'])

if __name__=='__main__':print(json.dumps(CAPABILITIES,indent=2))
