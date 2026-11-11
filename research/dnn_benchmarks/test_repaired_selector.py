"""Exercise the patched upstream selector without importing Torch/MLIR."""
import ast,itertools,json,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from .mapping_contract import FIELDS,check_execution_scope

class RepairedSelectorTests(unittest.TestCase):
    def test_actual_patched_selector(self):
        root=Path(__file__).parent;rel='PyTorchSimFrontend/mlir/mlir_gemm_template.py'
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);source=tmp/rel;source.parent.mkdir(parents=True)
            source.write_bytes((root/'vendor/PyTorchSim'/rel).read_bytes())
            subprocess.run(['git','apply',str((root/'patches/0002-external-gemm-contract.patch').resolve())],cwd=tmp,check=True)
            cls=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='MLIRGemmTemplate')
            method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='select_tile')
            path=tmp/'mapping.json';config=SimpleNamespace(codegen_mapping_strategy='external-then-heuristic',codegen_external_mapping_file=str(path),CONFIG_SUBTILE=True)
            env=dict(json=json,Path=Path,extension_config=config)
            exec(compile(ast.Module(body=[method],type_ignores=[]),'<patched-selector>','exec'),env)
            def fallback(*a,**kw):raise AssertionError('unexpected fallback')
            kernel=SimpleNamespace(vector_lane=128,gemm_combination_mapping=fallback)
            def select(shape,values):
                path.write_text(json.dumps({'_'.join(map(str,shape)):values}))
                return env['select_tile'](None,kernel,*shape,0,0,0,4)
            good=dict(zip(FIELDS,(16,32,8,8,32,8)))
            for order in itertools.permutations(FIELDS):
                self.assertEqual(select((64,128,32),{k:good[k] for k in order}),[list(good.values())])
            for change in ({'SUB_TILE_N':16},{'SUB_TILE_K':4},{'TILE_M':0},{'TILE_N':30},{'SUB_TILE_M':32},{'TILE_K':True},{'UNKNOWN':1}):
                with self.subTest(change=change),self.assertRaises(ValueError):select((64,128,32),dict(good,**change))
            for shape,tile in (((16,256,16),(16,256,16,16,128,16)),((16,32,256),(16,32,256,16,32,128))):
                values=dict(zip(FIELDS,tile));check_execution_scope(values)
                self.assertEqual(select(shape,values),[list(tile)])

if __name__=='__main__':unittest.main()
