"""CPU eager/functional-FX equivalence and shape checks for each saved export."""
import gzip
import json
from pathlib import Path
from time import perf_counter
import torch
from torch.fx import Interpreter
from research.graph_structure.real_models import factories, functional_graph


def main():
    torch.set_num_threads(2)
    saved=json.loads(gzip.decompress(Path('research/graph_structure/results/real_models.json.gz').read_bytes()))
    records={c['name']:c for c in saved['cases'] if c['status']=='ok'}
    result=[]
    for name,factory,kwargs,shape in factories():
        if name not in records:
            continue
        start=perf_counter()
        torch.manual_seed(19)
        model=factory(**kwargs).eval()
        x=torch.randn(shape)
        shapes={}
        class Capture(Interpreter):
            def run_node(self,node):
                value=super().run_node(node)
                if isinstance(value,torch.Tensor):
                    shapes[node.name]=list(value.shape)
                elif isinstance(value,(tuple,list)):
                    tensors=[v for v in value if isinstance(v,torch.Tensor)]
                    if len(tensors)==1:
                        shapes[node.name]=list(tensors[0].shape)
                return value
        with torch.no_grad():
            original=model(x)
            gm,_,_=functional_graph(model)
            normalized=Capture(gm).run(x)
        torch.testing.assert_close(normalized,original,rtol=1e-4,atol=1e-5)
        metadata=records[name]['export']['metadata']
        assert all(shapes[m['name']]==m['shape'] for m in metadata), name
        a=original if isinstance(original,torch.Tensor) else original['out']
        b=normalized if isinstance(normalized,torch.Tensor) else normalized['out']
        row=dict(name=name,status='passed',tensor_shapes_checked=len(metadata),
                 max_abs_error=float((a-b).abs().max()),seconds=perf_counter()-start)
        print(row,flush=True)
        result.append(row)
        Path('research/graph_structure/results/export_validation.json').write_text(
            json.dumps(dict(seed=19,rtol=1e-4,atol=1e-5,torch=torch.__version__,
                            weights=None,cases=result),indent=2)+'\n',encoding='utf-8')
        del model,gm,original,normalized


if __name__=='__main__':
    main()
