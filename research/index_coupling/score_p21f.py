"""Score frozen P21f records without running searches; diagnostics stay unscored."""
import argparse
import json

from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.run_p21f import MANIFEST, frozen, known_reference, path_for, sha


def compare(free, tied):
    """Exact integer intervals, including infeasible regions and the infinite tail."""
    cuts = sorted({0} | {p[0] for p in free + tied})
    intervals = []
    for j, c in enumerate(cuts):
        f, t = traffic_at(c, free), traffic_at(c, tied)
        if f == t:
            continue  # also handles infinity == infinity, without subtraction
        hi = cuts[j + 1] - 1 if j + 1 < len(cuts) else None
        relation = 'higher' if t > f else 'lower'
        if intervals and intervals[-1]['relation'] == relation and intervals[-1]['hi'] == c - 1:
            intervals[-1]['hi'] = hi
        else:
            intervals.append(dict(lo=c, hi=hi, relation=relation))
    return dict(equal=not intervals, intervals=intervals,
                higher=any(x['relation'] == 'higher' for x in intervals),
                lower=any(x['relation'] == 'lower' for x in intervals),
                unequal_capacities=None if any(x['hi'] is None for x in intervals) else
                    sum(x['hi'] - x['lo'] + 1 for x in intervals),
                free_plateau=free[-1][0], tied_plateau=tied[-1][0],
                same_min_traffic=free[-1][1] == tied[-1][1])


def validate(record, spec, arm, domain, manifest):
    for key, expected in dict(**spec, arm=arm, tile_domain=domain, experiment='P21f',
                              manifest_sha256=sha(MANIFEST), source_sha256=manifest['source_sha256'],
                              wall_limit_seconds=1800, address_space_limit_gib=8, hash_seed='0').items():
        if record.get(key) != expected:
            raise ValueError(f'mismatched {key}')
    if not record.get('source_revision'):
        raise ValueError('missing source revision')
    points = record['points']
    if not points or any(len(p) != 2 or any(type(v) is not int or v < 0 for v in p) for p in points):
        raise ValueError('missing or malformed points')
    if any(a[0] >= b[0] or a[1] <= b[1] for a, b in zip(points, points[1:])):
        raise ValueError('noncanonical frontier')
    if [w[:2] for w in record['witnesses']] != points:
        raise ValueError('witness/frontier mismatch')
    replays = record['replays']
    if len(replays) != len(points):
        raise ValueError('incomplete replays')
    for (c, q), r in zip(points, replays):
        a = r['actual']
        if not (r['exact'] is True and a['valid'] is True and
                (r['capacity'], r['traffic'], a['peak'], a['traffic']) == (c, q, c, q)):
            raise ValueError('inexact replay')


def load(directory, spec, arm, domain, manifest):
    path = path_for(directory, spec['case'], arm, domain)
    if not path.exists():
        return None, 'missing'
    try:
        record = json.loads(path.read_text())
        if record.get('status') != 'complete':
            return None, record.get('status', 'missing status')
        validate(record, spec, arm, domain, manifest)
        if not spec['held_out'] and domain == 'halving':
            original = json.loads(known_reference(spec, arm).read_text())
            if record['points'] != original['points']:
                raise ValueError('known P21e halving curve differs from archived reference')
        return record, None
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        return None, f'invalid: {exc}'


def plateau_prediction(spec, comparison):
    # Predictions are limited to the two open bands, not boundary equalities.
    expect_larger = spec['reads_x'] or spec['cohort'] == 'above'
    actual = comparison['tied_plateau'] > comparison['free_plateau'] if expect_larger else (
        comparison['tied_plateau'] == comparison['free_plateau'])
    return bool(comparison['same_min_traffic'] and actual)


