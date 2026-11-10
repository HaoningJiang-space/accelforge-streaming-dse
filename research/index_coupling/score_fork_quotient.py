"""Require every declared reference order before claiming quotient equality."""
import argparse
from collections import Counter
import json
from pathlib import Path

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
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);args=p.parse_args()
    result=score(args.directory)
    print(json.dumps(result,indent=2));return int(bool(result['errors']))


if __name__=='__main__':
    raise SystemExit(main())
