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
from .mapping_contract import FIELDS,canonical_request,check_serialized_request,check_execution_scope,template_ledger


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--mode',choices=('heuristic','autotune','external'),required=True)
    p.add_argument('--shape',type=int,nargs=3,default=(64,128,32),metavar=('M','N','K'))
    p.add_argument('--tile',type=int,nargs=6,default=(16,32,8,8,32,8))
    p.add_argument('--diagnostic-allow-n-split',action='store_true')
    p.add_argument('--backend-lock',type=Path,default=Path(__file__).with_name('backend_lock.json'))
    p.add_argument('--fixed-timing-addresses',action='store_true')
    a=p.parse_args();src=a.source.resolve();out=a.out.resolve()
    named=dict(zip(FIELDS,a.tile));mapping=canonical_request(a.shape,named)
    if a.mode=='external':check_execution_scope(named,a.diagnostic_allow_n_split)
    m,n,k=a.shape;requested=list(a.tile)
    out.mkdir(parents=True,exist_ok=False)
    import yaml
    cfg=yaml.safe_load((src/'tutorial/session1/togsim_configs/togsim_config.yml').read_text())
    cfg.update(pytorchsim_functional_mode=1,pytorchsim_timing_mode=1,
               codegen_mapping_strategy='external-then-heuristic' if a.mode=='external' else a.mode,
               codegen_compiler_optimization='none')
    cfg['ramulator_config_path']=str(src/'configs/ramulator2_configs/HBM2_TPUv3.yaml')
    write(out/'external_mapping.json',mapping)
    check_serialized_request(json.loads((out/'external_mapping.json').read_text()),a.shape,named)
    cfg['codegen_external_mapping_file']=str(out/'external_mapping.json') if a.mode=='external' else ''
    (out/'hardware.yml').write_text(yaml.safe_dump(cfg))
    os.environ.update(TORCHSIM_DIR=str(src),TOGSIM_CONFIG=str(out/'hardware.yml'),
        TORCHSIM_DUMP_PATH=str(out/'compiler'),TORCHSIM_LOG_PATH=str(out/'logs'),
        TORCHINDUCTOR_CACHE_DIR=str(out/'inductor'),TORCHSIM_DUMP_MLIR_IR='1',
        OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    revision=subprocess.run(['git','-C',str(src),'rev-parse','HEAD'],capture_output=True,text=True)
    files=('PyTorchSimFrontend/mlir/mlir_gemm_template.py','PyTorchSimFrontend/extension_config.py',
           'AsmParser/tog_generator.py','TOGSim/src/TileGraphParser.cc','TOGSim/build/bin/Simulator')
    record=dict(status='running',mode=a.mode,shape=a.shape,dtype='float32',macs=m*n*k,
        source_commit=revision.stdout.strip() if revision.returncode==0 else None,
        file_sha256={f:hashlib.sha256((src/f).read_bytes()).hexdigest() for f in files if (src/f).is_file()},
        requested_tile=requested if a.mode=='external' else None,
        candidate_tiles_observed=[],rendered_tiles_observed=[],
        source_template_ledger=template_ledger(a.shape,requested[:3]) if a.mode=='external' else None,
        independent_contract_audit='7e03ab3b',
        dma_byte_audit='pending; no traffic equality claim',
        timing_accepted=False,timing_rejection='Pinned backend byte-address mismatch; see PYTORCHSIM_RESULTS.md',
        scope='standalone GEMM import smoke; external tiles are manual controls, not a solver-quality result')
    write(out/'result.json',record)
    try:
        lock=json.loads(a.backend_lock.read_text())
        record['backend_lock_sha256']=hashlib.sha256(a.backend_lock.read_bytes()).hexdigest()
        if lock.get('patches'):
            record['timing_rejection']='Pending independent compiled-DMA ledger and functional verification'
        for name,sha in lock.get('runtime_binary_hashes',{}).items():
            path=Path('/')/name
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
                raise ValueError('runtime binary differs from lock: '+name)
        if record['source_commit']!=lock['runtime_git_commit']:
            raise ValueError('runtime commit differs from verified image')
        for name,sha in lock['audited_source_sha256'].items():
            if hashlib.sha256((src/name).read_bytes()).hexdigest()!=sha:
                raise ValueError('runtime differs from audited source: '+name)
        record['audited_source_commit']=lock['source_commit']
        record['source_difference']=lock['runtime_code_matches_submodule_except']
        import torch
        if a.fixed_timing_addresses:
            from Simulator.simulator import TOGSimulator
            original_attributes=TOGSimulator.write_kernel_attribute_file
            record['timing_address_layouts']=[]
            def fixed_attributes(attribute_dir,inputs,alloc_pool=None):
                if any(t.numel()*t.element_size()>=0x10000000 for t in inputs):
                    raise ValueError('pilot fixed-address slots cannot fit tensor')
                if len({t.data_ptr() for t in inputs})!=len(inputs):
                    raise ValueError('pilot requires nonaliasing input/output buffers')
                path=original_attributes(attribute_dir,inputs,alloc_pool)
                attrs=yaml.safe_load(Path(path).read_text())
                attrs['address_info']={f'arg{i}':0x10000000*(i+1) for i in range(len(inputs))}
                Path(path).write_text(yaml.safe_dump(attrs))
                record['timing_address_layouts'].append(dict(addresses=attrs['address_info'],bytes=[t.numel()*t.element_size() for t in inputs]))
                return path
            TOGSimulator.write_kernel_attribute_file=staticmethod(fixed_attributes)
        from PyTorchSimFrontend.mlir.mlir_gemm_template import MLIRGemmTemplate
        old_select=MLIRGemmTemplate.select_tile
        old_render=MLIRGemmTemplate.render
        def select(self,*args,**kw):
            if a.mode=='external':
                if tuple(int(x) for x in args[1:4])!=tuple(a.shape):raise ValueError('unexpected GEMM shape')
                check_serialized_request(json.loads((out/'external_mapping.json').read_text()),a.shape,named)
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
                if a.mode=='external' and any(found.get(k)!=named[k] for k in FIELDS[:5]):
                    raise ValueError('rendered GEMM tile differs from request')
            return result
        MLIRGemmTemplate.select_tile=select;MLIRGemmTemplate.render=render
        torch.set_num_threads(1);torch.manual_seed(0)
        x=torch.randn(m,k,dtype=torch.float32)
        w=torch.randn(k,n,dtype=torch.float32)
        reference=x@w
        def mm(x,w):return x@w
        start=time.monotonic()
        actual=torch.compile(dynamic=False)(mm)(x.to('npu:0'),w.to('npu:0')).cpu()
        import numpy as np
        np.savez_compressed(out/'numerical.npz',x=x.numpy(),w=w.numpy(),actual=actual.numpy(),reference=reference.numpy())
        record.update(compile_and_execute_seconds=time.monotonic()-start,torch_version=torch.__version__,
            max_abs_error=float((actual-reference).abs().max()),
            wrong_elements=int((~torch.isclose(actual,reference,rtol=1e-4,atol=1e-4)).sum()),
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
