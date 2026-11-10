"""One isolated GEMM import check, not an optimized graph-mapping benchmark.

Run inside the pinned PyTorchSim runtime. The caller supplies a fresh output
directory and a process timeout. No latency/energy optimality is inferred.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--mode',choices=('heuristic','autotune','external'),required=True)
    p.add_argument('--size',type=int,default=32)
    p.add_argument('--tile',type=int,default=16)
    a=p.parse_args();src=a.source.resolve();out=a.out.resolve()
    out.mkdir(parents=True,exist_ok=False)
    if a.size<=0 or a.tile<=0 or a.size%a.tile:p.error('positive divisible dimensions required')
    import yaml
    cfg=yaml.safe_load((src/'tutorial/session1/togsim_configs/togsim_config.yml').read_text())
    cfg.update(pytorchsim_functional_mode=1,pytorchsim_timing_mode=1,
               codegen_mapping_strategy='external-then-heuristic' if a.mode=='external' else a.mode,
               codegen_compiler_optimization='none')
    cfg['ramulator_config_path']=str(src/'configs/ramulator2_configs/HBM2_TPUv3.yaml')
    requested=[a.tile]*6
    mapping={f'{a.size}_{a.size}_{a.size}':dict(zip(
        ('TILE_M','TILE_N','TILE_K','SUB_TILE_M','SUB_TILE_N','SUB_TILE_K'),requested))}
    write(out/'external_mapping.json',mapping)
    cfg['codegen_external_mapping_file']=str(out/'external_mapping.json') if a.mode=='external' else ''
    (out/'hardware.yml').write_text(yaml.safe_dump(cfg))
    os.environ.update(TORCHSIM_DIR=str(src),TOGSIM_CONFIG=str(out/'hardware.yml'),
        TORCHSIM_DUMP_PATH=str(out/'compiler'),TORCHSIM_LOG_PATH=str(out/'logs'),
        TORCHINDUCTOR_CACHE_DIR=str(out/'inductor'),TORCHSIM_DUMP_MLIR_IR='1',
        OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    revision=subprocess.run(['git','-C',str(src),'rev-parse','HEAD'],capture_output=True,text=True)
    files=('PyTorchSimFrontend/mlir/mlir_gemm_template.py','PyTorchSimFrontend/extension_config.py',
           'AsmParser/tog_generator.py','TOGSim/src/TileGraphParser.cc','TOGSim/build/bin/Simulator')
    record=dict(status='running',mode=a.mode,size=a.size,dtype='float32',macs=a.size**3,
        source_commit=revision.stdout.strip() if revision.returncode==0 else None,
        file_sha256={f:hashlib.sha256((src/f).read_bytes()).hexdigest() for f in files if (src/f).is_file()},
        requested_tile=requested if a.mode=='external' else None,
        candidate_tiles_observed=[],rendered_tiles_observed=[],
        dma_byte_audit='pending; no traffic equality claim',
        scope='standalone GEMM import smoke; external tiles are manual controls, not a solver-quality result')
    write(out/'result.json',record)
    try:
        import torch
        from PyTorchSimFrontend.mlir.mlir_gemm_template import MLIRGemmTemplate
        old_select=MLIRGemmTemplate.select_tile
        old_render=MLIRGemmTemplate.render
        def select(self,*args,**kw):
            choices=old_select(self,*args,**kw)
            values=[[int(v) for v in row] for row in choices]
            record['candidate_tiles_observed'].append(values)
            if a.mode=='external' and values!=[requested]:
                raise ValueError('external mapping selection changed or fell back')
            return choices
        def render(self,*args,**kw):
            result=old_render(self,*args,**kw)
            if isinstance(result,str):
                found={k:int(v) for k,v in re.findall(r'//\s*(TILE_[MNK]|SUB_TILE_[MNK])\s*=\s*(\d+)',result)}
                if found:record['rendered_tiles_observed'].append(found)
                if a.mode=='external' and any(found.get(k)!=a.tile for k in ('TILE_M','TILE_N','TILE_K')):
                    raise ValueError('rendered GEMM tile differs from request')
            return result
        MLIRGemmTemplate.select_tile=select;MLIRGemmTemplate.render=render
        torch.set_num_threads(1);torch.manual_seed(0)
        x=torch.randn(a.size,a.size,dtype=torch.float32)
        w=torch.randn(a.size,a.size,dtype=torch.float32)
        reference=x@w
        def mm(x,w):return x@w
        start=time.monotonic()
        actual=torch.compile(dynamic=False)(mm)(x.to('npu:0'),w.to('npu:0')).cpu()
        record.update(compile_and_execute_seconds=time.monotonic()-start,torch_version=torch.__version__,
            max_abs_error=float((actual-reference).abs().max()),
            numerical_equal=bool(torch.allclose(actual,reference,rtol=1e-4,atol=1e-4)))
        if not record['numerical_equal']:raise ValueError('functional output mismatch')
        if a.mode=='external' and (not record['candidate_tiles_observed'] or not record['rendered_tiles_observed']):
            raise ValueError('missing evidence of external selection and rendering')
        record['status']='functional_import_pass; DMA ledger still pending'
    except Exception as e:
        record.update(status='failed',error=f'{type(e).__name__}: {e}')
        raise
    finally:
        write(out/'result.json',record)


if __name__=='__main__':main()
