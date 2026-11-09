"""Score the frozen P21 records without silently accepting missing cases."""
import argparse
import hashlib
import json
from pathlib import Path
from research.index_coupling.run_p21 import CASES, comparison, frontier, serial, shifted


def score(directory):
    complete, missing, incomplete, invalid = [], [], [], []
    for index, spec in enumerate(CASES):
        path = directory / f'case_{index:02d}.json'
        if not path.exists() or not path.stat().st_size:
            missing.append(index)
            continue
        record = json.loads(path.read_text())
        if record.get('status') != 'complete':
            incomplete.append(dict(case=index, error=record.get('error')))
            continue
        case = record['result']
        shape, depth, reads_x = spec
        expected_tiles = {shape, (shape[0]//2, shape[1], shape[2]),
                          (shape[0], shape[1]//2, shape[2]),
                          (shape[0]//2, shape[1]//2, shape[2])}
        actual_tiles = {tuple(x['shape']) for x in case['interfaces']}
        current_protocol = hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest()
        if (case['case'] != index or tuple(case['shape']) != shape
                or (case['depth'], case['reads_x']) != (depth, reads_x)
                or actual_tiles != expected_tiles or len(case['interfaces']) != len(expected_tiles)
                or record['protocol_sha256'] != current_protocol):
            invalid.append(index)
            continue
        complete.append(record)
    interfaces = [x for r in complete for x in r['result']['interfaces']]
    unique, duplicate_mismatches = {}, []
    for x in interfaces:
        key = (tuple(x['shape']), x['depth'], x['reads_x'])
        previous = unique.setdefault(key, x)
        if (previous['children'] != x['children'] or any(
                previous['curves'][k] != x['curves'][k]
                for k in ('keep', 'spill', 'actual', 'coarse'))):
            duplicate_mismatches.append(key)
    full = [r['result']['interfaces'][0] for r in complete]
    a = [x for x in interfaces if not x['reads_x']]
    b = [x for x in interfaces if x['reads_x']]
    replays = [p for x in interfaces for plans in x['replay'].values() for p in plans]
    branch_bad = [dict(shape=x['shape'], depth=x['depth'], reads_x=x['reads_x'], check=k)
                  for x in interfaces for k in ('keep', 'spill', 'composed')
                  if not x['checks'][k]['exact']]
    table = []
    read_credit = []
    for x in full:
        table.append(dict(shape=x['shape'], depth=x['depth'], reads_x=x['reads_x'],
                          fixed_points=len(x['curves']['actual']),
                          free_points=len(x['curves']['unrestricted']),
                          fixed_exact=x['checks']['composed']['exact'],
                          coarse_wrong_capacities=x['checks']['coarse']['wrong_capacities'],
                          free_wrong_capacities=x['checks']['free']['wrong_capacities'],
                          choices=x['choices'],
                          bare_wrong_choices=x['bare_inequality']['wrong_choices']))
        if x['reads_x']:
            # Post-hoc mechanism diagnostic on saved curves, not a new frozen claim:
            # does removing only the compulsory X read repair the coarse interface?
            s = x['s']
            children = x['children']
            keep = serial([shifted(children['resident'][0], s),
                           shifted(children['cold'][1], s, -s),
                           shifted(children['resident'][2], s)])
            repaired = frontier(keep + x['curves']['spill'])
            read_credit.append(dict(shape=x['shape'], depth=x['depth'],
                                    comparison=comparison(repaired, x['curves']['actual'])))
    complete_ok = len(complete) == len(CASES)
    return dict(expected_cases=len(CASES), complete_cases=len(complete),
                missing=missing, incomplete=incomplete, invalid=invalid,
                interfaces=len(interfaces), informative_interfaces=sum(
                    x['checks']['composed']['informative'] for x in interfaces),
                distinct_interfaces=len(unique), distinct_feasible_interfaces=sum(
                    x['checks']['composed']['informative'] for x in unique.values()),
                duplicate_mismatches=duplicate_mismatches,
                p21a_bridge_exact=sum(x['checks']['bridge']['exact'] for x in a),
                p21a_interfaces=len(a),
                p21a_informative_interfaces=sum(x['checks']['composed']['informative'] for x in a),
                p21a_bare_wrong_choice_interfaces=sum(bool(x['bare_inequality']['wrong_choices']) for x in a),
                p21b_coarse_wrong_interfaces=sum(not x['checks']['coarse']['exact'] for x in b),
                p21b_coarse_wrong_full_cases=sum(not x['checks']['coarse']['exact'] for x in full if x['reads_x']),
                p21b_residency_distinct_interfaces=sum(not x['checks']['h_residency']['exact'] for x in b),
                p21b_interfaces=len(b), composition_failures=branch_bad,
                p21b_informative_interfaces=sum(x['checks']['composed']['informative'] for x in b),
                free_differs_full_cases=sum(not x['checks']['free']['exact'] for x in full),
                replayed=len(replays), replay_failures=[x for x in replays if not x['exact']],
                seconds=sum(r['seconds'] for r in complete),
                max_peak_rss_kib=max((r['peak_rss_kib'] for r in complete), default=0),
                source_revisions=sorted({r['source_revision'] for r in complete}),
                protocol_hashes=sorted({r['protocol_sha256'] for r in complete}),
                exact_predictions_pass=(complete_ok and not branch_bad and not duplicate_mismatches
                    and all(x['checks']['bridge']['exact'] for x in a)
                    and not any(x['bare_inequality']['wrong_choices'] for x in a)
                    and all(x['exact'] for x in replays)),
                coarse_failure_prediction_pass=(complete_ok and any(
                    not x['checks']['coarse']['exact'] for x in full if x['reads_x'])),
                posthoc_compulsory_read_credit=read_credit,
                cases=table)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    result = score(args.directory)
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(0 if result['exact_predictions_pass'] and result['coarse_failure_prediction_pass'] else 1)
