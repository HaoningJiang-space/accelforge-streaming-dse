"""Follow-up matrix for analytic witnesses composed with existing reductions."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from . import bench_composition as base
from .artifacts import verify_sources

CASES = ('two_stage_join', 'asymmetric_join', 'mixed_join', 'ffn4', 'ancestor8')
ARMS = ('prefix', 'prefix_p', 'prefix_i', 'prefix_r', 'analytic', 'analytic_none',
        'analytic_p', 'analytic_i', 'analytic_r', 'analytic_pi', 'analytic_pr',
        'analytic_ir', 'analytic_pir')
SOURCES = tuple(sorted(set(base.SOURCES) | {
    'research/dag_mapping/bench_analytic_composition.py',
    'research/index_coupling/test_analytic_composition.py'}))


def run_arm(name, arm, profile=False):
    if arm.startswith('analytic_'):
        suffix = arm.partition('_')[2]
        flags = {} if suffix == 'none' else {base.FLAGS[k]: True for k in suffix}
        return base.run_arm(name, 'analytic', profile, analytic_flags=flags)
    return base.run_arm(name, arm, profile)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('run', 'worker'))
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--case', choices=CASES)
    p.add_argument('--arm', choices=ARMS+('reference',), default='analytic_p')
    p.add_argument('--mode', choices=('audit', 'time', 'work'), default='audit')
    p.add_argument('--reference', type=Path)
    args = p.parse_args()
    if args.command == 'worker':
        return base.worker(args, runner=run_arm, sources=SOURCES)
    if platform.system() != 'Linux':
        raise ValueError('fresh Linux processes required')
    verify_sources(args.revision, SOURCES)
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = dict(revision=args.revision, cases=CASES, arms=ARMS, rounds=3,
                    worker_seconds=180, memory_gib=4, hash_seed='0',
                    old_arms=('prefix', 'prefix_p', 'prefix_i', 'prefix_r', 'analytic'),
                    new_arms=tuple(a for a in ARMS if a.startswith('analytic_')),
                    policy='exact unlimited v2 default costs; halving; certified order representatives',
                    primary_comparison='analytic plus precheck versus old analytic on ffn4; descriptive fixed matrix')
    (args.out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    def launch(name, arm, mode, tag):
        cmd = [sys.executable, '-m', 'research.dag_mapping.bench_analytic_composition', 'worker',
               '--out', str(args.out/f'{name}_{arm}_{tag}.json'), '--revision', args.revision,
               '--case', name, '--arm', arm, '--mode', mode]
        if arm != 'reference':
            cmd += ['--reference', str(args.out/f'{name}_reference_audit.json')]
        return subprocess.run(cmd, env=dict(os.environ, PYTHONHASHSEED='0')).returncode
    for name in CASES:
        if launch(name, 'reference', 'audit', 'audit'):
            return 1
        for arm in ARMS:
            if launch(name, arm, 'audit', 'audit'):
                return 1
    failed = False
    for turn in range(3):
        arms = ARMS[turn:] + ARMS[:turn]
        for name in CASES:
            for arm in arms:
                failed |= bool(launch(name, arm, 'time', str(turn)))
    for name in CASES:
        for arm in ARMS:
            failed |= bool(launch(name, arm, 'work', 'work'))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
