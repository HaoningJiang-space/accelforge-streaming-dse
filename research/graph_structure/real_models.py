"""Export installed Torchvision models with FX and audit a materialized DAG.

No checkpoints are downloaded. Meta execution supplies actual operator shapes;
this is not a physical allocator trace. All non-identity tensor values, including
views, are charged as separate materializations; module workspaces are excluded.
"""
import argparse
import gzip
import hashlib
import inspect
import json
from pathlib import Path
import platform
from time import perf_counter

from research.graph_structure.analyze import DAG, METRICS, exact, greedy, lookahead, trace


def functional_graph(model):
    from torch.fx import symbolic_trace
    # Make leaf activation modules functional before scheduling independently.
    changed=[]
    for name,module in model.named_modules():
        if getattr(module,'inplace',False):
            module.inplace=False
            changed.append(name)
    gm=symbolic_trace(model.eval())
    changed_functions=[]
    for node in gm.graph.nodes:
        if node.kwargs.get('inplace',False):
            node.kwargs={**node.kwargs,'inplace':False}
            changed_functions.append(node.name)
        if node.op=='call_method' and str(node.target).endswith('_'):
            raise ValueError(f'mutating method unsupported: {node.target}')
    gm.recompile()
    return gm,changed,changed_functions


def export_model(model, shape):
    import torch
    from torch.fx import Interpreter
    gm,changed,changed_functions=functional_graph(model)
    values={}
    class Capture(Interpreter):
        def run_node(self,node):
            result=super().run_node(node)
            values[node]=result
            return result
    with torch.no_grad():
        Capture(gm).run(torch.empty(shape,device='meta'))

    def tensors(value):
        if isinstance(value,torch.Tensor):
            return [value]
        if isinstance(value,(tuple,list)):
            return [t for x in value for t in tensors(x)]
        if isinstance(value,dict):
            return [t for x in value.values() for t in tensors(x)]
        return []

    inputs,ops,owners,metadata={},[],{},[]
    omitted=[]
    for node in gm.graph.nodes:
        ts=tensors(values[node])
        if node.op=='output':
            continue
        if node.op=='get_attr':
            omitted.append(dict(node=node.name,reason='parameter/buffer'))
            continue
        if not ts:
            omitted.append(dict(node=node.name,reason='non-tensor shape/control result'))
            continue
        if len(ts)!=1:
            raise ValueError(f'{node.name}: multi-tensor output requires atomic multi-output IR')
        value=ts[0]
        size=value.numel()*value.element_size()
        if size<=0:
            raise ValueError(f'{node.name}: zero-sized tensor unsupported')
        if id(value) in owners:
            # Tuple projection / Identity returns exactly the same Tensor object.
            omitted.append(dict(node=node.name,reason='same Tensor object',owner=owners[id(value)]))
            continue
        deps=[]
        for prior in node.all_input_nodes:
            for tensor in tensors(values[prior]):
                owner=owners.get(id(tensor))
                if owner is not None and owner not in deps:
                    deps.append(owner)
        if node.op=='placeholder':
            inputs[node.name]=size
        elif not deps:
            # E.g. ViT class-token expand: immutable parameter-derived source.
            inputs[node.name]=size
            omitted.append(dict(node=node.name,reason='parameter-derived source counted as external tensor'))
        else:
            module=gm.get_submodule(str(node.target)) if node.op=='call_module' else None
            kind=(type(module).__module__+'.'+type(module).__qualname__) if module is not None else (
                getattr(node.target,'__module__','')+'.'+getattr(node.target,'__qualname__',str(node.target)))
            if node.op=='call_method' and str(node.target).endswith('_'):
                raise ValueError(f'mutating method unsupported: {node.target}')
            ops.append((node.name,tuple(deps),size,kind))
        owners[id(value)]=node.name
        metadata.append(dict(name=node.name,shape=list(value.shape),dtype=str(value.dtype),
                             bytes=size,fx_op=node.op,target=str(node.target)))
    output_node=next(n for n in gm.graph.nodes if n.op=='output')
    outputs=[owners[id(t)] for t in tensors(values[output_node])]
    if len(outputs)!=1 or not ops or outputs[0]!=ops[-1][0]:
        raise ValueError('require single final output; early output retention needs explicit sink')
    return DAG(inputs,ops),dict(fx_code=gm.code,metadata=metadata,omitted=omitted,
                               inplace_modules_normalized=changed,outputs=outputs,
                               inplace_functions_normalized=changed_functions,
                               fx_nodes=len(list(gm.graph.nodes)))


