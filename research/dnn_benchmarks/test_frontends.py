import json
from pathlib import Path
import unittest

from research.index_coupling.graph.model import Graph
from research.index_coupling.graph.curve import curve
from research.index_coupling.simulate_nest import input_value
from .frontends import lower_island
from .replay import replay,evaluate


class FrontendTests(unittest.TestCase):
    def test_pointwise_formulas_against_native_torch(self):
        import torch
        for x in (-3.,-.5,0.,2.):
            value=torch.tensor(x,dtype=torch.float64)
            for approximate in ('none','tanh'):
                expected=torch.nn.functional.gelu(value,approximate=approximate).item()
                self.assertAlmostEqual(evaluate('gelu',[x],dict(approximate=approximate)),expected,places=12)
            self.assertEqual(evaluate('relu',[x],{}),torch.relu(value).item())
            expected=torch.nn.functional.batch_norm(value.reshape(1,1,1,1),
                torch.tensor([1.],dtype=torch.float64),torch.tensor([3.],dtype=torch.float64),
                torch.tensor([2.],dtype=torch.float64),torch.tensor([4.],dtype=torch.float64),eps=1e-5).item()
            self.assertAlmostEqual(evaluate('batchnorm_eval',[x,1.,3.,2.,4.],dict(eps=1e-5)),expected,places=12)

    def test_linear_preserves_distinct_equal_size_indices_and_native_values(self):
        inventory=dict(model='fixture',nodes=[
            dict(name='x',output=dict(shape=[2,3])),
            dict(name='fc',kind='linear',tensor_inputs=['x'],target='fc',bias=True,output=dict(shape=[2,3]))])
        ir=lower_island(inventory,['fc'])
        g=Graph(ir['sizes'],[(o,{t:tuple(ds) for t,ds in a.items()}) for o,a in ir['ops']])
        self.assertNotEqual(g.dims('n_x')[-1],g.dims('n_fc')[-1])
        self.assertEqual(len(ir['sizes']),3)
        for leaf in ('v1','v2'):
            for c,q,w in curve(g,witness=True,partitions='dp',scalar_leaf=leaf):
                actual=replay(g,ir['semantics'],w,leaf)
                self.assertEqual((c,q),(actual['peak'],actual['traffic']))
        import torch
        x=torch.tensor([[input_value(('n_x',(i,k))) for k in range(3)] for i in range(2)],dtype=torch.float64)
        w=torch.tensor([[input_value(('p_fc.weight',(j,k))) for k in range(3)] for j in range(3)],dtype=torch.float64)
        b=torch.tensor([input_value(('p_fc.bias',(j,))) for j in range(3)],dtype=torch.float64)
        native=torch.nn.functional.linear(x,w,b)
        independent=torch.tensor([[sum(evaluate('product',[float(x[i,k]),float(w[j,k])],{}) for k in range(3))+float(b[j]) for j in range(3)] for i in range(2)])
        self.assertTrue(torch.equal(native,independent))

    def test_inventory_preserves_barriers_and_full_model_shapes(self):
        root=Path(__file__).parent/'results/fx_inventory'
        expected={'resnet50':(25557032,[1,1000]),'vit_b_16':(86567656,[1,1000]),'unet2015':(31030658,[1,2,388,388])}
        for model,(params,shape) in expected.items():
            d=json.loads((root/f'{model}.json').read_text())
            self.assertEqual(d['parameters'],params)
            self.assertEqual(d['output']['shape'],shape)
            self.assertGreater(d['kinds']['boundary'],0)
            self.assertFalse(any(w['whole_window_search_supported'] for w in d['windows']))
            original={i['island']:i for i in d['resource_islands'] if i['extent_cap'] is None}
            for ir in d['resource_islands']:
                if ir['extent_cap']==2:
                    self.assertEqual(ir['original_sizes'],original[ir['island']]['sizes'])
                    self.assertTrue(all(n<=2 for n in ir['sizes'].values()))


if __name__=='__main__':unittest.main()
