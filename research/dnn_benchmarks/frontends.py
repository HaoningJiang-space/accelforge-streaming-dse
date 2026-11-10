"""FX inventories and a deliberately restricted, out-of-place resource IR.

Unsupported operators are barriers, never replaced with a GEMM or a copy.
No pretrained weights are downloaded. Meta execution propagates real shapes.
An extracted island has DRAM boundaries; it is not a whole-model optimum.
"""
import argparse
from collections import Counter
import hashlib
import inspect
import json
from math import prod
import operator
from pathlib import Path


def unet2015():
    """Original valid-convolution U-Net geometry: 572 -> 388, 1 input/2 classes.

    64/128/256/512/1024 channels, transpose-convolution upsampling and central
    cropping. Architecture follows https://arxiv.org/abs/1505.04597 Figure 1.
    This is our architecture implementation, not pretrained paper software.
    """
    import torch
    from torch import nn

    def block(a,b):
        return nn.Sequential(nn.Conv2d(a,b,3),nn.ReLU(),nn.Conv2d(b,b,3),nn.ReLU())

    class UNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.down=nn.ModuleList([block(a,b) for a,b in zip((1,64,128,256,512),(64,128,256,512,1024))])
            self.pool=nn.MaxPool2d(2)
            self.up=nn.ModuleList([nn.ConvTranspose2d(a,b,2,stride=2) for a,b in zip((1024,512,256,128),(512,256,128,64))])
            self.merge=nn.ModuleList([block(a,b) for a,b in zip((1024,512,256,128),(512,256,128,64))])
            self.head=nn.Conv2d(64,2,1)

        def forward(self,x):
            skips=[]
            for layer in self.down[:-1]:
                x=layer(x);skips.append(x);x=self.pool(x)
            x=self.down[-1](x)
            for up,merge,skip in zip(self.up,self.merge,reversed(skips)):
                x=up(x)
                dh=(skip.shape[-2]-x.shape[-2])//2
                dw=(skip.shape[-1]-x.shape[-1])//2
                cropped=skip[:,:,dh:dh+x.shape[-2],dw:dw+x.shape[-1]]
                x=merge(torch.cat((cropped,x),dim=1))
            return self.head(x)
    return UNet()


def tensor_meta(meta):
    if hasattr(meta,'shape') and hasattr(meta,'dtype'):
        return dict(shape=list(meta.shape),dtype=str(meta.dtype),stride=list(meta.stride))
    if isinstance(meta,(list,tuple)):
        return [tensor_meta(m) for m in meta]
    return None


