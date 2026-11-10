import ast
import itertools
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from .mapping_contract import FIELDS,canonical_request,check_serialized_request,template_ledger


class MappingContractTests(unittest.TestCase):
    def test_all_input_orders_select_same_actual_upstream_tuple(self):
        source=Path(__file__).parent/'vendor/PyTorchSim/PyTorchSimFrontend/mlir/mlir_gemm_template.py'
        tree=ast.parse(source.read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MLIRGemmTemplate')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='select_tile')
        code=compile(ast.Module(body=[method],type_ignores=[]),'<upstream-selector>','exec')
        shape=(64,128,32);values=dict(zip(FIELDS,(16,32,8,8,16,8)))
        with TemporaryDirectory() as d:
            path=Path(d)/'request.json'
            config=SimpleNamespace(codegen_mapping_strategy='external-then-heuristic',
                                   codegen_external_mapping_file=str(path),CONFIG_SUBTILE=True)
            env=dict(json=json,Path=Path,extension_config=config);exec(code,env)
            def fallback(*a,**kw):raise AssertionError('unexpected fallback')
            kernel=SimpleNamespace(vector_lane=8,gemm_combination_mapping=fallback)
            for fields in itertools.permutations(FIELDS):
                request=canonical_request(shape,{f:values[f] for f in fields})
                path.write_text(json.dumps(request))
                check_serialized_request(json.loads(path.read_text()),shape,values)
                actual=env['select_tile'](None,kernel,*shape,0,0,0,4)
                self.assertEqual(actual,[[16,32,8,8,16,8]])

    def test_bad_geometry_missing_shapes_and_reserialization_fail_closed(self):
        shape=(64,128,32);good=dict(zip(FIELDS,(16,32,8,8,16,8)))
        for changes in ({'TILE_M':0},{'TILE_N':30},{'SUB_TILE_M':32},{'TILE_K':True}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                canonical_request(shape,dict(good,**changes))
        for data in ({}, {'64_128_32':{k:good[k] for k in FIELDS[:3]}},
                     json.loads(json.dumps(canonical_request(shape,good),sort_keys=True))):
            with self.assertRaises(ValueError):check_serialized_request(data,shape,good)

    def test_ledger_matches_enumerated_source_tile_accesses(self):
        shape=(64,128,32);tile=(16,32,8);reads=stores=ops=macs=0
        m,n,k=shape;tm,tn,tk=tile
        for i in range(0,m,tm):
            for j in range(0,n,tn):
                for h in range(0,k,tk):
                    reads+=tm*tk+tk*tn;ops+=2;macs+=tm*tn*tk
                stores+=tm*tn;ops+=1
        ledger=template_ledger(shape,tile)
        self.assertEqual((ledger['useful_bytes'],ledger['source_dma_operations'],ledger['mac_count']),
                         (4*(reads+stores),ops,macs))


if __name__=='__main__':unittest.main()
