"""Independent compiled-GEMM DMA ledger, including inner-loop load-tag reuse.

Accepts only the pinned, direct float32, no-cache, serial plain-GEMM template.
The C++ address unit test separately checks actual Simulator object code.
"""
import argparse,ast,hashlib,itertools,json,re
from collections import Counter
from pathlib import Path


def audit(run):
    result=json.loads((run/'result/result.json').read_text())
    graphs=list((run/'result/compiler').glob('*/*_tog.py'))
    if len(graphs)!=1:raise ValueError('requires exactly one kernel')
    path=graphs[0];tree=ast.parse(path.read_text())
    graph=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='graph'))
    loops={n['loop_index']:n for n in graph.values() if n['node_type']==2}
    outer=[n for n in loops.values() if n['loop_type']=='outer_loop']
    if len(outer)!=2 or outer[0]['children']!=[outer[1]['node_id']]:raise ValueError('requires two leading outer loops')
    attrs=list(path.parent.glob('runtime_*/attribute/*'))
    traces=list((run/'result/logs').glob('*.trace'))
    if len(traces)!=1:raise ValueError('requires one selected-kernel timing trace')
    lines=traces[0].read_text().strip().splitlines()
    if len(lines)!=1 or not lines[0].startswith('LAUNCH_KERNEL,'):raise ValueError('requires single selected-kernel launch')
    selected=lines[0].split(',')[5]
    attr=run/'result'/selected.removeprefix('/experiment/result/')
    if attr not in attrs:raise ValueError('selected runtime attribute is missing')
    bases={k:int(v) for k,v in re.findall(r'\s+(arg\d+): (\d+)',attr.read_text().split('sram_alloc:')[0])}
    if bases!={f'arg{i}':0x10000000*(i+1) for i in range(3)}:raise ValueError('requires canonical nonaliasing address layout')
    hardware=(run/'result/hardware.yml').read_text()
    if re.search(r'(?im)^.*cache.*:\s*(true|1)\s*$',hardware):raise ValueError('cache not in audited scope')
    lanes=int(re.search(r'vpu_num_lanes: (\d+)',hardware)[1]);systolic=lanes
    logs=list((run/'result/logs').glob('*.log'))
    if len(logs)!=1:raise ValueError('requires one timing log')
    log=logs[0].read_text();request=int(re.search(r'(\d+) bytes per request',log)[1])
    observed=re.search(r'combined .*?\| (\d+) reads, (\d+) writes',log)
    observed=dict(read=int(observed[1]),write=int(observed[2]))
    inst_observed={d:int(re.search(rf'{op}\s+inst_count: (\d+)',log)[1]) for d,op in [('read','MOVIN'),('write','MOVOUT')]}
    m,n,k=result['shape'];sizes=dict(arg0=m*k,arg1=k*n,arg2=m*n)
    transactions=Counter();visits=Counter();cells=Counter();outputs=Counter();tags={};skipped=0
    # Each tag maps to its precise region; tag reuse must never suppress a
    # different load. Counts use unique transaction blocks per emitted DMA.
    address_hash=hashlib.sha256()
    def visit(i,indices):
        nonlocal tags,skipped
        node=graph[i];kind=node['node_type']
        if kind==2:
            for val in range(node['loop_start'],node['loop_end'],node['loop_step']):
                if i==outer[-1]['node_id']:tags={}
                for child in node['children']:visit(child,{**indices,node['loop_index']:val})
            return
        if kind==3:
            if node['indirect_mode'] or node['element_size']!=32:raise ValueError('only direct float32 DMA')
            name=node['base_address'];base=bases[name]
            offset=sum(indices[idx]*stride for idx,stride in zip(node['loop_idx_list'],node['loop_stride_list']))
            region=tuple(offset+sum(v*s for v,s in zip(index,node['tile_stride'])) for index in itertools.product(*(range(s) for s in node['tile_size'])))
            if not all(0<=x<sizes[name] for x in region):raise ValueError('DMA exceeds tensor')
            if not node['is_write']:
                accum=tuple(indices[idx] for idx in node['loop_idx_list'] if loops[idx]['loop_type']=='accumulation_loop') or (0,)
                tag=sum((indices.get(idx,0)//min(loops[idx]['loop_step'],systolic) if idx in loops else 0)*stride for idx,stride in zip(node['tag_idx_list'],node['tag_stride_list']))
                key=(name,accum,tag)
                if key in tags:
                    if tags[key]!=region:raise ValueError('load-tag collision suppresses a different region')
                    skipped+=1;return
                tags[key]=region
            direction='write' if node['is_write'] else 'read'
            blocks={((base+4*cell+byte)//request)*request for cell in region for byte in range(4)}
            address_hash.update(json.dumps([direction,sorted(blocks)],separators=(',',':')).encode())
            transactions[direction]+=len(blocks);visits[direction]+=1;cells[name]+=len(region)
            if node['is_write']:
                if name!='arg2':raise ValueError('unexpected store tensor')
                outputs.update(region)
        for child in node['children']:visit(child,indices)
    visit(0,{})
    arrays={name:int(count) for name,count in re.findall(r'float (\w+_spad)\[(\d+)\]',(path.parent/'global_var.h').read_text())}
    equal=bool(result.get('numerical_equal'));once=len(outputs)==m*n and set(outputs.values())=={1}
    tx_match=dict(transactions)==observed;inst_match=dict(visits)==inst_observed
    accepted=equal and once and tx_match and inst_match
    return dict(scope='one direct float32 GEMM; fixed nonaliasing addresses; no cache; lane-aligned split geometry',runtime_attribute_count=len(attrs),selected_runtime_attribute=str(attr.relative_to(run)),shape=result['shape'],mode=result['mode'],requested_tile=result['requested_tile'],numerical_equal=equal,max_abs_error=result.get('max_abs_error'),request_bytes=request,
        emitted_dma=dict(visits),observed_dma=inst_observed,tag_reused_loads=skipped,
        useful_cells=dict(cells),useful_bytes=4*sum(cells.values()),expected_transactions=dict(transactions),observed_transactions=observed,
        transaction_bytes={d:v*request for d,v in transactions.items()},output_written_once=once,transactions_match=tx_match,instruction_counts_match=inst_match,
        expected_address_stream_sha256=address_hash.hexdigest(),total_cycles=int(re.search(r'Total execution cycles: (\d+)',log)[1]),
        float_array_cells_per_lane=arrays,float_array_reserved_bytes=4*lanes*sum(arrays.values()),
        reservation_caveat='Static three-buffer reservation, not full peak including tags and overlap buffers',
        timing_accepted=accepted,timing_acceptance_scope='Internal repaired-backend pilot consistency only; no hardware calibration or whole-DNN claim')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();result=audit(a.run)
    with a.out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))
    if not result['timing_accepted']:raise SystemExit(1)

if __name__=='__main__':main()
