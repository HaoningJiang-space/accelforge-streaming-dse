"""Conservative plain-GEMM import contract; no physical SRAM/timing claim.

Canonical serializer and source ledger adapted from the independent audit at
7e03ab3b (audit_mapping_interface.py). Keep the audit branch independent.
"""
FIELDS=('TILE_M','TILE_N','TILE_K','SUB_TILE_M','SUB_TILE_N','SUB_TILE_K')


def canonical_request(shape,values):
    if len(shape)!=3 or any(type(n) is not int or n<=0 for n in shape):
        raise ValueError('positive integer M,N,K required')
    if set(values)!=set(FIELDS) or any(type(values[k]) is not int or values[k]<=0 for k in FIELDS):
        raise ValueError('all six named positive integer tile fields required')
    tile=[values[k] for k in FIELDS[:3]];sub=[values[k] for k in FIELDS[3:]]
    if any(t>n or n%t for n,t in zip(shape,tile)):
        raise ValueError('pilot requires tiles dividing each dimension')
    if any(s>t or t%s for t,s in zip(tile,sub)):
        raise ValueError('pilot requires subtiles dividing each tile')
    return {'_'.join(map(str,shape)):{k:values[k] for k in FIELDS}}


def check_serialized_request(data,shape,values):
    expected=canonical_request(shape,values);key=next(iter(expected))
    if set(data)!={key} or tuple(data[key])!=FIELDS or data[key]!=expected[key]:
        raise ValueError('mapping file shape, fields, values or insertion order changed')
    return [data[key][f] for f in FIELDS]


def check_execution_scope(values,diagnostic=False):
    if values['SUB_TILE_N']!=values['TILE_N'] and not diagnostic:
        raise ValueError('N-split subtiles are outside the validated pilot subset; diagnostic flag required')


def template_ledger(shape,tile,element_bytes=4):
    canonical_request(shape,dict(zip(FIELDS,(*tile,*tile))))
    if type(element_bytes) is not int or element_bytes<=0:raise ValueError('positive integer bytes required')
    m,n,k=shape;tm,tn,tk=tile
    return dict(mac_count=m*n*k,useful_input_elements=dict(X=m*k*(n//tn),W=k*n*(m//tm)),
        useful_output_elements=m*n,useful_bytes=element_bytes*(m*k*(n//tn)+k*n*(m//tm)+m*n),
        logical_buffer_bytes=element_bytes*(tm*tk+tk*tn+tm*tn),
        source_dma_operations=(m//tm)*(n//tn)*(2*(k//tk)+1),
        partial_sum_dram_reads=0,partial_sum_dram_writes=0,
        caveat='Pre-pass logical counts; not compiled DMA bytes, DRAM transactions or physical SRAM.')
