"""Copy interface evidence without OCI host paths, caches or executables."""
import argparse,hashlib,json,shutil
from pathlib import Path


def archive(root,out):
    out.mkdir(parents=True,exist_ok=False);hashes={}
    names={'plan.json','summary.json','requests.json','request.json','evaluation.json','launch_result.json','dma_audit.json','dma_audit_error.json','result.json','hardware.yml','external_mapping.json','numerical.npz','global_var.h','tile_graph.onnx','allocation_manifest.json','allocation_symbols.txt'}
    for path in sorted(root.rglob('*')):
        rel=path.relative_to(root)
        if not path.is_file() or any(x in rel.parts for x in ('oci','inductor','__pycache__','m5out','.torchinductor')):continue
        if not (path.name in names or path.name.endswith(('.request.json','.stats.json','_tog.py')) or path.suffix in ('.mlir','.s','.raw','.trace','.log') or path.parent.name=='attribute'):continue
        dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest);hashes[str(rel)]=hashlib.sha256(path.read_bytes()).hexdigest()
    (out/'archive_sha256.json').write_text(json.dumps(hashes,indent=2)+'\n');return dict(files=len(hashes))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(archive(a.run,a.out)))
