"""Diagnose archived one-tile, row-padded GEMMs; never accept their timing.

This deliberately narrow diagnostic compares the full emitted DMA with the
logical tensor, the validation wrapper's malloc, and completed timing counters.
It does not add padding semantics to the production auditor.
"""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from .audit_repaired_dma import audit, DMABoundsError
from .togsim_statistics import parse_completed_statistics


def one(paths):
    paths=list(paths)
    if len(paths)!=1:raise ValueError('requires exactly one artifact')
    return paths[0]


def diagnose(run):
    result=json.loads((run/'result/result.json').read_text())
    graph_path=one((run/'result/compiler').glob('*/*_tog.py'))
    tree=ast.parse(graph_path.read_text())
    graph=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='graph'))
    events=[]

    def visit(node_id,indices):
        node=graph[node_id]
        if node['node_type']==2:
            for val in range(node['loop_start'],node['loop_end'],node['loop_step']):
                for child in node['children']:
                    visit(child,{**indices,node['loop_index']:val})
            return
        if node['node_type']==3:events.append((node,indices))
        for child in node['children']:visit(child,indices)

    visit(0,{})
    if len(events)!=3:raise ValueError('diagnostic requires two loads and one store, each emitted once')
    nodes={node['base_address']:node for node,_ in events}
    if set(nodes)!={'arg0','arg1','arg2'}:raise ValueError('unexpected argument set')
    m,n,k=result['shape'];padded_m=nodes['arg0']['tile_size'][0]
    if padded_m<=m:raise ValueError('requires row padding')
    shapes={'arg0':[padded_m,k],'arg1':[k,n],'arg2':[padded_m,n]}
    strides={'arg0':[k,1],'arg1':[n,1],'arg2':[n,1]}
    logical={'arg0':4*m*k,'arg1':4*k*n,'arg2':4*m*n}
    for node,indices in events:
        name=node['base_address']
        if (node['indirect_mode'] or node['element_size']!=32 or
            node['tile_size']!=shapes[name] or node['tile_stride']!=strides[name] or
            bool(node['is_write'])!=(name=='arg2') or
            any(indices[idx] for idx in node['loop_idx_list'])):
            raise ValueError('requires dense, direct, origin-zero, full-tile DMA')
    wrapper=(graph_path.parent/'validation_wrapper.c').read_text()
    allocations=re.findall(r'float\* (\w+) = malloc\((\d+)ULL\)',wrapper)
    if len(allocations)!=3:raise ValueError('requires three float argument allocations')
    # Establish argument order from the actual call, not allocator declaration order.
    call=re.search(r'wrapper_kernel\((c_\w+), \1, 0, (\d+), 1, (c_\w+), \3, 0, (\d+), 1, (c_\w+), \5, 0, (\d+), 1\);',wrapper)
    if not call:raise ValueError('unrecognized wrapper argument contract')
    allocated=dict(allocations)
    for i in range(3):
        if 4*int(call[2*i+2])!=logical[f'arg{i}']:raise ValueError('wrapper logical extent differs')
    hardware=(run/'result/hardware.yml').read_text()
    channels=int(re.search(r'^dram_channels: (\d+)$',hardware,re.MULTILINE)[1])
    log=one((run/'result/logs').glob('*.log')).read_text()
    request=int(re.search(r'(\d+) bytes per request',log)[1])
    statistics=parse_completed_statistics(log,channels)
    layouts=result['timing_address_layouts']
    if len(layouts)!=1 or layouts[0]['bytes']!=list(logical.values()):
        raise ValueError('timing layout differs from logical tensors')
    expected=Counter();clipped=Counter();emitted=Counter();tensors={}
    for name,node in nodes.items():
        size=4*shapes[name][0]*shapes[name][1]
        base=layouts[0]['addresses'][name]
        direction='write' if node['is_write'] else 'read'
        expected[direction]+=(base+size-1)//request-base//request+1
        clipped[direction]+=(base+logical[name]-1)//request-base//request+1
        emitted[direction]+=1
        allocation=int(allocated[call[2*int(name[-1])+1]])
        tensors[name]=dict(logical_bytes=logical[name],dma_byte_interval=[0,size],
                           excess_bytes=size-logical[name],validation_malloc_bytes=allocation,
                           inside_validation_malloc=size<=allocation)
    try:
        audit(run)
    except DMABoundsError as error:
        rejection=error.details
    else:
        raise ValueError('expected strict logical-bounds rejection')
    artifacts={str(p.relative_to(run)):hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(run.rglob('*')) if p.is_file()}
    return dict(case=run.name,shape=result['shape'],padded_m=padded_m,
                numerical_equal=result['numerical_equal'],wrong_elements=result['wrong_elements'],
                tensors=tensors,request_bytes=request,emitted_dma=dict(emitted),
                expected_full_tile_transactions=dict(expected),
                hypothetical_clipped_transactions=dict(clipped),
                observed_transactions=statistics['observed_transactions'],
                transactions_match=dict(expected)==statistics['observed_transactions'],
                instruction_counts_match=dict(emitted)==statistics['observed_dma'],
                strict_rejection=rejection,timing_accepted=False,
                scope='post-hoc diagnosis only; no new simulator run or padding acceptance',
                artifact_sha256=artifacts)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    results=[diagnose(args.runs/name) for name in ('resnet_c2_heuristic','resnet_c3_heuristic')]
    with args.out.open('x') as f:json.dump(results,f,indent=2);f.write('\n')
    for r in results:
        print(r['case'],r['shape'][0],'->',r['padded_m'],r['expected_full_tile_transactions'],
              'matches:',r['transactions_match'] and r['instruction_counts_match'])
    if not all(r['transactions_match'] and r['instruction_counts_match'] for r in results):
        raise SystemExit(1)


if __name__=='__main__':main()
