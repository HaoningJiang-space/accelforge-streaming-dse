"""Verify the archived offline audit; add post-hoc shared-DAG ceilings.

The ideal simultaneous deletion is an optimistic ceiling, NOT a safe policy.
It can delete candidates used in each other's certificates. No solver is run.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from .c2_bound_audit import CASES, COUNTERS, analyze, reachable

HERE = Path(__file__).parent
REPO = HERE.parents[1]
PREFIX = 'research/index_coupling/'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def historical(revision, name):
    return subprocess.check_output(['git', 'show', f'{revision}:{PREFIX}{name}'], cwd=REPO)


def normalized(value):
    return json.loads(json.dumps(value))


def summarize(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    assert manifest['cases'] == list(CASES)
    assert json.loads((directory / 'exits.json').read_text()) == [0] * len(CASES)
    revision = manifest['revision']
    for name, digest in manifest['source_sha256'].items():
        assert sha(historical(revision, name)) == digest
        assert sha((HERE / name).read_bytes()) == digest
    result = dict(revision=revision,
        supplement='Post-hoc analysis of the frozen offline run; no online pruning or timing comparison.',
        ideal_ceiling_contract='Delete every individually oracle-eligible non-anchor loop edge; '
            'upper bound for this bound/pinned-anchor interface, not a jointly valid policy.',
        source_sha256={Path(__file__).name: sha(Path(__file__).read_bytes())},
        manifest_sha256=sha((directory / 'manifest.json').read_bytes()), cases={})
    for case in CASES:
        path = directory / case
        run = json.loads((path / 'run.json').read_text())
        report = json.loads((path / 'analysis.json').read_text())
        assert run['status'] == 'complete' and run['revision'] == revision
        assert run['source_sha256'] == manifest['source_sha256']
        for name, digest in run['artifacts_sha256'].items():
            assert sha((path / name).read_bytes()) == digest
        root_name = f'results/grammar_v2/check/{case}.v2.json'
        root_bytes = historical(revision, root_name)
        assert sha(root_bytes) == run['root_archive_sha256']
        with gzip.open(path / 'baseline.json.gz', 'rt') as stream:
            baseline = json.load(stream)
        with gzip.open(path / 'choices.jsonl.gz', 'rt') as stream:
            choices = [json.loads(line) for line in stream]
        assert baseline['points'] == json.loads(root_bytes)['v2']
        if 'old_census_sha256' in run:
            census_bytes = historical(revision, f'results/grammar_v2/census/{case}_v2.json')
            assert sha(census_bytes) == run['old_census_sha256']
            assert json.loads(census_bytes)['keys'] == len(baseline['nodes'])
        rebuilt, details = analyze(case, baseline)
        assert normalized(rebuilt) == report and normalized(details) == choices
        assert all(report['validation'].values())
        nodes = {n['id']: n for n in baseline['nodes']}
        all_nodes = set(nodes)
        modes = {}
        for mode in ('raw', 'slots'):
            ideal = {(r['parent'], r['child']) for r in choices if r['ideal_' + mode]}
            ordered = {(r['parent'], r['child']) for r in choices if r['ordered_' + mode]}
            assert ordered <= ideal
            alive = reachable(baseline['root'], baseline['edges'], ordered)
            targets = {c for p, c in ordered if p in alive}
            ceiling_alive = reachable(baseline['root'], baseline['edges'], ideal)
            assert ceiling_alive <= alive
            gone = all_nodes - ceiling_alive
            saved = {k: sum(nodes[i]['work'][k] for i in gone) for k in COUNTERS}
            projection = report['ordered_work_projection'][mode]
            modes[mode] = dict(
                ordered_unique_direct_targets=len(targets),
                ordered_direct_targets_still_reachable=len(targets & alive),
                ordered_direct_targets_unreachable=len(targets - alive),
                ordered_dp_saved=projection['saved_exclusive_work']['dp_transitions'],
                ordered_dp_fraction=projection['saved_exclusive_work']['dp_transitions'] /
                    report['baseline_work']['dp_transitions'],
                ideal_simultaneous_unreachable_states=len(gone),
                ideal_simultaneous_saved_exclusive_work=saved,
                ideal_dp_fraction=saved['dp_transitions'] / report['baseline_work']['dp_transitions'])
        top_m = []
        for family in report['top_families']:
            if family['axis'] != 'M':
                continue
            by_count = defaultdict(list)
            for action in family['actions']:
                by_count[len(action['keep'])].append(action)
            counts = []
            for k, actions in sorted(by_count.items()):
                plateaus = Counter(tuple(nodes[a['child']]['points'][-1]) for a in actions)
                counts.append(dict(kept=k, choices=len(actions),
                    flags={flag: sum(a.get(flag, False) for a in actions)
                           for flag in ('ideal_raw', 'ideal_slots', 'ordered_raw', 'ordered_slots')},
                    child_plateaus=[dict(capacity=c, traffic=q, count=n)
                                    for (c, q), n in sorted(plateaus.items())]))
            top_m.append(dict(tile=family['tile'], lacking=family['lacking'],
                              anchor=family['anchor'], group_response=family['parent'],
                              raw_bound_classes=family['classes'], by_kept_count=counts))
        result['cases'][case] = dict(states=report['states'], counts=report['strata']['all'],
            baseline_work=report['baseline_work'], modes=modes, top_M=top_m,
            run_sha256=sha((path / 'run.json').read_bytes()),
            checks=dict(artifacts_and_sources_verified=True, root_archive_equal=True,
                census_count_equal=run.get('census_count_equal'),
                complete_analysis_reproduced=True))
    result['checks'] = dict(complete_cases=len(CASES),
        archive_root_matches=sum(r['checks']['root_archive_equal'] for r in result['cases'].values()),
        old_census_count_matches=sum(r['checks']['census_count_equal'] is True for r in result['cases'].values()),
        analyses_reproduced=len(CASES))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.data)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['checks']))
    for case, row in result['cases'].items():
        print(case, {m: {k: v for k, v in values.items() if k.endswith('_fraction') or 'targets' in k}
                     for m, values in row['modes'].items()})


if __name__ == '__main__':
    main()
