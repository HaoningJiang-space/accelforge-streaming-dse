"""Read-only integrity checks and descriptive summaries of the frozen matrix."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess


def summarize(root):
    manifest = json.loads((root/'manifest.json').read_text())
    revision = manifest['revision']
    cases, arms, rounds = (manifest[k] for k in ('cases', 'arms', 'rounds'))
    expected = {f'{case}_reference_audit.json' for case in cases}
    expected |= {f'{case}_{arm}_{tag}.json' for case in cases for arm in arms
                 for tag in ('audit', 'work', *map(str, range(rounds)))}
    missing = sorted(name for name in expected if not (root/name).exists())
    if missing:
        raise ValueError(f'incomplete matrix: {missing}')
    records = {name: json.loads((root/name).read_text()) for name in sorted(expected)}
    sources = {}
    replay_count = comparison_count = 0
    placeholders = transported = 0
    for name, record in records.items():
        if record['revision'] != revision or record['status'] != 'complete':
            raise ValueError(f'failed/unfrozen record: {name}')
        if record['hash_seed'] != '0':
            raise ValueError(f'hash seed differs: {name}')
        for source, digest in record['source_sha256'].items():
            if source not in sources:
                data = subprocess.check_output(['git', 'show', f'{revision}:{source}'])
                sources[source] = hashlib.sha256(data).hexdigest()
            if sources[source] != digest:
                raise ValueError(f'frozen source differs: {name}/{source}')
        reference_path = root/f"{record['case']}_reference_audit.json"
        reference = records[reference_path.name]
        if record['frontier'] != reference['frontier']:
            raise ValueError(f'union mismatch: {name}')
        by_order = {tuple(row['order']): row['frontier'] for row in reference['order_frontiers']}
        for row in record['order_frontiers']:
            if row['frontier'] != by_order[tuple(row['order'])]:
                raise ValueError(f'fixed-order mismatch: {name}')
            comparison_count += record['arm'] != 'reference'
        if record['arm'] != 'reference':
            if not record['equal'] or record['reference_sha256'] != hashlib.sha256(reference_path.read_bytes()).hexdigest():
                raise ValueError(f'reference mismatch: {name}')
        if len(record['replays']) != len(record['frontier']):
            raise ValueError(f'missing root replay: {name}')
        for point, replay in zip(record['frontier'], record['replays']):
            actual = replay['actual']
            if replay['point'] != point or not actual['valid'] or [actual['peak'], actual['traffic']] != point:
                raise ValueError(f'execution mismatch: {name}')
            replay_count += 1
        placeholders += record.get('selected_exact_placeholders', 0)
        transported += record.get('selected_transported_placeholders', 0)

    result = dict(revision=revision, records=len(records), source_files=len(sources),
                  full_order_comparisons=comparison_count, root_replays=replay_count,
                  selected_exact_placeholders=placeholders,
                  selected_transported_placeholders=transported,
                  all_frontiers_equal=True, cases={},
                  scorer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    for case in cases:
        table = {}
        for arm in arms:
            times = [records[f'{case}_{arm}_{r}.json'] for r in range(rounds)]
            generation = [row['generation_seconds'] for row in times]
            table[arm] = dict(generation_median=statistics.median(generation),
                              generation_range=[min(generation), max(generation)],
                              inclusive_median=statistics.median(row['inclusive_seconds'] for row in times),
                              recovery_median=statistics.median(row['recovery_seconds'] for row in times),
                              peak_rss_mib=statistics.median(row['pre_replay_peak_rss_kib']/1024 for row in times),
                              work=records[f'{case}_{arm}_work.json']['work'])
        old = min(manifest.get('old_arms', ('native', 'native_p', 'prefix', 'analytic')),
                  key=lambda arm: table[arm]['generation_median'])
        best_new = min(manifest.get('new_arms', [arm for arm in arms if arm.startswith('prefix_')]),
                       key=lambda arm: table[arm]['generation_median'])
        for arm, row in table.items():
            row.update(speedup_vs_prefix=table['prefix']['generation_median']/row['generation_median'],
                       speedup_vs_best_old=table[old]['generation_median']/row['generation_median'],
                       speedup_vs_native=table['native']['generation_median']/row['generation_median'] if 'native' in table else None,
                       speedup_vs_analytic=table['analytic']['generation_median']/row['generation_median'],
                       rss_ratio_vs_prefix=row['peak_rss_mib']/table['prefix']['peak_rss_mib'],
                       paired_wins_vs_analytic=sum(records[f'{case}_{arm}_{r}.json']['generation_seconds'] <
                                                   records[f'{case}_analytic_{r}.json']['generation_seconds']
                                                   for r in range(rounds)),
                       paired_wins_vs_best_old=sum(records[f'{case}_{arm}_{r}.json']['generation_seconds'] <
                                                   records[f'{case}_{old}_{r}.json']['generation_seconds']
                                                   for r in range(rounds)),
                       paired_wins_vs_prefix=sum(records[f'{case}_{arm}_{r}.json']['generation_seconds'] <
                                                 records[f'{case}_prefix_{r}.json']['generation_seconds']
                                                 for r in range(rounds)))
        reference = records[f'{case}_reference_audit.json']
        result['cases'][case] = dict(arms=table, best_declared_old=old, best_observed_combination=best_new,
                                    all_orders=reference['all_orders'],
                                    representative_orders=records[f'{case}_prefix_audit.json']['searched_orders'],
                                    frontier=reference['frontier'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('preserve prior summary')
    result = summarize(args.root)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('records', 'source_files', 'full_order_comparisons', 'root_replays')}))
    for name, case in result['cases'].items():
        best = case['best_observed_combination']
        print(name, best, case['arms'][best]['speedup_vs_prefix'])


if __name__ == '__main__':
    main()
