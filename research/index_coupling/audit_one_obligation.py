"""Bounded coverage audit of scalar retention and a two-live normal form.

Exploratory exact-response checks, not a frozen prediction or speed benchmark.
Production solver, its cache keys, and previous archived sources stay intact.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import time

from research.index_coupling.audit_residency_states import instrumented_curve
from research.index_coupling.free_retention import retention_candidates, make_free_retention_curve
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import fork
from research.index_coupling.one_obligation import two_live_response
from research.index_coupling.scalar_bridge import bridge_response
from research.index_coupling.streamed_bridge import streamed_response, make_streamed_bridge_curve
from research.index_coupling.simulate_nest import simulate
from research.index_coupling.test_free_retention import conditional_cases
from research.index_coupling.test_one_obligation import cases, frame
from research.index_coupling.test_streamed_bridge import framed_streamed_witness

HERE = Path(__file__).parent
FRESH = ((1,2,4,1,'kkkkkk'), (1,2,4,1,'kkkiii'), (4,2,1,1,'iiiiii'),
         (1,1,4,2,'kkk'), (4,1,1,2,'kii'), (1,1,4,1,'kkk'),
         (4,2,2,2,'kkk'), (4,2,4,2,'kki'), (4,2,2,2,'kkkk'), (4,2,4,2,'kkii'))


def hashes():
    names = ('free_retention.py','one_obligation.py','test_free_retention.py','test_one_obligation.py',
             'audit_one_obligation.py','scalar_bridge.py','streamed_bridge.py','test_scalar_bridge.py',
             'test_streamed_bridge.py','audit_residency_states.py','graph/curve.py','graph/model.py',
             'graph/span_names.py','simulate_nest.py')
    return {n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in names}


def write_gzip(path, value):
    with gzip.open(path,'wt') as stream:
        json.dump(value,stream,separators=(',',':'))


def observer(graph):
    counts, records = Counter(), []
    def check(state):
        counts['all_states'] += 1
        if state['stage']!='solve' or state['constrained'] or len(state['ops'])<2:
            return
        args = (graph,state['ops'],state['ext'],state['external'],state['owned'],sorted(graph.sizes))
        rows = list(retention_candidates(*args))
        counts['one_obligation_axes'] += len(rows)
        counts['states_with_one_obligation_axis'] += bool(rows)
        for row in rows:
            counts['reason:'+row['reason']] += 1
            counts['scalar_obligation_axes'] += row['size']==1
            counts['scalar_and_slot_drop_axes'] += row['size']==1 and row['child_bound']==row['d']-1
            counts['incidence_criterion_wrong'] += row['all_bottlenecks_access'] != (row['child_bound']==row['d']-1)
        qualified = [r for r in rows if r['eligible']]
        if qualified:
            old = bridge_response(*args)
            if old is None:
                old = streamed_response(*args)
            expected = ((qualified[0]['d'],0),)
            exact = tuple(map(tuple,state['points']))==expected
            counts['free_retention_states'] += 1
            counts['free_retention_wrong'] += not exact
            counts['already_covered'] += old is not None
            counts['incremental_states'] += old is None
            records.append(dict(kind='free_retention',state=state,certificates=qualified,
                                already_covered=old is not None,exact=exact))
        predicted = two_live_response(*args)
        if predicted is not None:
            exact = tuple(map(tuple,state['points']))==tuple(p[:2] for p in predicted)
            counts['two_live_states'] += 1
            counts['two_live_wrong'] += not exact
            records.append(dict(kind='two_live',state=state,predicted=predicted,exact=exact))
    return counts,records,check


def archived(name, out):
    directory = HERE/'results/residency_states'/name
    run = json.loads((directory/'run.json').read_text())
    if run['status']!='complete' or not run['cache_count_matches']:
        raise ValueError('complete census required')
    counts,records,check = observer(fork(*run['graph_args']))
    raw = directory/'states.jsonl.gz'
    with gzip.open(raw,'rt') as stream:
        for line in stream:
            check(json.loads(line))
    if counts['all_states']!=run['completed_states']:
        raise ValueError('incomplete raw state stream')
    write_gzip(out/f'{name}.json.gz',records)
    return dict(case=name,shape=run['graph_args'],counts=dict(counts),
                raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),source_sha256=run['source_sha256'])


def fresh(shape, out):
    graph = fork(*shape)
    counts,records,check = observer(graph)
    variants = {}
    for name,compute in (('baseline',instrumented_curve(check)),
                         ('existing_bridges',make_streamed_bridge_curve()),
                         ('free_retention',make_free_retention_curve())):
        stats = {}
        points = compute(graph,partitions='dp',witness=True,stats=stats)
        replays = []
        for c,q,w in points:
            actual = simulate(graph,w)
            replays.append(dict(exact=actual['valid'] and (actual['peak'],actual['traffic'])==(c,q),
                                expected=[c,q],actual=[actual['peak'],actual['traffic']]))
        variants[name] = dict(points=[list(p[:2]) for p in points],witnesses=points,replays=replays,stats=stats)
    count_matches = counts['all_states']==sum(variants['baseline']['stats'][k]['currsize'] for k in ('solve_cache','group_cache'))
    equal = all(v['points']==variants['baseline']['points'] for v in variants.values())
    exact = all(r['exact'] for v in variants.values() for r in v['replays'])
    filename = '_'.join(map(str,shape))+'.json.gz'
    write_gzip(out/filename,dict(shape=shape,states=records,variants=variants))
    stats = {name:{k:v['stats'].get(k,0) for k in
                  ('dp_transitions','loop_choices','scalar_bridge_hits','streamed_bridge_hits','free_retention_hits')}
             for name,v in variants.items()}
    for name,v in variants.items():
        stats[name]['cache_entries'] = sum(v['stats'][k]['currsize'] for k in ('solve_cache','group_cache'))
    return dict(shape=shape,file=filename,counts=dict(counts),stats=stats,
                root_replays=sum(len(v['replays']) for v in variants.values()),
                valid=count_matches and equal and exact and not any(counts[k] for k in
                    ('free_retention_wrong','two_live_wrong','incidence_criterion_wrong')))


def validate_formulas(out):
    rows, counts = [], Counter()
    for shape,graph,resident,child in conditional_cases():
        expected = tuple(p[:2] for p in child)
        base = sum(graph.size(t,set()) for t in (graph.consumed()^graph.produced())-resident)
        for method in ('dp','enumerate'):
            points = tuple((c,q-base) for c,q in curve(graph,external=resident,partitions=method))
            counts['free_oracle_queries'] += 1
            counts['free_oracle_wrong'] += points!=expected
        parent,notes,c,q = framed_streamed_witness(graph,resident,child)
        actual = simulate(parent,notes)
        exact = actual['valid'] and (actual['peak'],actual['traffic'])==(c,q)
        counts['free_framed_replays'] += 1
        counts['free_replay_wrong'] += not exact
        rows.append(dict(kind='free_retention',shape=shape,resident=sorted(resident),child=child,
                         notes=notes,expected=[c,q],actual=[actual['peak'],actual['traffic']],exact=exact))
    for label,graph,resident in cases():
        for domain in ('halving','divisors'):
            for owned in (False,True) if 'EX' in graph.ops else (False,):
                written = {'X'} if owned else set()
                predicted = two_live_response(graph,graph.ops,tuple(graph.sizes.values()),resident,
                                              written,tuple(graph.sizes),witness=True,tile_domain=domain)
                base = sum(graph.size(t,set()) for t in (graph.consumed()^graph.produced())-resident)
                expected = tuple(p[:2] for p in predicted)
                counts['two_live_conditional_queries'] += 1
                for method in ('dp','enumerate'):
                    points = tuple((c,q-base) for c,q in curve(graph,external=resident,written=written,
                                                              partitions=method,tile_domain=domain))
                    counts['two_live_oracle_queries'] += 1
                    counts['two_live_oracle_wrong'] += points!=expected
                replays = []
                if domain=='halving' or label[:2]==(13,12):
                    for point in predicted:
                        parent,notes,c,q = frame(graph,resident,(point,),owned)
                        actual = simulate(parent,notes)
                        exact = actual['valid'] and (actual['peak'],actual['traffic'])==(c,q)
                        counts['two_live_framed_replays'] += 1
                        counts['two_live_owned_replays'] += owned
                        counts['two_live_replay_wrong'] += not exact
                        replays.append(dict(notes=notes,expected=[c,q],actual=[actual['peak'],actual['traffic']],exact=exact))
                rows.append(dict(kind='two_live',case=label,domain=domain,owned=owned,resident=sorted(resident),
                                 predicted=predicted,replays=replays))
    graph = fork(4,4,1,4,'ii')
    controls = []
    for other in ('A','D1'):
        resident = graph.tensors(graph.ops)-{'X','V0',other}
        base = sum(graph.size(t,set()) for t in (graph.consumed()^graph.produced())-resident)
        points = curve(graph,external=resident,partitions='dp',witness=True)
        internal = tuple((c,q-base,w) for c,q,w in points)
        replays = []
        for point in internal:
            parent,notes,c,q = frame(graph,resident,(point,))
            actual = simulate(parent,notes)
            exact = actual['valid'] and (actual['peak'],actual['traffic'])==(c,q)
            counts['negative_control_replays'] += 1
            counts['negative_control_replay_wrong'] += not exact
            replays.append(dict(notes=notes,expected=[c,q],actual=[actual['peak'],actual['traffic']],exact=exact))
        controls.append(tuple(p[:2] for p in internal))
        rows.append(dict(kind='negative_control',shape=(4,4,1,4,'ii'),other_live=other,
                         resident=sorted(resident),points=internal,replays=replays))
    counts['negative_control_wrong'] += controls[0]!=((2,20),(3,8),(5,0)) or controls[1]!=((2,24),(3,8),(5,0))
    write_gzip(out/'formula_validation.json.gz',rows)
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=25,help='per census or validation batch')
    args = parser.parse_args()
    if args.seconds<=0:
        parser.error('positive budget required')
    args.out.mkdir(parents=True,exist_ok=False)
    initial = hashes()
    report = dict(status='running',revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip(),
                  started_utc=datetime.now(timezone.utc).isoformat(),source_sha256=initial,
                  hash_seed=os.environ.get('PYTHONHASHSEED'),python=platform.python_version(),
                  seconds_per_batch=args.seconds,memory_cap_bytes=2**30,
                  memory_enforcement='sampled peak RSS; additionally RLIMIT_AS on Linux',
                  scope='Exploratory fixed-order certificates. Multi-operator solve states only; axis and state counts kept separate. Profiled times are not speed measurements.')
    start = time.monotonic()
    deadline = start+args.seconds
    if platform.system()=='Linux':
        resource.setrlimit(resource.RLIMIT_AS,(2**30,2**30))
    def watch(*_):
        if time.monotonic()>=deadline:
            raise TimeoutError('one-obligation audit batch budget')
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if (rss if platform.system()=='Darwin' else rss*1024)>2**30:
            raise MemoryError('one-obligation peak RSS cap')
    def save():
        (args.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    signal.signal(signal.SIGALRM,watch)
    signal.setitimer(signal.ITIMER_REAL,.25,.25)
    save()
    try:
        report['archived'] = []
        for name in ('same6_serial40','mixed6_serial40'):
            deadline = time.monotonic()+args.seconds
            row = archived(name,args.out)
            report['archived'].append(row)
            print(json.dumps(dict(case=name,counts=row['counts'])),flush=True)
            save()
        report['fresh'] = []
        for shape in FRESH:
            deadline = time.monotonic()+args.seconds
            row = fresh(shape,args.out)
            report['fresh'].append(row)
            print(json.dumps(dict(shape=shape,counts=row['counts'],valid=row['valid'])),flush=True)
            save()
        deadline = time.monotonic()+args.seconds
        report['validation'] = validate_formulas(args.out)
        report['source_unchanged'] = hashes()==initial
        valid = (report['source_unchanged'] and all(r['valid'] for r in report['fresh'])
                 and not any(v for k,v in report['validation'].items() if k.endswith('_wrong'))
                 and not any(v for r in report['archived'] for k,v in r['counts'].items() if k.endswith('_wrong')))
        report['status'] = 'complete' if valid else 'invalid'
    except Exception as exc:
        report.update(status='error',error=f'{type(exc).__name__}: {exc}')
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        report['seconds'] = time.monotonic()-start
        save()
    return int(report['status']!='complete')


if __name__=='__main__':
    raise SystemExit(main())
