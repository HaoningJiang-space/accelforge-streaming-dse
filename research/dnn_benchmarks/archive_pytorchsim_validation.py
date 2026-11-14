"""Archive validation evidence without executables, OCI host paths or caches."""
import argparse,hashlib,json,shutil
from pathlib import Path


def archive(run,out):
    manifest=json.loads((run/'manifest.json').read_text());out.mkdir(parents=True,exist_ok=False)
    files=[run/'manifest.json',run/'summary.json']
    for name in ('address_test/execution.log','address_test/test/result.json','address_test/test/stdout.txt'):
        if (run/name).is_file():files.append(run/name)
    for case in manifest['cases']:
        base=run/case[0]
        files += [base/name for name in ('launch_result.json','execution.log','dma_audit.json','dma_audit_error.json') if (base/name).is_file()]
        for p in (base/'result').rglob('*'):
            if not p.is_file() or 'inductor' in p.parts:continue
            if (p.name in ('result.json','hardware.yml','external_mapping.json','numerical.npz','global_var.h','tile_graph.onnx')
                or p.suffix in ('.mlir','.raw','.trace') or p.name.endswith('_tog.py')
                or (p.suffix=='.log' and p.parent.name=='logs') or p.parent.name=='attribute'):files.append(p)
    hashes={}
    for path in sorted(set(files)):
        rel=path.relative_to(run);dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
        hashes[str(rel)]=hashlib.sha256(path.read_bytes()).hexdigest()
    (out/'archive_sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    return dict(files=len(hashes),all_bytes=sum((out/f).stat().st_size for f in hashes))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(archive(a.run,a.out)))
