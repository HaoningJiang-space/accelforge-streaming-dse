"""Fetch a pinned public OCI image into a user-owned OCI layout, without Docker.

Every content blob is SHA-256 verified. Only an anonymous pull token is used;
it is never persisted or printed. Extraction is delegated to pinned umoci,
which implements OCI whiteouts and rootless archive safety.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
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
    p.add_argument('--umoci',type=Path)
    p.add_argument('--download-only',action='store_true',help='prepare verified OCI layout without extraction')
    p.add_argument('--range-mib',type=int,default=0,help='optional resumable HTTP range size; zero streams blobs')
    p.add_argument('--range-workers',type=int,default=4,choices=range(1,9))
    args=p.parse_args();root=args.root.resolve();root.mkdir(parents=True,exist_ok=True)
    if not 0<=args.range_mib<=32:p.error('--range-mib must be between 0 and 32')
    if (root/'bundle').exists():raise FileExistsError('preserve existing runtime bundle')
    if not args.download_only:
        if args.umoci is None:p.error('--umoci is required for extraction')
        assert hashlib.sha256(args.umoci.read_bytes()).hexdigest()==UMOCI_SHA
    needed=12 if args.download_only else 80
    assert shutil.disk_usage(root).free>needed*2**30,f'need {needed} GiB free'
    layout=root/'oci';blobs=layout/'blobs/sha256';blobs.mkdir(parents=True,exist_ok=True)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path,extra_headers=None):
        with opener.open(REGISTRY+'/token?scope=repository:'+REPOSITORY+':pull',timeout=30) as r:
            token=json.load(r)['token']
        return opener.open(urllib.request.Request(REGISTRY+'/v2/'+REPOSITORY+'/'+path,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.manifest.v1+json',**(extra_headers or {})}),timeout=60)

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
        if args.range_mib and desc['size']>args.range_mib*2**20:
            step=args.range_mib*2**20;progress=path.with_suffix('.ranges.json')
            done=set()
            if progress.exists() and temp.exists():
                saved=json.loads(progress.read_text())
                if saved['step']==step and saved['size']==desc['size']:done=set(saved['done'])
            fd=os.open(temp,os.O_RDWR|os.O_CREAT,0o600);os.ftruncate(fd,desc['size'])
            def segment(offset):
                end=min(offset+step,desc['size'])-1
                for attempt in range(3):
                    try:
                        with request('blobs/'+desc['digest'],{'Range':f'bytes={offset}-{end}'}) as response:
                            assert response.status==206 and response.headers.get('Content-Range')==f'bytes {offset}-{end}/{desc["size"]}'
                            data=response.read();assert len(data)==end-offset+1
                        n=0
                        while n<len(data):n+=os.pwrite(fd,data[n:],offset+n)
                        return offset
                    except Exception:
                        if attempt==2:raise
                        time.sleep(2**attempt)
            try:
                with ThreadPoolExecutor(max_workers=args.range_workers) as pool:
                    for offset in pool.map(segment,(x for x in range(0,desc['size'],step) if x not in done)):
                        done.add(offset)
                        pending=progress.with_suffix('.tmp')
                        pending.write_text(json.dumps(dict(step=step,size=desc['size'],done=sorted(done))))
                        pending.replace(progress)
                os.fsync(fd)
            finally:os.close(fd)
            with temp.open('rb') as out:
                for chunk in iter(lambda:out.read(2**20),b''):h.update(chunk);size+=len(chunk)
        else:
            with request('blobs/'+desc['digest']) as response,temp.open('wb') as out:
                while True:
                    chunk=response.read(2**20)
                    if not chunk:break
                    out.write(chunk);h.update(chunk);size+=len(chunk)
        assert h.hexdigest()==digest and size==desc['size']
        temp.replace(path)
        path.with_suffix('.ranges.json').unlink(missing_ok=True)
        print(json.dumps(dict(blob=digest,bytes=size,seconds=time.monotonic()-start)),flush=True)

    # At most two streamed blobs, or one range pool with its declared limit.
    with ThreadPoolExecutor(max_workers=1 if args.range_mib else 2) as pool:
        list(pool.map(fetch,[manifest['config']]+manifest['layers']))
    (layout/'oci-layout').write_text('{"imageLayoutVersion":"1.0.0"}\n')
    index=dict(schemaVersion=2,manifests=[dict(mediaType=manifest['mediaType'],digest=MANIFEST,size=len(raw),
        annotations={'org.opencontainers.image.ref.name':'pilot'})])
    (layout/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    config=json.loads((blobs/manifest['config']['digest'].split(':')[1]).read_text())
    (root/'image_config.json').write_text(json.dumps(config,indent=2)+'\n')
    if args.download_only:
        (root/'downloaded.json').write_text(json.dumps(dict(image_manifest=MANIFEST,status='verified OCI layout'),indent=2)+'\n')
        return
    subprocess.run([str(args.umoci.resolve()),'unpack','--rootless','--image',str(layout)+':pilot',str(root/'bundle')],check=True)
    (root/'ready.json').write_text(json.dumps(dict(image_manifest=MANIFEST,umoci_sha256=UMOCI_SHA,status='unpacked'),indent=2)+'\n')


if __name__=='__main__':main()
