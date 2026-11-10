"""Check frozen conditional predictions against unmodified v2 and replay all points."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from math import isfinite
import os
from pathlib import Path
import platform
import signal
import subprocess
from time import perf_counter

from .graph.analysis import traffic_at
from .graph.curve import curve
from .graph.model import Graph
from .simulate_nest import simulate
from .test_streamed_bridge import framed_streamed_witness

HERE = Path(__file__).parent


def graph_of(shape):
    a,b,c = shape
    return Graph(dict(I=a,J=b,K=c),[
        ('E0',{'x':('I',),'W0':('I','J'),'h':('J',)}),
        ('E1',{'h':('J',),'W1':('J','K'),'z':('K',)})])


def run(prediction_path, out):
    raw = prediction_path.read_bytes()
    frozen = json.loads(raw)
    for name,digest in frozen['source_sha256'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == digest,name
    # Verify the checked prediction is in the already committed freeze revision.
    freeze_revision = '5b2b6169'
    archived = subprocess.check_output(['git','show',
        f'{freeze_revision}:research/index_coupling/results/two_contraction_interfaces/predictions.json'])
    assert archived == raw
    out.mkdir(parents=True,exist_ok=False)
    sources = dict(frozen['source_sha256'])
    for name in ('check_two_contraction_interfaces.py','graph/span_names.py','graph/remainder.py',
                 'scalar_bridge.py','streamed_bridge.py'):
        sources[name] = hashlib.sha256((HERE/name).read_bytes()).hexdigest()
    record = dict(freeze_revision=freeze_revision, prediction_sha256=hashlib.sha256(raw).hexdigest(),
        source_sha256=sources, python=platform.python_version(), platform=platform.system(),
        hash_seed=os.environ.get('PYTHONHASHSEED'), seconds_per_case=30,
        options=dict(scalar_leaf='v2',oracle_partitions='enumerate',control_partitions='dp',
                     grid=None,witness=True,spill_cost=2), cases=[])
    groups = defaultdict(list)
    for row in frozen['predictions']:
        key = (tuple(row['shape']),row['resident_in'],row['resident_out'],row['domain'],row['entry'])
        groups[key].append(row)
    assert len(groups) == frozen['cases']
    totals, strata = Counter(), defaultdict(Counter)
    def timeout(*_):
        raise TimeoutError('30-second direct-interface case budget')
    previous = signal.signal(signal.SIGALRM,timeout)
    with (out/'cases.jsonl').open('w') as stream:
        for (shape,p,q,domain,entry), rows in groups.items():
            start = perf_counter()
            signal.alarm(30)
            item = dict(shape=shape,resident_in=p,resident_out=q,domain=domain,entry=entry)
            try:
                graph = graph_of(shape)
                resident = {'W0','W1'} | ({'x'} if p else set()) | ({'z'} if q else set())
                compulsory = (0 if p else shape[0])+(0 if q else shape[2])
                stats = {}
                points = curve(graph,external=resident,entry=entry,tile_domain=domain,
                               scalar_leaf='v2',partitions='enumerate',witness=True,stats=stats)
                control = curve(graph,external=resident,entry=entry,tile_domain=domain,
                                scalar_leaf='v2',partitions='dp')
                item['dp_equal'] = tuple(x[:2] for x in points) == control
                expected_frontier, best, mismatches = [], float('inf'), []
                kinds = Counter()
                for row in rows:
                    actual = traffic_at(row['capacity'],points)-compulsory
                    actual = actual if isfinite(actual) else None
                    expected = row['extra']
                    kinds['infeasible' if expected is None else ('zero' if expected == 0 else 'positive')] += 1
                    if actual != expected:
                        mismatches.append(dict(capacity=row['capacity'],expected=expected,actual=actual))
                    if expected is not None and expected < best:
                        expected_frontier.append((row['capacity'],expected))
                        best = expected
                actual_frontier = [(c,t-compulsory) for c,t,_ in points]
                item.update(mismatches=mismatches, frontier_equal=actual_frontier==expected_frontier,
                            compulsory=compulsory, expected_frontier=expected_frontier,
                            actual_frontier=actual_frontier, points=points, stats=stats, point_kinds=dict(kinds))
                replays = []
                for capacity,traffic,witness in points:
                    # A nonscalar group witness must be entered from a legal
                    # solve wrapper; scalar redirected groups already are solves.
                    child_notes = witness
                    if entry == 'group' and witness and witness[0][0] == 'loop':
                        child_notes = (('groups',(graph.ops,),'kept',(),'via DRAM',()),)+witness
                    extra = traffic-compulsory
                    framed, notes, expected_peak, frame_compulsory = framed_streamed_witness(
                        graph,resident,((capacity,extra,child_notes),))
                    actual = simulate(framed,notes,scalar_leaf='v2')
                    expected_traffic = frame_compulsory+2*extra  # two real caller-loop trips
                    exact = (actual['peak'],actual['traffic']) == (expected_peak,expected_traffic)
                    replays.append(dict(capacity=capacity,extra=extra,exact=exact,
                        expected_frame_peak=expected_peak,expected_frame_traffic=expected_traffic,
                        actual=actual))
                item['replays'] = replays
                valid = item['dp_equal'] and item['frontier_equal'] and not mismatches and all(r['exact'] for r in replays)
                item['status'] = 'pass' if valid else 'fail'
                summary = dict(cases=1,pass_cases=int(valid),point_comparisons=len(rows),
                    point_matches=len(rows)-len(mismatches),dp_equal=int(item['dp_equal']),
                    frontier_equal=int(item['frontier_equal']),replays=len(replays),
                    exact_replays=sum(r['exact'] for r in replays),**kinds)
                totals.update(summary)
                for label in (entry,domain,f'context_{int(p)}{int(q)}'):
                    strata[label].update(summary)
            except Exception as exc:
                item.update(status='timeout' if isinstance(exc,TimeoutError) else 'error',
                            error=f'{type(exc).__name__}: {exc}')
                totals['errors'] += 1
            finally:
                signal.alarm(0)
                item['seconds'] = perf_counter()-start
            stream.write(json.dumps(item,allow_nan=False)+'\n')
            stream.flush()
            record['cases'].append({k:item[k] for k in ('shape','resident_in','resident_out','domain','entry','status','seconds')})
            if item['status'] != 'pass':
                print(json.dumps({k:v for k,v in item.items() if k in ('shape','entry','status','error','mismatches')}),flush=True)
    signal.signal(signal.SIGALRM,previous)
    record.update(totals=dict(totals),strata={k:dict(v) for k,v in strata.items()},
        complete=len(record['cases'])==frozen['cases'],
        all_pass=totals['pass_cases']==frozen['cases'],
        cases_sha256=hashlib.sha256((out/'cases.jsonl').read_bytes()).hexdigest())
    (out/'run.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print(json.dumps(record['totals']))
    return record['all_pass']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    return int(not run(args.predictions,args.out))


if __name__ == '__main__':
    raise SystemExit(main())