def score(directory, manifest):
    rows, records = [], {}
    for spec in manifest['cases']:
        for domain in spec['domains']:
            row = dict(case=spec['case'], cohort=spec['cohort'], reads_x=spec['reads_x'],
                       shape=spec['shape'], held_out=spec['held_out'], tile_domain=domain)
            pair, errors = {}, {}
            for arm in ('free', 'tied'):
                r, error = load(directory, spec, arm, domain, manifest)
                if r is not None:
                    pair[arm] = r
                    records[spec['case'], domain, arm] = r
                else:
                    errors[arm] = error
            row.update(valid=False, errors=errors)
            if not errors:
                if pair['free']['source_revision'] != pair['tied']['source_revision']:
                    row['errors']['pair'] = 'mixed source revisions'
                else:
                    comparison = compare(pair['free']['points'], pair['tied']['points'])
                    row.update(comparison)
                    row['valid'] = not comparison['lower']
                    if comparison['lower']:
                        row['errors']['pair'] = 'tied below free: invalid subset comparison'
                    if row['valid'] and spec['cohort'] in ('between', 'above'):
                        row['plateau_pass'] = plateau_prediction(spec, comparison)
                        row['existence_pass'] = comparison['higher']
            rows.append(row)
    primary = [r for r in rows if r['cohort'] in ('between', 'above')]
    strata = {}
    for reads_x in (False, True):
        for cohort in ('between', 'above'):
            group = [r for r in primary if r['reads_x'] == reads_x and r['cohort'] == cohort]
            key = ('read_x_' if reads_x else 'independent_') + cohort
            strata[key] = dict(passed=sum(r.get('plateau_pass', False) for r in group),
                               valid=sum(r['valid'] for r in group), total=8, required=8)
    failed = any(r.get('plateau_pass') is False for r in primary)
    all_valid = all(r['valid'] for r in primary)
    plateau_verdict = 'fail' if failed else 'pass' if all_valid else 'incomplete_or_invalid'
    diagnostics = []
    for spec in manifest['cases']:
        if 'divisors' not in spec['domains']:
            continue
        h, d = [next(r for r in rows if r['case'] == spec['case'] and r['tile_domain'] == domain)
                for domain in ('halving', 'divisors')]
        item = dict(case=spec['case'], held_out=spec['held_out'], valid=False)
        if h['valid'] and d['valid']:
            inclusion = {arm: compare(records[spec['case'], 'halving', arm]['points'],
                                      records[spec['case'], 'divisors', arm]['points'])
                         for arm in ('free', 'tied')}
            item.update(valid=not any(c['higher'] for c in inclusion.values()),
                        divisors_never_worse={a: not c['higher'] for a, c in inclusion.items()},
                        halving_unequal_capacities=h['unequal_capacities'],
                        divisors_unequal_capacities=d['unequal_capacities'],
                        outcome=('both_equal' if h['equal'] and d['equal'] else
                                 'removed' if d['equal'] else 'introduced' if h['equal'] else 'persists'))
        diagnostics.append(item)
    summary = dict(experiment='P21f', manifest_sha256=sha(MANIFEST), plateau_verdict=plateau_verdict,
                   primary_strata=strata, primary_valid=sum(r['valid'] for r in primary), primary_total=32,
                   existence=dict(passed=sum(r.get('existence_pass', False) for r in primary), required=32,
                                  verdict='fail' if any(r.get('existence_pass') is False for r in primary) else
                                      'pass' if all_valid else 'incomplete_or_invalid'),
                   complete_records=len(records), expected_records=manifest['jobs'],
                   all_pairs_valid=all(r['valid'] for r in rows),
                   tile_diagnostic_valid=all(r['valid'] for r in diagnostics))
    return dict(summary=summary, comparisons=rows, tile_diagnostics=diagnostics)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    args = parser.parse_args()
    report = score(args.directory, frozen())
    print(json.dumps(report, indent=2, allow_nan=False))
    s = report['summary']
    return 0 if (s['plateau_verdict'] == 'pass' and s['existence']['verdict'] == 'pass'
                 and s['all_pairs_valid'] and s['tile_diagnostic_valid']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