def extract(model_name):
    import torch,torchvision
    from torch import nn
    from torch.fx.passes.shape_prop import ShapeProp
    with torch.device('meta'):
        if model_name=='resnet50':
            model=torchvision.models.resnet50(weights=None).eval();shape=(1,3,224,224)
        elif model_name=='vit_b_16':
            model=torchvision.models.vit_b_16(weights=None).eval();shape=(1,3,224,224)
        elif model_name=='unet2015':
            model=unet2015().eval();shape=(1,1,572,572)
        else:raise ValueError(model_name)
    gm=torch.fx.symbolic_trace(model)
    ShapeProp(gm).propagate(torch.empty(shape,device='meta'))
    rows=[]
    for node in gm.graph.nodes:
        meta=tensor_meta(node.meta.get('tensor_meta'))
        row=dict(name=node.name,fx_op=node.op,target=str(node.target),
                 inputs=[n.name for n in node.all_input_nodes],output=meta,
                 kind='boundary',reason='operator has no exact lowering in this resource IR')
        if node.op in ('placeholder','get_attr','output'):
            row.update(kind='interface',reason='FX interface or parameter')
        elif meta is None:
            row.update(kind='shape_only',reason='no tensor result')
        elif node.op=='call_module':
            m=gm.get_submodule(node.target)
            row['module_type']=type(m).__name__
            row['parameters']={k:list(p.shape) for k,p in m.named_parameters(recurse=False)}
            if isinstance(m,nn.Linear):row.update(kind='linear',bias=m.bias is not None,reason=None)
            elif isinstance(m,nn.Conv2d):
                row['conv']=dict(kernel=list(m.kernel_size),stride=list(m.stride),padding=list(m.padding),groups=m.groups,dilation=list(m.dilation))
                if m.kernel_size==(1,1) and m.stride==(1,1) and m.padding==(0,0) and m.groups==1:
                    row.update(kind='conv1x1',bias=m.bias is not None,reason=None)
                else:row['reason']='affine spatial indexing / padding / groups not representable by rank projections'
            elif isinstance(m,nn.BatchNorm2d) and m.affine and m.track_running_stats:
                row.update(kind='batchnorm_eval',eps=m.eps,reason=None)
            elif isinstance(m,(nn.ReLU,nn.GELU)):
                row.update(kind='relu' if isinstance(m,nn.ReLU) else 'gelu',
                           inplace=getattr(m,'inplace',False),approximate=getattr(m,'approximate','none'),reason=None)
            elif isinstance(m,(nn.Dropout,nn.Identity)):
                row.update(kind='alias',reason='evaluation-mode identity')
        elif node.op=='call_function' and node.target in (operator.add,torch.add) and len(row['inputs'])==2:
            row.update(kind='add',reason=None)
        rows.append(row)
    lookup={r['name']:r for r in rows}
    alias={r['name']:r['inputs'][0] for r in rows if r['kind']=='alias'}
    def resolve(n):
        while n in alias:n=alias[n]
        return n
    for row in rows:row['tensor_inputs']=[resolve(n) for n in row['inputs'] if isinstance(lookup[n]['output'],dict)]
    compute=[r for r in rows if r['kind'] not in ('interface','shape_only','alias')]
    islands=[];pending=[]
    for row in compute:
        if row['kind']=='boundary':
            if pending:islands.append(pending);pending=[]
        else:pending.append(row['name'])
    if pending:islands.append(pending)
    windows=[]
    for size in (16,32,64,128):
        selected=compute[:size]
        windows.append(dict(requested_ops=size,available=len(compute)>=size,
            actual_ops=len(selected),supported_ops=sum(r['kind']!='boundary' for r in selected),
            barriers=[r['name'] for r in selected if r['kind']=='boundary'],
            whole_window_search_supported=len(selected)==size and all(r['kind']!='boundary' for r in selected)))
    source_file=Path(inspect.getfile(type(model)))
    return dict(schema='dnn-fx-inventory.v1',model=model_name,input_shape=shape,
        output=rows[-1]['output'],parameters=sum(p.numel() for p in model.parameters()),
        torch=torch.__version__,torchvision=torchvision.__version__,weights='none',mode='eval',
        source_file=source_file.name,source_sha256=hashlib.sha256(source_file.read_bytes()).hexdigest(),
        fx_nodes=len(rows),compute_nodes=len(compute),kinds=dict(Counter(r['kind'] for r in compute)),
        nodes=rows,islands=islands,windows=windows,
        contract='float32, out-of-place functional operators; unsupported operators terminate islands')


