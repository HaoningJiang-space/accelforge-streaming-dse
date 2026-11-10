"""Score exploratory cut controls and derive X's conditional residency value."""
import argparse
from collections import Counter
import json
from math import isfinite
from pathlib import Path

from research.index_coupling.analyze_p21_cuts import MENUS
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.run_p21 import CASES, comparison, frontier, intervals


def summarize(directory):
    rows, values, missing, invalid = [], [], [], []
    executions = failed = context_bad = context_count = 0
    menu_exact = Counter()
    seconds = []
    sources = set()
    for i, (shape, depth, reads_x) in enumerate(CASES):
        path = directory / f'case_{i}.json'
        if not path.exists() or not path.stat().st_size:
            missing.append(i)
            continue
        record = json.loads(path.read_text())
        if record['status'] != 'complete':
            invalid.append(dict(case=i, error=record.get('error')))
            continue
        r = record['result']
        if (tuple(r['shape']) != shape or (r['depth'], r['reads_x']) != (depth, reads_x)
                or r['case'] != i or set(r['menus']) != set(MENUS)):
            invalid.append(dict(case=i, error='case identity mismatch'))
            continue
        sources.add(record['source_revision'])
        seconds.append(record['seconds'])
        checks = dict(r['menus'])
        combined = frontier(r['menu_union'] + r['output_resident_lifted'])
        raw_combined = r['menu_union']
        round_one = comparison(combined, r['unrestricted'])
        tail = None
        if depth == 8:
            path = directory / f'tail_{i}.json'
            if not path.exists() or not path.stat().st_size:
                missing.append(f'tail_{i}')
                continue
            tail = json.loads(path.read_text())
            if (tail['status'] != 'complete' or tail['case'] != i
                    or tail['result']['case'] != i
                    or tuple(tail['result']['shape']) != shape
                    or tail['result']['unrestricted'] != r['unrestricted']
                    or set(tail['result']['menus']) != {'streamed_tail'}):
                invalid.append(dict(case=i, error='tail control incomplete'))
                continue
            sources.add(tail['source_revision'])
            seconds.append(tail['seconds'])
            checks.update(tail['result']['menus'])
            combined = frontier(combined + tail['result']['menu_union'])
            raw_combined = frontier(raw_combined + tail['result']['menu_union'])
        for name, m in checks.items():
            context_count += 1
            menu_exact[name] += m['comparison']['exact']
            context_bad += not m['context_equal']
            executions += len(m['replay'])
            failed += sum(not p['exact'] for p in m['replay'])
        final = comparison(combined, r['unrestricted'])
        # Use one common finite capacity domain for the whole refinement ladder.
        stages = dict(frozen=r['frozen'], output_resident=r['output_resident'],
                      outer_context=r['output_resident_lifted'],
                      four_cuts=frontier(r['menu_union']+r['output_resident_lifted']),
                      five_cuts=combined)
        upper = max(p[0] for curve in list(stages.values())+[r['unrestricted']] for p in curve)
        metrics = {}
        for name, points in stages.items():
            above, infeasible, below = [], [], []
            excess = 0
            for c in range(upper+1):
                exact, got = traffic_at(c, r['unrestricted']), traffic_at(c, points)
                if not isfinite(exact):
                    continue
                if got > exact:
                    above.append(c)
                    if isfinite(got):
                        excess += got-exact
                    else:
                        infeasible.append(c)
                elif got < exact:
                    below.append(c)
            metrics[name] = dict(above=above, infeasible=infeasible, below=below,
                                 finite_excess_sum=excess,
                                 tail_excess=points[-1][1]-r['unrestricted'][-1][1])
        rows.append(dict(case=i, shape=shape, operators=depth+2, reads_x=reads_x,
                         common_capacity_upper=upper, stages=metrics,
                         five_menu_only_comparison=comparison(raw_combined, r['unrestricted']),
                         four_cut_comparison=round_one, five_cut_comparison=final))
        original = json.loads((directory.parent/'p21'/f'case_{i:02d}.json').read_text())['result']['interfaces'][0]
        s = original['s']
        cold, resident = original['children']['cold'][1], original['children']['resident'][1]
        upper_h = max(c for c,q in cold+resident)
        finite_values = [(c, traffic_at(c,cold)-traffic_at(c,resident))
                         for c in range(upper_h+1)
                         if isfinite(traffic_at(c,cold)) and isfinite(traffic_at(c,resident))]
        eligible, bad = 0, []
        # Check the generalized threshold on its finite, endpoint-compatible domain.
        for c in original['bare_inequality']['eligible_capacities']:
            a, b, d = traffic_at(c-s,cold), traffic_at(c,cold), traffic_at(c-s,resident)
            if not all(isfinite(q) for q in (a,b,d)):
                continue
            eligible += 1
            opportunity, value = a-b, a-d
            k, sp = traffic_at(c,original['curves']['keep']), traffic_at(c,original['curves']['spill'])
            compare = lambda x,y: (x>y)-(x<y)
            if compare(opportunity, 2*s+value) != compare(k,sp):
                bad.append(c)
        values.append(dict(case=i, reads_x=reads_x, s=s, steps=intervals(finite_values),
                           minimum=min(v for _,v in finite_values), maximum=max(v for _,v in finite_values),
                           generalized_inequality_capacities=eligible, generalized_inequality_errors=bad))
    return dict(expected_cases=16, cases=len(rows), missing=missing, invalid=invalid,
                menu_exact_full_cases=dict(menu_exact),
                four_cut_exact_cases=sum(x['four_cut_comparison']['exact'] for x in rows),
                five_cut_exact_cases=sum(x['five_cut_comparison']['exact'] for x in rows),
                five_menu_only_exact_cases=sum(x['five_menu_only_comparison']['exact'] for x in rows),
                replayed=executions, replay_failures=failed, contexts_checked=context_count,
                context_mismatches=context_bad,
                below_reference=sum(len(v['below']) for x in rows for v in x['stages'].values()),
                threshold_checked_capacities=sum(x['generalized_inequality_capacities'] for x in values),
                threshold_errors=sum(len(x['generalized_inequality_errors']) for x in values),
                summed_case_seconds=sum(seconds), max_case_seconds=max(seconds,default=0),
                source_revisions=sorted(sources), rows=rows, residency_values=values)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    result = summarize(parser.parse_args().directory)
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(1 if result['missing'] or result['invalid'] or result['cases']!=16
                     or result['replay_failures'] or result['context_mismatches']
                     or result['below_reference'] or result['threshold_errors'] else 0)
