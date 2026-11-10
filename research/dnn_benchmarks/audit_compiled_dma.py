"""Compare compiled unsplit DMA regions with byte-address semantics.

Restricted to the plain pilot graph with unit-trip inner loops, where load-tag
deduplication cannot alter the visit count. Separately reproduce the pinned
backend address expression and compare its transaction counts to actual logs.
No timing or energy acceptance is granted by this audit.
"""
import argparse
import ast
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import re


def audit(run,source):
    result=json.loads((run/'result/result.json').read_text())
    root=run/'result/compiler';graphs=list(root.glob('*/*_tog.py'))
    if len(graphs)!=1:raise ValueError('requires one compiled kernel')
    path=graphs[0];tree=ast.parse(path.read_text())
    graph=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='graph'))
    if any(n.get('loop_type')=='inner_loop' and len(range(n['loop_start'],n['loop_end'],n['loop_step']))>1 for n in graph.values()):
        raise ValueError('split inner loops require a separate tag-lifetime audit')
    attrs=list(path.parent.glob('runtime_*/attribute/*'))
    if len(attrs)!=1:raise ValueError('requires one invocation')
    address_text=attrs[0].read_text().split('sram_alloc:')[0]
    bases={name:int(value) for name,value in re.findall(r'\s+(arg\d+): (\d+)',address_text)}
    instruction=(source/'TOGSim/src/Instruction.cc').read_text()
    parser=(source/'TOGSim/src/TileGraphParser.cc').read_text()
    if 'address = dram_addr + (address * _elem_bits + 7) >> 3;' not in instruction or '0, base_addr+offset,' not in parser:
        raise ValueError('address implementation changed; do not reuse the ported expression')
    logs=list((run/'result/logs').glob('*.log'))
    if len(logs)!=1:raise ValueError('requires one non-autotune timing log')
    log=logs[0].read_text()
    request_bytes=int(re.search(r'(\d+) bytes per request',log)[1])
    if request_bytes&(request_bytes-1):raise ValueError('requires power-of-two transaction size')
    observed=re.search(r'combined .*?\| (\d+) reads, (\d+) writes',log)
    observed=dict(read=int(observed[1]),write=int(observed[2]))
    expected=Counter();ported=Counter();cells=Counter();visits=Counter();mismatches=0;examples=[]
    m,n,k=result['shape'];sizes=dict(arg0=m*k,arg1=k*n,arg2=m*n)
    seen_outputs=Counter()
    def visit(i,indices):
        nonlocal mismatches
        node=graph[i];kind=node['node_type']
        if kind==2:
            for val in range(node['loop_start'],node['loop_end'],node['loop_step']):
                for child in node['children']:visit(child,{**indices,node['loop_index']:val})
            return
        if kind==3:
            if node['indirect_mode'] or node['element_size']!=32:raise ValueError('only direct float32 DMA admitted')
            base_name=node['base_address'];base=bases[base_name]
            offset=sum(indices[idx]*stride for idx,stride in zip(node['loop_idx_list'],node['loop_stride_list']))
            correct_set=set();actual_set=set();direction='write' if node['is_write'] else 'read'
            for index in itertools.product(*(range(s) for s in node['tile_size'])):
                local=sum(v*s for v,s in zip(index,node['tile_stride']))
                cell=offset+local
                if not 0<=cell<sizes[base_name]:raise ValueError('compiled DMA region exceeds tensor')
                correct=base+4*cell
                # Exact C++ precedence in the pinned backend; offset is passed unscaled.
                actual=(base+offset+local*32+7)>>3
                correct_set.add(correct//request_bytes*request_bytes)
                actual_set.add(actual//request_bytes*request_bytes)
                cells[base_name]+=1
                if node['is_write']:seen_outputs[cell]+=1
                if actual!=correct:
                    mismatches+=1
                    if len(examples)<3:examples.append(dict(tensor=base_name,element=cell,expected=correct,backend_expression=actual))
            expected[direction]+=len(correct_set);ported[direction]+=len(actual_set);visits[direction]+=1
        for child in node['children']:visit(child,indices)
    visit(0,{})
    float_arrays={name:int(count) for name,count in re.findall(r'float (\w+_spad)\[(\d+)\]',(path.parent/'global_var.h').read_text())}
    lanes=int(re.search(r'vpu_num_lanes: (\d+)',(run/'result/hardware.yml').read_text())[1])
    return dict(scope='unit-trip inner loops; one plain float32 GEMM invocation',shape=result['shape'],
        numerical_equal=result.get('numerical_equal'),request_bytes=request_bytes,
        dma_visits=dict(visits),useful_cells=dict(cells),useful_bytes=4*sum(cells.values()),
        output_elements_written_once=(len(seen_outputs)==m*n and set(seen_outputs.values())=={1}),
        correct_byte_address_transactions=dict(expected),ported_backend_transactions=dict(ported),
        observed_dram_transactions=observed,ported_expression_matches_logged_counts=dict(ported)==observed,
        addressed_cells_differing_from_byte_contract=mismatches,examples=examples,
        generated_float_array_cells_per_lane=float_arrays,lanes=lanes,
        three_float_arrays_reserved_bytes=4*lanes*sum(float_arrays.values()),
        allocation_caveat='These static arrays are not a complete measurement of peak SRAM, tags or overlap buffers.',
        source_sha256={f:hashlib.sha256((source/f).read_bytes()).hexdigest() for f in ('TOGSim/src/Instruction.cc','TOGSim/src/TileGraphParser.cc')},
        timing_accepted=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();result=audit(a.run,a.source)
    with a.out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ('useful_bytes','correct_byte_address_transactions','ported_backend_transactions','observed_dram_transactions','ported_expression_matches_logged_counts','timing_accepted')}))


if __name__=='__main__':main()
