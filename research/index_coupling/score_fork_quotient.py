"""Require every declared reference order before claiming quotient equality."""
import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import median

from .graph.curve import pareto


def score(directory):
    directory = Path(directory)
    manifest = json.loads((directory/'manifest.json').read_text())
    records, errors = {}, []
    for spec in manifest['specs']:
        name = spec['name']; path = directory/f'{name}.json'
        if not path.exists():
            errors.append(dict(case=name, error='missing record')); continue
        record = json.loads(path.read_text()); records[name] = record
        if record.get('spec') != spec or record.get('source_sha256') != manifest['source_sha256']:
            errors.append(dict(case=name, error='spec/source mismatch'))
        if record.get('revision') != manifest['revision'] or record.get('hash_seed') != '0':
            errors.append(dict(case=name, error='revision/seed mismatch'))
        if record.get('status') != 'complete':
            errors.append(dict(case=name, error=record.get('status')))
    comparisons = []
    for spec in manifest['specs']:
        if spec['mode'] != 'quotient': continue
        refspecs = [s for s in manifest['specs'] if s['mode']=='oracle' and s['case']==spec['case']]
        actual = records.get(spec['name'])
        refs = [records.get(s['name']) for s in refspecs]
        complete = bool(refs) and actual and actual.get('status')=='complete' and all(r and r.get('status')=='complete' for r in refs)
        comparison = dict(case=spec['case'], required_reference_orders=len(refs), complete_reference=bool(complete))
        if complete:
            expected = [list(p) for p in pareto(tuple(p) for r in refs for p in r['points'])]
            comparison.update(equal=expected==actual['points'], quotient=actual['points'], oracle=expected,
                reference_search_seconds=sum(r['search_seconds'] for r in refs),
                reference_memo_entries=sum(r['stats'][f'{s}_cache']['currsize'] for r in refs for s in ('solve','group')),
                quotient_search_seconds=actual['search_seconds'],
                quotient_memo_entries={s:actual['stats'][f'{s}_cache']['currsize'] for s in ('solve','group','sequence')})
            if not comparison['equal']:errors.append(dict(case=spec['case'], error='frontier mismatch'))
        comparisons.append(comparison)
    replays, censuses = [], []
    for r in records.values():
        replays.extend(r.get('replays', []))
        if r['spec']['mode']=='census':
            queries = r.get('queries', [])
            replays.extend(c for q in queries for c in q['replays'])
            valid = (r.get('status')=='complete' and len(queries)==64 and
                     all(q['equal'] and q['oracle']['orders']==6 for q in queries) and
                     r.get('root_orbits')==r.get('predicted_orbits'))
            censuses.append(dict(case=r['spec']['case'], valid=valid, queries=len(queries),
                                 root_orbits=r.get('root_orbits'), predicted=r.get('predicted_orbits')))
            if not valid:errors.append(dict(case=r['spec']['name'], error='incomplete/invalid census'))
    wrong = sum(not r['exact'] for r in replays)
    if wrong:errors.append(dict(error='replay mismatch', count=wrong))
    return dict(revision=manifest['revision'], expected_jobs=len(manifest['specs']), records=len(records),
                statuses=dict(Counter(r['status'] for r in records.values())), errors=errors,
                comparisons=comparisons, censuses=censuses, replays=len(replays), replay_failures=wrong,
                verdict='valid' if not errors else 'incomplete_or_invalid')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--ablation',action='store_true');args=p.parse_args()
    result=score_ablation(args.directory) if args.ablation else score(args.directory)
    print(json.dumps(result,indent=2));return int(bool(result['errors']))


def score_ablation(directory):
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
    records,errors={},[]
    for spec in manifest['specs']:
        path=directory/f"{spec['name']}.json"
        if not path.exists():errors.append(dict(case=spec['name'],error='missing'));continue
        r=json.loads(path.read_text());records[spec['name']]=r
        if (r.get('spec')!=spec or r.get('source_sha256')!=manifest['source_sha256'] or
            r.get('revision')!=manifest['revision'] or r.get('hash_seed')!='0'):
            errors.append(dict(case=spec['name'],error='provenance mismatch'))
        if r.get('status')!='complete':errors.append(dict(case=spec['name'],error=r.get('status')))
    comparisons=[]
    for m in (4,6):
        for role in ('same','mixed'):
            a=records.get(f'ablation_{role}{m}_quotient');b=records.get(f'ablation_{role}{m}_labeled')
            complete=a and b and a['status']==b['status']=='complete'
            c=dict(case=f'{role}{m}',complete=bool(complete))
            if complete:
                c.update(equal=a['points']==b['points'],quotient_seconds=a['search_seconds'],labeled_seconds=b['search_seconds'],
                         quotient_entries=sum(a['stats'][f'{s}_cache']['currsize'] for s in ('solve','group','sequence')),
                         labeled_entries=sum(b['stats'][f'{s}_cache']['currsize'] for s in ('solve','group','sequence')))
                if not c['equal']:errors.append(dict(case=c['case'],error='frontier mismatch'))
            comparisons.append(c)
    timing={mode:[records.get(f'timing_{mode}_{i}') for i in range(3)] for mode in ('fixed','quotient')}
    valid=all(r and r['status']=='complete' for rs in timing.values() for r in rs)
    timing_result=dict(complete=valid)
    if valid:
        frontiers={tuple(map(tuple,r['points'])) for rs in timing.values() for r in rs}
        seconds={mode:[r['search_seconds'] for r in rs] for mode,rs in timing.items()}
        medians={mode:median(ts) for mode,ts in seconds.items()}
        timing_result.update(equal=len(frontiers)==1,search_seconds=seconds,medians=medians,
                             median_ratio=medians['fixed']/medians['quotient'])
        if len(frontiers)!=1:errors.append(dict(error='timing frontier mismatch'))
    replays=[c for r in records.values() for c in r.get('replays',[])]
    wrong=sum(not c['exact'] for c in replays)
    if wrong:errors.append(dict(error='replay mismatch',count=wrong))
    return dict(expected_jobs=len(manifest['specs']),records=len(records),errors=errors,
                statuses=dict(Counter(r['status'] for r in records.values())),comparisons=comparisons,
                timing=timing_result,replays=len(replays),replay_failures=wrong)


if __name__=='__main__':
    raise SystemExit(main())
