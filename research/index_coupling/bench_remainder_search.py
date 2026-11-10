"""Serial, fresh-process four-arm remainder comparisons with complete replays.

Three unprofiled timing rounds and one separately profiled round by default.
The arm order rotates between rounds. Every attempt is retained; reruns skip
recorded attempts, including failures. Use a new directory for a new attempt.
Requires psutil for parent-side RSS enforcement (also on macOS).
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import statistics
import subprocess
import sys
import time

from .graph.curve import curve
from .graph.model import fork
from .graph.stacks import ffn_stack, attention_stack
from .run_ancestor_width import control
from .simulate_nest import simulate


CASES = {
    'ffn4': (ffn_stack, (4,)),
    'attention4': (attention_stack, (4,)),
    'ffn_train1': (ffn_stack, (1, 2, 2, 2, True)),
    'ancestor8': (control, (8,)),
    'fork6_same': (fork, (2, 2, 2, 2, 'kkkkkk')),
    'fork6_mixed': (fork, (2, 2, 2, 2, 'kkkiii')),
    'p19_same': (fork, (8, 4, 8, 2, 'kkkkkk')),
    'p19_mixed': (fork, (8, 4, 8, 2, 'kkkiii')),
}
ARMS = {'baseline': (False, False), 'precheck': (False, True),
        'remainder': (True, False), 'both': (True, True)}


def atomic_json(path, obj):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, indent=2) + '\n')
    tmp.replace(path)


def sources():
    root = Path(__file__).parent
    names = ('graph/curve.py', 'graph/remainder.py', 'graph/model.py',
             'graph/stacks.py', 'graph/span_names.py', 'simulate_nest.py',
             'run_ancestor_width.py', 'bench_remainder_search.py')
    return {n: hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}


def worker(args):
    factory, shape = CASES[args.case]
    graph = factory(*shape)
    canonical, precheck = ARMS[args.arm]
    options = dict(partitions='dp', witness=True, canonical_remainders=canonical,
                   prune_infeasible_groups=precheck, independent_ops=args.independent_ops)
    stats = {} if args.profile else None
    out = dict(case=args.case, arm=args.arm, shape=shape, n_ops=len(graph.ops),
               options=options, profile=args.profile, stats=stats, status='running', phase='search',
               python=platform.python_version(), system=platform.system(), machine=platform.machine(),
               hash_seed=os.environ.get('PYTHONHASHSEED'), source_sha256=sources(),
               started_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(args.out, out)
    if sys.platform == 'linux':
        cap = int(args.mem_gib * 2**30)
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))

    def timeout(*_):
        raise TimeoutError('search and replay time budget')

    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, args.seconds)
    begin = time.perf_counter()
    try:
        points = curve(graph, stats=stats, **options)
        out.update(search_seconds=time.perf_counter()-begin, phase='replay',
                   points=[p[:2] for p in points], witnesses=points, replays=[])
        atomic_json(args.out, out)
        replay_start = time.perf_counter()
        for c, q, witness in points:
            actual = simulate(graph, witness)
            out['replays'].append(dict(expected=[c, q], actual=actual,
                exact=actual['valid'] and (actual['peak'], actual['traffic']) == (c, q)))
        out.update(replay_seconds=time.perf_counter()-replay_start, phase='finished',
                   status='complete' if all(r['exact'] for r in out['replays']) else 'invalid')
    except TimeoutError:
        out['status'] = 'timeout'
    except MemoryError:
        out['status'] = 'memory'
    except Exception as exc:
        out.update(status='error', error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out.update(seconds=time.perf_counter()-begin,
               peak_rss_bytes=rss if sys.platform == 'darwin' else rss*1024)
    atomic_json(args.out, out)


def run(args, case, arm, profile, path):
    import psutil
    if path.exists():
        return json.loads(path.read_text())
    command = [sys.executable, '-m', __spec__.name, '--worker', '--case', case, '--arm', arm,
               '--out', str(path), '--seconds', str(args.seconds), '--mem-gib', str(args.mem_gib)]
    if profile:
        command.append('--profile')
    if args.independent_ops:
        command.append('--independent-ops')
    with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                          text=True, env=dict(os.environ, PYTHONHASHSEED='0')) as child:
        begin, sampled_rss, failure = time.monotonic(), 0, None
        proc = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                sampled_rss = max(sampled_rss, proc.memory_info().rss)
            except psutil.NoSuchProcess:
                break
            if sampled_rss > args.mem_gib * 2**30:
                failure = 'rss_limit'
            elif time.monotonic()-begin > args.seconds+10:
                failure = 'hard_timeout'
            if failure:
                child.kill()
                break
            time.sleep(.1)
        _, stderr = child.communicate()
    out = json.loads(path.read_text()) if path.exists() else dict(case=case, arm=arm, profile=profile)
    if failure or out.get('status') in (None, 'running'):
        out.update(status=failure or 'crashed', exitcode=child.returncode, stderr=stderr[-2000:])
    out.update(sampled_peak_rss_bytes=sampled_rss)
    atomic_json(path, out)
    return out


def summarize(args, outputs):
    comparisons = {}
    for case in args.cases:
        rows = [o for o in outputs if o['case'] == case]
        complete = [o for o in rows if o['status'] == 'complete']
        timings = {arm: [o['search_seconds'] for o in complete if o['arm']==arm and not o['profile']]
                   for arm in ARMS}
        medians = {arm: statistics.median(ts) if len(ts)==args.repeats else None for arm,ts in timings.items()}
        comparisons[case] = dict(completed=len(complete), requested=len(rows),
            full_matrix_equal=(all(o['points']==complete[0]['points'] for o in complete)
                               if len(complete)==len(rows) else None),
            completed_equal=(all(o['points']==complete[0]['points'] for o in complete)
                             if len(complete)>1 else None),
            exact_replays=sum(len(o['replays']) for o in complete),
            median_search_seconds=medians,
            baseline_over_arm={a:medians['baseline']/t if medians['baseline'] and t else None
                               for a,t in medians.items()},
            profile={o['arm']:dict(stats=o['stats'],peak_rss_bytes=o.get('peak_rss_bytes'))
                     for o in complete if o['profile']})
    return dict(comparisons=comparisons, statuses={o['attempt']:o['status'] for o in outputs})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cases', nargs='+', choices=CASES, default=['ffn4','attention4','ffn_train1','ancestor8'])
    p.add_argument('--seconds', type=float, default=40)
    p.add_argument('--mem-gib', type=float, default=1)
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--independent-ops', action='store_true')
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--case', choices=CASES, help=argparse.SUPPRESS)
    p.add_argument('--arm', choices=ARMS, help=argparse.SUPPRESS)
    p.add_argument('--profile', action='store_true', help=argparse.SUPPRESS)
    args = p.parse_args()
    if min(args.seconds,args.mem_gib,args.repeats) <= 0:
        p.error('positive budgets and repeats required')
    if args.worker:
        worker(args)
        return
    args.out.mkdir(parents=True, exist_ok=True)
    config = dict(source_sha256=sources(),cases=args.cases,repeats=args.repeats,
                  seconds=args.seconds,mem_gib=args.mem_gib,independent_ops=args.independent_ops,
                  arms=ARMS,hash_seed='0',timing='serial fresh processes; rotate arms; separate profile',
                  revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
    manifest = args.out/'manifest.json'
    if manifest.exists() and json.loads(manifest.read_text()) != json.loads(json.dumps(config)):
        p.error('output source/config differs; preserve old attempt and use a new directory')
    atomic_json(manifest,config)
    outputs = []
    for r in range(args.repeats+1):
        arms = list(ARMS)
        arms = arms[r%len(arms):]+arms[:r%len(arms)]
        for case in args.cases:
            for arm in arms:
                attempt = f'{case}__{arm}__'+('profile' if r==args.repeats else f'r{r}')
                out = run(args,case,arm,r==args.repeats,args.out/f'{attempt}.json')
                out['attempt'] = attempt
                outputs.append(out)
                print(json.dumps({k:out.get(k) for k in ('attempt','status','search_seconds','peak_rss_bytes')}),flush=True)
                atomic_json(args.out/'summary.json',summarize(args,outputs))
    summary = summarize(args,outputs)
    bad = any(o['status'] in ('error','invalid') for o in outputs)
    mismatch = any(c['completed_equal'] is False for c in summary['comparisons'].values())
    sys.exit(1 if bad or mismatch else 2 if any(o['status']!='complete' for o in outputs) else 0)


if __name__ == '__main__':
    main()
