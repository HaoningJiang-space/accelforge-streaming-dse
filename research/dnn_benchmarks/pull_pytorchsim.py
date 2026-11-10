"""Fetch a pinned public OCI image into a user-owned OCI layout, without Docker.

Every content blob is SHA-256 verified. Only an anonymous pull token is used;
it is never persisted or printed. Extraction is delegated to pinned umoci,
which implements OCI whiteouts and rootless archive safety.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

REGISTRY='https://ghcr.io'
REPOSITORY='psal-postech/torchsim-ci'
MANIFEST='sha256:92ad4cf36ca22dae4852dae8fdc3c997e82144b0f41a36e741da14c688defd24'
UMOCI_SHA='b51c267ec394499e42c6fde47f240b7b7dba57ea49df0b5acd304378b82a3b71'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--umoci',type=Path,required=True)
    args=p.parse_args();root=args.root.resolve();root.mkdir(parents=True,exist_ok=True)
    if (root/'bundle').exists():raise FileExistsError('preserve existing runtime bundle')
    assert hashlib.sha256(args.umoci.read_bytes()).hexdigest()==UMOCI_SHA
    assert shutil.disk_usage(root).free>80*2**30,'need 80 GiB free for compressed image and runtime'
    layout=root/'oci';blobs=layout/'blobs/sha256';blobs.mkdir(parents=True,exist_ok=True)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path):
        with opener.open(REGISTRY+'/token?scope=repository:'+REPOSITORY+':pull',timeout=30) as r:
            token=json.load(r)['token']
        return opener.open(urllib.request.Request(REGISTRY+'/v2/'+REPOSITORY+'/'+path,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.manifest.v1+json'}),timeout=60)

    with request('manifests/'+MANIFEST) as response:raw=response.read()
    assert hashlib.sha256(raw).hexdigest()==MANIFEST.split(':')[1]
    manifest=json.loads(raw);(blobs/MANIFEST.split(':')[1]).write_bytes(raw)
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

    def fetch(desc):
        digest=desc['digest'].split(':')[1];path=blobs/digest
        if path.exists():
            h=hashlib.sha256()
            with path.open('rb') as f:
                for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
            assert h.hexdigest()==digest
            return
        temp=path.with_suffix('.part');h=hashlib.sha256();size=0;start=time.monotonic()
        with request('blobs/'+desc['digest']) as response,temp.open('wb') as out:
            while True:
                chunk=response.read(2**20)
                if not chunk:break
                out.write(chunk);h.update(chunk);size+=len(chunk)
        assert h.hexdigest()==digest and size==desc['size']
        temp.replace(path)
        print(json.dumps(dict(blob=digest,bytes=size,seconds=time.monotonic()-start)),flush=True)

    # Two downloads limit pressure on the shared host/network.
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(fetch,[manifest['config']]+manifest['layers']))
    (layout/'oci-layout').write_text('{"imageLayoutVersion":"1.0.0"}\n')
    index=dict(schemaVersion=2,manifests=[dict(mediaType=manifest['mediaType'],digest=MANIFEST,size=len(raw),
        annotations={'org.opencontainers.image.ref.name':'pilot'})])
    (layout/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    config=json.loads((blobs/manifest['config']['digest'].split(':')[1]).read_text())
    (root/'image_config.json').write_text(json.dumps(config,indent=2)+'\n')
    subprocess.run([str(args.umoci.resolve()),'unpack','--rootless','--image',str(layout)+':pilot',str(root/'bundle')],check=True)
    (root/'ready.json').write_text(json.dumps(dict(image_manifest=MANIFEST,umoci_sha256=UMOCI_SHA,status='unpacked'),indent=2)+'\n')


if __name__=='__main__':main()
