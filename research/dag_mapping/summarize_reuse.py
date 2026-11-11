"""Read-only scoring of the frozen cross-order experiment and primary gate."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median

from .artifacts import frozen_bytes


def summarize(root):
    manifest = json.loads((root/'manifest.json').read_text())
    revision, arms = manifest['revision'], manifest['arms']
    failures, references, audit_counts = [], {}, dict(hits=0, verified=0, verified_empty=0, verified_multiop=0)
    replays, records, comparisons = 0, 0, 0

    def read(path):
        nonlocal replays, records, comparisons
        if not path.exists():
            failures.append(dict(file=path.name, error='missing'))
            return None
        r = json.loads(path.read_text())
        records += 1
        if r['revision'] != revision:
            raise ValueError('mixed frozen revisions')
        for source, digest in r['source_sha256'].items():
            if hashlib.sha256(frozen_bytes(revision, source)).hexdigest() != digest:
                raise ValueError(f'source hash mismatch: {source}')
        if r['status'] != 'complete':
            failures.append(dict(file=path.name, error=r.get('error', r['status'])))
            return None
        rows = r['arms'] if r['mode'] == 'audit' else [r]
        for row in rows:
            if row['arm'] == 'native' and row['case'] not in references:
                references[row['case']] = row
            ref = references[row['case']]
            if row['frontier'] != ref['frontier']:
                raise ValueError('complete union differs')
            per_order = {tuple(p['order']): p['frontier'] for p in ref['order_frontiers']}
            for pointset in row['order_frontiers']:
                if pointset['frontier'] != per_order[tuple(pointset['order'])]:
                    raise ValueError('complete per-order response differs')
                comparisons += 1
            for replay in row['replays']:
                actual = replay['actual']
                if not actual['valid'] or [actual['peak'], actual['traffic']] != replay['point']:
                    raise ValueError('execution differs')
                replays += 1
        return r

    for name in manifest['audit_cases']:
        r = read(root/f'{name}_sym_shared_audit.json')
        if r:
            for row in r['arms']:
                if row['pool']:
                    if row['pool']['hits'] != row['pool']['verified']:
                        raise ValueError('unverified audit hit')
                    for field in audit_counts:
                        audit_counts[field] += row['pool'][field]
    rows = []
    for name in manifest['timed_cases']:
        values, work = {}, {}
        samples = {}
        for arm in arms:
            timed = [read(root/f'{name}_{arm}_{turn}.json') for turn in range(manifest['rounds'])]
            w = read(root/f'{name}_{arm}_work.json')
            if not all(timed) or w is None:
                continue
            fields = ('setup_seconds', 'generation_seconds', 'inclusive_seconds',
                      'recovery_seconds', 'replay_seconds', 'pre_replay_peak_rss_kib')
            values[arm] = {field: median(r[field] for r in timed) for field in fields}
            values[arm].update(generation_range=[min(r['generation_seconds'] for r in timed),
                                                 max(r['generation_seconds'] for r in timed)],
                               all_orders=w['all_orders'], searched_orders=w['searched_orders'],
                               sharing_enabled=w['sharing_enabled'])
            samples[arm] = [r['generation_seconds'] for r in timed]
            work[arm] = dict(w['work'], pool=w['pool'],
                            response_bodies=w['pool']['misses'] if w['pool'] else
                            w['work']['local_solve_misses']+w['work']['local_group_misses'])
        row = dict(case=name, medians=values, work=work)
        if all(arm in values for arm in ('sym_shared','sym_prefix','sym_analytic')):
            baseline = min(('sym_prefix','sym_analytic'), key=lambda a: values[a]['generation_seconds'])
            candidate, base = values['sym_shared'], values[baseline]
            reduction = 1-candidate['generation_seconds']/base['generation_seconds']
            wins = sum(a < b for a,b in zip(samples['sym_shared'], samples[baseline]))
            inclusive = candidate['inclusive_seconds'] < min(values[a]['inclusive_seconds']
                                                             for a in ('sym_prefix','sym_analytic'))
            memory = candidate['pre_replay_peak_rss_kib']/base['pre_replay_peak_rss_kib']
            row['primary_comparison'] = dict(baseline=baseline, reduction=reduction, paired_wins=wins,
                                             inclusive_faster=inclusive, rss_ratio=memory,
                                             passed=reduction>=.10 and wins>=4 and inclusive and memory<=2)
        rows.append(row)
    primary = [r for r in rows if r['case'] in manifest['primary_cases']]
    passed = (not failures and len(primary)==len(manifest['primary_cases']) and
              all(r.get('primary_comparison',{}).get('passed',False) for r in primary))
    return dict(revision=revision, record_count=records, failures=failures,
                audit_counts=audit_counts, independent_replays=replays,
                complete_per_order_comparisons=comparisons, rows=rows, primary_passed=passed,
                analyzer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                interpretation='bounded cross-global-order reuse; no global-order elimination or DNN claim')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('preserve previous summary')
    result = summarize(args.archive)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('record_count','failures','audit_counts',
                                          'independent_replays','primary_passed')}))
