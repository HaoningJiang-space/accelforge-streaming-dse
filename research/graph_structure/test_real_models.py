"""Exporter contracts; requires the isolated torch/torchvision environment."""
import pytest
torch=pytest.importorskip('torch')
from research.graph_structure.real_models import export_model, audit


def test_export_fork_and_view_materialization():
    class Fork(torch.nn.Module):
        def forward(self,x):
            a=x+1
            b=x*2
            return (a+b).flatten(1)
    g,record=export_model(Fork(),(1,3,4,4))
    assert len(g.ops)==4
    assert len(g.ops[2][1])==2
    assert g.ops[-1][2]==192
    assert len(record['metadata'])==5
    assert audit(g)['solution']['status']=='exact'


def test_functional_inplace_is_normalized():
    class Activation(torch.nn.Module):
        def forward(self,x):
            return torch.nn.functional.relu(x+1,inplace=True)
    g,record=export_model(Activation(),(1,3,4,4))
    assert len(g.ops)==2
    assert len(record['inplace_functions_normalized'])==1


def test_reject_multioutput_instead_of_serializing_outputs():
    class Split(torch.nn.Module):
        def forward(self,x):
            a,b=x.chunk(2,dim=1)
            return a+b
    with pytest.raises(ValueError,match='multi-tensor'):
        export_model(Split(),(1,4,4,4))


def test_bound_match_is_separate_from_prefix_completion():
    from research.graph_structure.analyze import DAG
    g=DAG({'X':5},[('a',('X',),7,'op'),('b',('a',),3,'op')])
    result=audit(g,state_limit=1)
    assert result['solution']['optimum'] is None
    assert result['event_certificate']=='local_bound_matches_schedule'
    assert result['event_certified_optimum']==12


def test_resnet_export_matches_cpu_shapes():
    from torchvision.models import resnet18
    from torch.fx import symbolic_trace, Interpreter
    torch.set_num_threads(2)
    model=resnet18(weights=None).eval()
    expected={}
    class Capture(Interpreter):
        def run_node(self,n):
            v=super().run_node(n)
            if isinstance(v,torch.Tensor):
                expected[n.name]=list(v.shape)
            return v
    with torch.no_grad():
        Capture(symbolic_trace(model)).run(torch.zeros(1,3,64,64))
    graph,record=export_model(model.to('meta'),(1,3,64,64))
    assert len(graph.ops)>50
    assert all(m['shape']==expected[m['name']] for m in record['metadata'])