def audit(graph, state_limit=5000, time_limit=10):
    schedules={}
    candidates={'source':list(range(len(graph.ops)))}
    candidates.update({f'greedy_{name}':greedy(graph,j) for j,name in enumerate(METRICS)})
    candidates['lookahead_2']=lookahead(graph,2)
    for name,order in candidates.items():
        peaks,rows=trace(graph,order)
        schedules[name]=dict(order=[graph.ops[i][0] for i in order],peaks=peaks,trace=rows)
    solved=exact(graph,state_limit,time_limit)
    # Every execution must simultaneously hold each op's inputs and new output.
    lower=max(sum(graph.sizes[x] for x in set(args)|{name}) for name,args,_,_ in graph.ops)
    upper=min(s['peaks']['event_bytes'] for s in schedules.values())
    event_optimum=solved['optimum']['event_bytes'] if solved['status']=='exact' else (upper if lower==upper else None)
    return dict(schedules=schedules,solution=solved,event_local_lower_bound=lower,
                event_best_schedule_upper_bound=upper,event_certified_optimum=event_optimum,
                event_certificate='prefix_dp' if solved['status']=='exact' else
                ('local_bound_matches_schedule' if lower==upper else 'unresolved'))


def factories():
    from torchvision import models
    for name in ('resnet18','resnet50','mobilenet_v2','mobilenet_v3_small','efficientnet_b0',
                 'densenet121','squeezenet1_1','shufflenet_v2_x1_0','convnext_tiny','vit_b_16'):
        yield name,getattr(models,name),dict(weights=None), (1,3,224,224)
    yield 'deeplabv3_resnet50',models.segmentation.deeplabv3_resnet50,dict(
        weights=None,weights_backbone=None,aux_loss=False),(1,3,224,224)


def main():
    import torch
    import torchvision
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models',nargs='*')
    parser.add_argument('--state-limit',type=int,default=5000)
    parser.add_argument('--time-limit',type=float,default=10)
    parser.add_argument('--output',type=Path,default=Path('research/graph_structure/results/real_models.json.gz'))
    args=parser.parse_args()
    result=dict(torch=torch.__version__,torchvision=torchvision.__version__,python=platform.python_version(),
                dtype='float32',device='meta',weights=None,training=False,
                abstraction='FX leaf-module DAG; independent full tensor materialization incl views; no workspace/weights',
                limits=dict(states=args.state_limit,seconds=args.time_limit),cases=[])
    for name,factory,kwargs,shape in factories():
        if args.models and name not in args.models:
            continue
        start=perf_counter()
        try:
            with torch.device('meta'):
                model=factory(**kwargs).eval()
            graph,export=export_model(model,shape)
            source_path=Path(inspect.getfile(type(model)))
            source=dict(model_class=type(model).__module__+'.'+type(model).__qualname__,
                        source_file=source_path.name,sha256=hashlib.sha256(source_path.read_bytes()).hexdigest())
            measured=audit(graph,args.state_limit,args.time_limit)
            row=dict(name=name,status='ok',input_shape=shape,source=source,
                     graph=dict(inputs=graph.inputs,ops=graph.ops),export=export,**measured)
            print(name,len(graph.ops),measured['solution']['status'],measured['event_certificate'],
                  measured['schedules']['source']['peaks'],flush=True)
        except Exception as error:
            row=dict(name=name,status='failed',error=repr(error))
            print(name,'FAILED',repr(error),flush=True)
        row['seconds']=perf_counter()-start
        result['cases'].append(row)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        # Checkpoint every model; deterministic gzip header, elapsed times remain measured.
        args.output.write_bytes(gzip.compress((json.dumps(result,indent=2)+'\n').encode(),mtime=0))


if __name__=='__main__':
    main()
