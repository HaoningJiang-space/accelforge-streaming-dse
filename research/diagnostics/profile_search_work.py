"""Run the frozen search-work boundary protocol in fresh serial processes."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter

from research.joint_synthesis.graph_ir import TwoMM, CostModel
from research.joint_synthesis.search_engine import SearchPolicy, TwoMMSearch
from .search_work_boundary import observe


ROOT = Path(__file__).resolve().parents[2]
SHAPES = ((2,2,2,2), (2,3,4,5), (4,4,4,4))
POLICIES = {
    'unpruned': SearchPolicy(local_pruning=False, layout_pruning=False),
    'local_only': SearchPolicy(local_pruning=True, layout_pruning=False),
    'default': SearchPolicy(),
}


def fingerprint():
    sources = [Path(__file__), Path(__file__).with_name('search_work_boundary.py'),
               Path(__file__).with_name('SEARCH_WORK_BOUNDARY_PROTOCOL.md')]
    sources += list((ROOT/'research/joint_synthesis').glob('*.py'))
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(sources)}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2)+'\n')


def worker(args):
    graph = TwoMM(*args.shape)
    model = CostModel()
    policy = POLICIES[args.policy]
    def run():
        return TwoMMSearch(graph, model, policy).solve()
    started = perf_counter(); cold = run(); cold_s = perf_counter()-started
    started = perf_counter(); warm = run(); warm_s = perf_counter()-started
    if cold != warm:
        raise AssertionError('cold/warm complete plans or statistics changed')
    observed = None
    if args.observe:
        measured, observed = observe(graph, model, policy)
        if measured != warm:
            raise AssertionError('observation changed complete plans or statistics')
        observed['exact_plans_and_statistics_equal'] = True
        observed['wall_over_warm_ratio'] = observed['instrumented_wall_s']/warm_s
    root, stats = warm
    report = dict(status='complete', shape=list(args.shape), policy=args.policy,
        policy_parameters=asdict(policy), model=asdict(model), cold_s=cold_s, warm_s=warm_s,
        cold_warm_exact_plans_and_statistics_equal=True, work=stats,
        frontier=sorted({d.vector for d in root}),
        plans_sha256=hashlib.sha256(json.dumps([asdict(d.plan)for d in root],sort_keys=True).encode()).hexdigest(),
        observation=observed, source_sha256=fingerprint())
    write(args.output, report)
    print(json.dumps(dict(shape=args.shape, policy=args.policy, cold_s=cold_s, warm_s=warm_s,
                          materialized=stats['materialized_complete_pairs'])), flush=True)


def matrix(args):
    reports = []
    args.output.mkdir(parents=True, exist_ok=True)
    sources = fingerprint()
    for repeat in range(args.repeats):
        policies = list(POLICIES) if repeat%2==0 else list(POLICIES)[::-1]
        for shape in SHAPES:
            for policy in policies:
                stem = '_'.join(map(str,shape))+f'_{policy}_{repeat+1}'
                path = args.output/(stem+'.json')
                command = [sys.executable,'-m','research.diagnostics.profile_search_work',
                           '--shape',*map(str,shape),'--policy',policy,'--output',str(path)]
                if repeat == 0:
                    command.append('--observe')
                env = dict(os.environ, PYTHONHASHSEED='0', OMP_NUM_THREADS='1',
                           OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMBA_NUM_THREADS='1')
                with (args.output/(stem+'.log')).open('w') as stream:
                    done = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
                if done.returncode:
                    raise RuntimeError(f'{stem} failed; see its log')
                result = json.loads(path.read_text())
                if result['source_sha256'] != sources:
                    raise AssertionError('sources changed during experiment')
                reports.append(result)
                write(args.output/'progress.json',dict(status='in_progress',completed=len(reports)))
                print(json.dumps(dict(trial=repeat+1, shape=shape, policy=policy, warm_s=result['warm_s'])),flush=True)
    summary = dict(status='complete',repeats=args.repeats, groups={}, source_sha256=sources,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        environment=dict(python=sys.version,platform=platform.platform(),workers=1,requested_numeric_threads=1),
        native_3mm='Historical receipts only; not rerun; different grammar/model/coverage; no cross-system speed ratio.',
        engine_core_changed=False, new_provider=False, new_search_algorithm=False,
        timing_scope='Fresh full restricted 2mm search; imports, serialization, observation and hardware binding excluded.')
    for shape in SHAPES:
        fronts = []
        for policy in POLICIES:
            rows = [r for r in reports if r['shape']==list(shape) and r['policy']==policy]
            reference = rows[0]
            if any(r['frontier']!=reference['frontier'] or r['work']!=reference['work'] or
                   r['plans_sha256']!=reference['plans_sha256'] for r in rows):
                raise AssertionError('replicates changed results/statistics')
            fronts.append(reference['frontier'])
            key = ','.join(map(str,shape))+'/'+policy
            summary['groups'][key] = dict(shape=shape, policy=policy,
                cold_samples_s=[r['cold_s']for r in rows],warm_samples_s=[r['warm_s']for r in rows],
                cold_median_s=statistics.median(r['cold_s']for r in rows),
                warm_median_s=statistics.median(r['warm_s']for r in rows),
                warm_range_s=[min(r['warm_s']for r in rows),max(r['warm_s']for r in rows)],
                work=reference['work'], frontier=reference['frontier'],
                observation=reference['observation'], all_replicates_exact_equal=True)
        if any(f!=fronts[0]for f in fronts):
            raise AssertionError('existing policies disagree about the full numerical frontier')
    summary['all_matched_policy_frontiers_equal'] = True
    write(args.output/'summary.json',summary)
    write(args.output/'progress.json',dict(status='complete',completed=len(reports)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shape',nargs=4,type=int)
    parser.add_argument('--policy',choices=POLICIES)
    parser.add_argument('--observe',action='store_true')
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.repeats<1:
        parser.error('positive repeat count required')
    if (args.shape is None)!=(args.policy is None):
        parser.error('shape and policy must be supplied together')
    worker(args) if args.shape else matrix(args)


if __name__=='__main__':
    main()
