"""Compare all completed arms and their internal responses to literal enumeration."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
from statistics import median

from .run_unified_search import CASES
from .unified_search import mixed_branch_graph, scalar_separator_certificate


def key(row):
    s = row['state']
    return (tuple(row['order']), s['stage'], tuple(s['ops']), tuple(s['ext']),
            tuple(s['external']), tuple(s['owned']), s['constrained'])


def rows(path):
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            yield json.loads(line)


def numeric(record):
    return [[p['capacity'], p['traffic']] for p in record.get('points', [])]


def score(census, timing=None):
    census = Path(census)
    manifest = json.loads((census / 'manifest.json').read_text())
    errors, arms, lower_checks = [], [], []
    total_compared = total_replays = 0
    for case in CASES:
        baseline_path = census / f'{case}_000.json'
        if not baseline_path.exists():
            errors.append(dict(case=case, error='missing baseline'))
            continue
        baseline = json.loads(baseline_path.read_text())
        if baseline['status'] != 'complete':
            errors.append(dict(case=case, error='incomplete baseline'))
            continue
        reference = {}
        graph = mixed_branch_graph(CASES[case])
        counts, spans, shared_counts = Counter(), Counter(), Counter()
        examples = []
        for row in rows(census / f'{case}_000.states.jsonl.gz'):
            k = key(row)
            if k in reference:
                errors.append(dict(case=case, error='duplicate baseline state'))
            reference[k] = row['points']
            s = row['state']
            if s['stage'] == 'solve' and not s['constrained']:
                cert = scalar_separator_certificate(graph, s['ops'], s['ext'], s['external'], s['owned'], sorted(graph.sizes))
                if cert is not None:
                    counts['eligible'] += 1
                    spans[','.join(s['ops'])] += 1
                    shared_counts[len(cert['shared'])] += 1
                    expected = [[cert['capacity'], 0]]
                    if row['points'] != expected:
                        counts['wrong'] += 1
                        if len(examples) < 3:
                            examples.append(dict(state=s, expected=expected, actual=row['points']))
        lower_checks.append(dict(case=case, baseline_states=len(reference), counts=dict(counts),
                                 by_span=dict(spans), shared_scalar_counts=dict(shared_counts), errors=examples))
        if counts['wrong']:
            errors.append(dict(case=case, error='certificate mismatch', count=counts['wrong']))
        for job in (j for j in manifest['jobs'] if j['case'] == case):
            path = census / (job['name'] + '.json')
            if not path.exists():
                errors.append(dict(case=case, arm=job['bits'], error='missing arm'))
                continue
            r = json.loads(path.read_text())
            if (r['source_sha256'] != manifest['source_sha256'] or r['revision'] != manifest['revision']
                    or r['hash_seed'] != '0' or r['shape'] != list(CASES[case]) or r['switches'] != job['bits']):
                errors.append(dict(case=case, arm=job['bits'], error='provenance mismatch'))
            entry = dict(case=case, switches=r['switches'], status=r['status'], stats=r.get('stats'),
                         search_seconds=r.get('search_seconds'), peak_rss_kib=r['peak_rss_kib'],
                         state_records=r['state_records'], joint_chain=r.get('joint_chain', False))
            if r['status'] != 'complete':
                errors.append(dict(case=case, arm=job['bits'], error=r['status']))
                arms.append(entry)
                continue
            entry['root_equal'] = numeric(r) == numeric(baseline)
            entry['replays'] = len(r['replays'])
            total_replays += len(r['replays'])
            if not entry['root_equal'] or len(r['replays']) != len(r['points']) or not all(x['exact'] for x in r['replays']):
                errors.append(dict(case=case, arm=job['bits'], error='root curve/replay mismatch'))
            compared = missing = wrong = seen = 0
            examples = []
            for row in rows(census / (job['name'] + '.states.jsonl.gz')):
                seen += 1
                k = key(row)
                if k not in reference:
                    missing += 1
                    if len(examples) < 3:
                        examples.append(dict(error='missing reference context', row=row))
                else:
                    compared += 1
                    if reference[k] != row['points']:
                        wrong += 1
                        if len(examples) < 3:
                            examples.append(dict(error='different response', row=row, reference=reference[k]))
            if seen != r['state_records'] or seen != r['stats']['solve_entries'] + r['stats']['group_entries']:
                errors.append(dict(case=case, arm=job['bits'], error='incomplete census'))
            if missing or wrong:
                errors.append(dict(case=case, arm=job['bits'], error='internal comparison', missing=missing, wrong=wrong))
            if job['bits'] != '000':
                total_compared += compared
            entry.update(internal_compared=compared, internal_missing=missing, internal_wrong=wrong, examples=examples,
                         selected_certificates=len(r['selected_certificates']))
            arms.append(entry)
    controls = []
    if timing is not None:
        timing = Path(timing)
        tm = json.loads((timing / 'manifest.json').read_text())
        if tm['source_sha256'] != manifest['source_sha256'] or tm['revision'] != manifest['revision']:
            errors.append(dict(error='timing provenance mismatch'))
        for case in ('core', 'rectangle'):
            baseline = json.loads((census / f'{case}_000.json').read_text())
            samples = {'000': [], '111': []}
            replays = 0
            for job in (j for j in tm['jobs'] if j['case'] == case):
                path = timing / (job['name'] + '.json')
                if not path.exists():
                    errors.append(dict(case=case, error='missing timing', name=job['name']))
                    continue
                r = json.loads(path.read_text())
                valid = (r['status'] == 'complete' and r['source_sha256'] == manifest['source_sha256']
                         and r['revision'] == manifest['revision'] and r['hash_seed'] == '0'
                         and numeric(r) == numeric(baseline) and len(r.get('replays', [])) == len(r.get('points', []))
                         and all(p['exact'] for p in r.get('replays', [])))
                if not valid:
                    errors.append(dict(case=case, error='invalid timing', name=job['name'], status=r['status']))
                    continue
                samples[r['switches']].append(r['search_seconds'])
                replays += len(r['replays'])
            record = dict(case=case, samples=samples, replays=replays)
            if all(len(v) == 3 for v in samples.values()):
                record.update(medians={k: median(v) for k, v in samples.items()},
                              ratio=median(samples['000']) / median(samples['111']))
            controls.append(record)
    return dict(revision=manifest['revision'], errors=errors, arms=arms, certificate_baseline_audit=lower_checks,
                optimized_internal_comparisons=total_compared, census_replays=total_replays,
                timing_controls=controls, timing_replays=sum(c['replays'] for c in controls))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('census', type=Path)
    p.add_argument('--timing', type=Path)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    result = score(args.census, args.timing)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('errors', 'optimized_internal_comparisons', 'census_replays', 'timing_replays')}))
    return int(bool(result['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