def lower_island(inventory,names,extent_cap=None):
    """Keep index identities from semantics, never identify ranks by equal size."""
    rows={r['name']:r for r in inventory['nodes']}
    shapes={};parent={};ops=[];semantics={}
    def tensor(name,shape):
        shape=tuple(shape)
        if name in shapes:
            assert shapes[name]==shape
        shapes[name]=shape
        axes=tuple((name,i) for i in range(len(shape)))
        for a in axes:parent.setdefault(a,a)
        return axes
    def find(a):
        if parent[a]!=a:parent[a]=find(parent[a])
        return parent[a]
    def join(a,b):
        assert shapes[a[0]][a[1]]==shapes[b[0]][b[1]],'inconsistent semantic rank equality'
        a,b=find(a),find(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    def edge(n):
        r=rows[n]
        assert isinstance(r['output'],dict)
        return tensor('n_'+n,r['output']['shape'])
    def add_op(name,inputs,output,kind,**kw):
        ops.append((name,tuple(inputs)+(output,)))
        semantics[name]=dict(kind=kind,**kw)
    for name in names:
        r=rows[name];kind=r['kind'];ins=r['tensor_inputs'];out='n_'+name
        assert kind not in ('boundary','interface','shape_only','alias')
        oa=edge(name)
        ia=[edge(n) for n in ins]
        it=['n_'+n for n in ins]
        if kind in ('linear','conv1x1'):
            assert len(ia)==1
            channel=-1 if kind=='linear' else 1
            for j in range(len(oa)):
                if j!=channel%len(oa):join(ia[0][j],oa[j])
            w='p_'+r['target']+'.weight'
            wa=tensor(w,(shapes[out][channel],shapes[it[0]][channel]))
            join(wa[0],oa[channel]);join(wa[1],ia[0][channel])
            contraction=out if not r['bias'] else out+'_prebias'
            if r['bias']:
                ca=tensor(contraction,shapes[out])
                for a,b in zip(ca,oa):join(a,b)
            add_op(name+'_matmul',it+[w],contraction,'product')
            if r['bias']:
                bias='p_'+r['target']+'.bias';ba=tensor(bias,(shapes[out][channel],));join(ba[0],oa[channel])
                add_op(name+'_bias',[contraction,bias],out,'add')
        elif kind=='batchnorm_eval':
            for a,b in zip(ia[0],oa):join(a,b)
            params=[]
            for param in ('running_mean','running_var','weight','bias'):
                p='p_'+r['target']+'.'+param;pa=tensor(p,(shapes[out][1],));join(pa[0],oa[1]);params.append(p)
            add_op(name,it+params,out,kind,eps=r['eps'])
        else:
            for axes in ia:
                assert len(axes)<=len(oa)
                for a,b in zip(reversed(axes),reversed(oa)):
                    if shapes[a[0]][a[1]]==shapes[b[0]][b[1]]:join(a,b)
                    else:assert shapes[a[0]][a[1]]==1,'non-broadcast input'
            add_op(name,it,out,kind,approximate=r.get('approximate','none'))
    roots=sorted({find(a) for a in parent});rn={a:f'r{i}' for i,a in enumerate(roots)}
    original={rn[a]:shapes[a[0]][a[1]] for a in roots}
    sizes={v:min(n,extent_cap) if extent_cap else n for v,n in original.items()}
    dimensions={t:tuple(rn[find((t,j))] for j in range(len(s))) for t,s in shapes.items()}
    assert all(len(ds)==len(set(ds)) for ds in dimensions.values()),'diagonal projection unsupported'
    serialized=[(o,{t:dimensions[t] for t in ts}) for o,ts in ops]
    steps=sum(prod(sizes[v] for v in {v for t in ts for v in dimensions[t]}) for _,ts in ops)
    return dict(schema='dnn-resource-island.v1',model=inventory['model'],fx_nodes=names,
        sizes=sizes,original_sizes=original,extent_cap=extent_cap,ops=serialized,semantics=semantics,
        scalar_steps=steps,element_bytes=4,
        contract='isolated island with DRAM input/output boundaries; all ops functional/out-of-place')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    for model in ('resnet50','unet2015','vit_b_16'):
        path=args.out/f'{model}.json'
        if path.exists():raise FileExistsError(path)
        record=extract(model)
        lowered=[]
        for i,names in enumerate(record['islands']):
            for cap in (None,2):
                ir=lower_island(record,names,cap)
                ir['island']=i
                lowered.append(ir)
        record['resource_islands']=lowered
        path.write_text(json.dumps(record,indent=2)+'\n')
        print(model,record['compute_nodes'],record['kinds'],'max island',max(map(len,record['islands']),default=0),flush=True)


if __name__=='__main__':main()
