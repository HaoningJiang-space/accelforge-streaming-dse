"""Compare count objectives, Boolean membership and uint64 membership end to end.

All use the finite-target event enumerator. Timed phases exclude diagnostics,
query-frontier comparisons and final Mapping re-evaluation. Methods rotate in
one warm process; this is not an independent-per-architecture FFM comparison.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import common
from accelforge.mapper.FFM._pareto_df import pareto
from accelforge.mapper.FFM._pareto_df.capacity_membership import (
    booleanize_exclusions, expand_membership, is_excluded_col, is_membership_col,
)
from accelforge.mapper.FFM._pareto_df.interval_membership import is_interval_col
from accelforge.mapper.FFM._pareto_df.df_convention import col_used_in_pareto


def canonical(frame):
    columns = sorted(frame.columns)
    data = frame[columns].drop_duplicates().sort_values(columns).reset_index(drop=True)
    return {'schema': [[c, str(data[c].dtype)] for c in columns], 'values': data.values.tolist()}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def semantic_frontiers(data, caps):
    common.clear_switches()
    expanded = booleanize_exclusions(expand_membership(data))
    columns = [c for c in expanded.select_dtypes(include=['number', 'bool']) if col_used_in_pareto(c)]
    full = canonical(pareto.makepareto(expanded[columns]))
    cost_columns = [c for c in columns if not is_excluded_col(c)]
    queries = []
    for cap in caps:
        fits = common.rows_for_capacity(data, cap, max(caps))
        queries.append(canonical(pareto.makepareto(fits[cost_columns])))
    return full, queries


def input_stats(pm):
    frames = [g.mappings.data for groups in pm.einsum2pmappings.values() for g in groups]
    members = lambda f: [c for c in f if is_membership_col(c) or is_excluded_col(c)]
    jobs = [j for js in pm.einsum2jobs.values() for j in js]
    return dict(groups=len(frames), rows=sum(len(f) for f in frames),
                interval_groups=sum(any(is_interval_col(c) for c in f) for f in frames),
                interval_rows=sum(len(f) for f in frames if any(is_interval_col(c) for c in f)),
                max_membership_columns=max((len(members(f)) for f in frames), default=0),
                membership_payload_bytes=sum(int(f[members(f)].memory_usage(index=False).sum()) for f in frames),
                numeric_payload_bytes=sum(int(f.select_dtypes(include=['number', 'bool']).memory_usage(index=False).sum()) for f in frames),
                state_expansions=sum(getattr(j, 'target_enumeration_stats', {}).get('state_expansions', 0) for j in jobs),
                expanded_rows=sum(getattr(j, 'target_enumeration_stats', {}).get('expanded_rows', 0) for j in jobs))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arch', choices=('nvdla', 'tpu_v4i'), default='nvdla')
    p.add_argument('--count', type=int, default=64)
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--methods', nargs='+', choices=('counts','boolean','bitset','interval'),
                   default=['counts','boolean','bitset'])
    p.add_argument('--case', choices=('glu','counter'), default='glu')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.count < 2 or a.repeats < 1:
        p.error('count >= 2 and repeats >= 1 required')
    common.af.set_n_parallel_jobs(1)
    params, low, high = ((64, 128, 256), .03125, .25) if a.arch == 'nvdla' else ((256, 512, 1024), .25, 4.)
    case = common.Case('glu', a.arch, params)
    if a.case == 'counter':
        if a.arch != 'nvdla':
            p.error('historical counterexample uses NVDLA')
        case, low, high = common.Case('matmuls','nvdla',(2,4,8)), 64/2**20, 128/2**20
    caps = [low * (high / low)**(i / (a.count - 1)) for i in range(a.count)]
    caps[-1] = high
    report = dict(case=str(case), caps=caps, repeats=a.repeats, jobs=1,
                  python=platform.python_version(), system=platform.platform(),
                  hashseed=os.environ.get('PYTHONHASHSEED'),
                  threads={k: os.environ.get(k) for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMBA_NUM_THREADS')},
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  runs=[], full_frontiers={}, query_frontiers={})
    source_paths = [*Path('accelforge').rglob('*.py'), Path(__file__)]
    report['python_sources_sha256'] = digest({str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in source_paths})
    report['working_tree_dirty'] = bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip())
    a.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        a.output.write_text(json.dumps(report, indent=2) + '\n')

    methods = list(dict.fromkeys(a.methods))
    last_results = {}
    expected = None
    for repeat in range(-1, a.repeats):
        order = methods if repeat < 0 else methods[repeat % len(methods):] + methods[:repeat % len(methods)]
        for mode in order:
            spec = common.build(case, high, common.RU)
            common.clear_switches()
            os.environ.update({**common.capacity_fractions_env(caps),
                               'AF_TARGET_ENUMERATION': 'events', 'AF_CAPACITY_MEMBERSHIP': mode,
                               'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer'})
            start = time.perf_counter()
            pm = common.make_pmappings(spec, print_number_of_pmappings=False)
            make_s = time.perf_counter() - start
            common.clear_switches()
            os.environ.update({'AF_VARIABLE_RESOURCES': 'GlobalBuffer', 'AF_CAPACITY_MEMBERSHIP': mode})
            start = time.perf_counter()
            result = common.join_pmappings(pm)
            join_s = time.perf_counter() - start
            common.clear_switches()
            full, queries = semantic_frontiers(result.data, caps)
            full_id, query_id = digest(full), digest(queries)
            report['full_frontiers'].setdefault(full_id, full)
            report['query_frontiers'].setdefault(query_id, queries)
            if expected is None:
                expected = (full_id, query_id)
            exact = expected == (full_id, query_id)
            row = dict(repeat=repeat, mode=mode, make_s=make_s, join_s=join_s,
                       search_s=make_s + join_s, rows_front=len(result.data),
                       input=input_stats(pm), boolean_frontier=full_id,
                       per_target_frontiers=query_id, exact=exact)
            report['runs'].append(row)
            row['picks'] = common.validate_capacity_picks(case, caps, result.data)
            row['picks_valid'] = all(p['ok'] for p in row['picks'])
            report['all_picks_valid'] = all(r['picks_valid'] for r in report['runs'])
            last_results[mode] = result
            save()
            print('RUN', json.dumps({k:v for k,v in row.items() if k != 'picks'}), flush=True)
            if not exact or not row['picks_valid']:
                return 2
    report['picks'] = {}
    for mode, result in last_results.items():
        report['picks'][mode] = [common.check_pick(case, cap, common.best_row(
            common.rows_for_capacity(result.data, cap, high))) for cap in caps]
    report['all_picks_valid'] &= all(p['ok'] for picks in report['picks'].values() for p in picks)
    report['summary'] = {}
    for mode in methods:
        runs = [r for r in report['runs'] if r['mode'] == mode and r['repeat'] >= 0]
        report['summary'][mode] = {key: statistics.median(r[key] for r in runs) for key in ('make_s', 'join_s', 'search_s')}
        report['summary'][mode]['input'] = runs[-1]['input']
        report['summary'][mode]['rows_front'] = runs[-1]['rows_front']
    report['peak_rss_gb'] = common.peak_rss_gb()
    save()
    print('SUMMARY', json.dumps(report['summary']), flush=True)
    return 0 if report['all_picks_valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
