"""Windows single-worker watchdog; incomplete cases never become reference data."""
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import time


def memory(proc):
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[
            (name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize',
            'QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    api=ctypes.WinDLL('psapi',use_last_error=True)
    api.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    api.GetProcessMemoryInfo.restype=wintypes.BOOL
    value=Counters()
    value.cb=ctypes.sizeof(value)
    if not api.GetProcessMemoryInfo(wintypes.HANDLE(int(proc._handle)),ctypes.byref(value),value.cb):
        if proc.poll() is not None:
            return 0
        raise ctypes.WinError(ctypes.get_last_error())
    return value.PeakWorkingSetSize


def main():
    if sys.platform!='win32':
        raise SystemExit('Use a POSIX process-group/cgroup supervisor on other hosts.')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cases',nargs='+')
    parser.add_argument('--seconds',type=float,default=240)
    parser.add_argument('--gib',type=float,default=2)
    parser.add_argument('--directory',type=Path,default=Path('research/structure_prediction/results'))
    args=parser.parse_args()
    if args.seconds<=0 or args.gib<=0:
        parser.error('positive limits required')
    args.directory.mkdir(parents=True,exist_ok=True)
    for name in args.cases:
        if not name.replace('_','').isalnum():
            raise ValueError('case identifiers must be alphanumeric with underscores')
        output=args.directory/f'{name}.json'
        # Prevent an old complete report from being mistaken for a fresh failed run.
        if output.exists():
            raise FileExistsError(output)
        start=time.perf_counter()
        peak=0
        status='running'
        command=[sys.executable,'-m','research.structure_prediction.experiment',name,'--output',str(output)]
        with (args.directory/f'{name}.log').open('w',encoding='utf-8') as log:
            proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            try:
                while proc.poll() is None:
                    peak=max(peak,memory(proc))
                    if peak>args.gib*2**30:
                        status='memory_limit'
                    elif time.perf_counter()-start>args.seconds:
                        status='time_limit'
                    if status!='running':
                        proc.kill()
                        break
                    time.sleep(.2)
                proc.wait()
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        phase=json.loads(output.read_text()).get('phase') if output.exists() else None
        if status=='running':
            status='complete' if proc.returncode==0 and phase=='complete' else 'failed'
        record=dict(case=name,status=status,worker_phase=phase,returncode=proc.returncode,
                    wall_seconds=time.perf_counter()-start,peak_working_set_gib=peak/2**30,
                    limits=dict(seconds=args.seconds,gib=args.gib,poll_seconds=.2))
        (args.directory/f'{name}_status.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        print(record,flush=True)


if __name__=='__main__':
    main()
