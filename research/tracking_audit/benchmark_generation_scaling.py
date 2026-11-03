"""Run generation K curves sequentially in fresh, single-worker processes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--counts', default='2,4,8,16')
    p.add_argument('--arches', default='nvdla,tpu_v4i')
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--phases', action='store_true')
    p.add_argument('--pareto-bytes', type=int, default=0)
    p.add_argument('--target-mode', choices=('independent', 'events'), default='independent')
    a = p.parse_args()
    counts = [int(k) for k in a.counts.split(',')]
    if a.repeats < 1 or a.pareto_bytes < 0 or any(k < 2 for k in counts):
        p.error('repeats must be positive and counts >= 2')
    cases = {'nvdla': ('64,128,256', .03125, .25),
             'tpu_v4i': ('256,512,1024', .25, 4.)}
    arches = a.arches.split(',')
    if any(arch not in cases for arch in arches):
        p.error('supported architectures: nvdla,tpu_v4i')
    a.output_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PYTHONHASHSEED': '0', 'OMP_NUM_THREADS': '1',
           'OPENBLAS_NUM_THREADS': '1', 'NUMBA_NUM_THREADS': '1'}
    benchmark = Path(__file__).with_name('benchmark_symbolic_generation.py')
    runs = []
    for arch in arches:
        params, low, high = cases[arch]
        for count in counts:
            caps = [low * (high / low)**(i / (count - 1)) for i in range(count)]
            caps[-1] = high
            output = a.output_dir / f'{arch}-k{count}.json'
            cmd = [sys.executable, str(benchmark), '--repo', str(a.repo), '--arch', arch,
                   '--params', params, '--caps', ','.join(map(repr, caps)), '--factors', '1',
                   '--repeats', str(a.repeats), '--output', str(output),
                   '--pareto-bytes', str(a.pareto_bytes), '--target-mode', a.target_mode]
            if a.phases:
                cmd.append('--phases')
            print('START', arch, count, flush=True)
            with output.with_suffix('.log').open('w') as log:
                completed = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
            runs.append(dict(arch=arch, k=count, returncode=completed.returncode, output=str(output)))
            (a.output_dir / 'execution.json').write_text(json.dumps(runs, indent=2))
            print('DONE', json.dumps(runs[-1]), flush=True)
            if completed.returncode:
                return completed.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
