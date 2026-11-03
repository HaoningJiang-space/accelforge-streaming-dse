"""Rotated dense/packed-output and late/early Join ablations, all with bitsets."""
import argparse
import copy
from contextlib import contextmanager
import importlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import common
from audit_membership_structure import trace_materialized_pairs
from benchmark_event_join import digest, input_signature
from benchmark_membership import semantic_frontiers, input_stats
from accelforge.mapper.FFM._pareto_df.capacity_membership import validate_membership
from accelforge.mapper.FFM._pareto_df.target_membership import PackedMembership

tiles = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')
frames = importlib.import_module('accelforge.mapper.FFM._join_pmappings.pmapping_dataframe')


@contextmanager
def output_format(dense):
    """Ablate output construction only, without adding another production switch."""
    original = tiles.get_tile_shape_choices_for_targets
    outputs = []

    def enumerate(*args, **kwargs):
        kwargs['membership_format'] = 'excluded' if dense else 'packed'
        result = original(*args, **kwargs)
        if result[1] is not None:
            data = result[1].words if isinstance(result[1], PackedMembership) else result[1]
            outputs.append(dict(shape=list(data.shape), dtype=str(data.dtype), bytes=data.nbytes))
        return result

    tiles.get_tile_shape_choices_for_targets = enumerate
    try:
        yield outputs
    finally:
        tiles.get_tile_shape_choices_for_targets = original


def live_frontiers(data, caps):
    words = validate_membership(data)
    live = (data[list(words)].to_numpy() != 0).any(axis=1)
    return semantic_frontiers(data[live], caps)


def setup_join(mode):
    common.clear_switches()
    os.environ.update({'AF_VARIABLE_RESOURCES': 'GlobalBuffer', 'AF_CAPACITY_MEMBERSHIP': 'bitset',
                       'AF_MEMBERSHIP_JOIN': mode})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=('glu', 'tpu', 'counter', 'mobile'), default='glu')
    p.add_argument('--count', type=int, default=64)
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--join-only', action='store_true', help='generate once, replay frozen input; measures no generation comparison')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.count < 2 or a.repeats < 1:
        p.error('count >= 2 and repeats >= 1 required')
    configurations = {
        'glu': (common.Case('glu', 'nvdla', (64,128,256)), .03125, .25),
        'tpu': (common.Case('glu', 'tpu_v4i', (256,512,1024)), .25, 4.),
        'counter': (common.Case('matmuls', 'nvdla', (2,4,8)), 64/2**20, 128/2**20),
        'mobile': (common.Case('mobilenet', 'nvdla', (1,)), .03125, .25),
    }
    case, low, high = configurations[a.case]
    caps = [low * (high/low)**(i/(a.count-1)) for i in range(a.count)]
    caps[-1] = high
    common.af.set_n_parallel_jobs(1)
    report = dict(case=str(case), caps=caps, repeats=a.repeats, jobs=1, join_only=a.join_only,
                  parent_commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
                  runs=[], semantic_frontiers={}, diagnostics={}, picks={})
    a.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        a.output.write_text(json.dumps(report, indent=2) + '\n')

    def generate(dense):
        common.clear_switches()
        os.environ.update({**common.capacity_fractions_env(caps), 'AF_TARGET_ENUMERATION':'events',
                           'AF_CAPACITY_MEMBERSHIP':'bitset', 'AF_GENERATION_VARIABLE_RESOURCES':'GlobalBuffer'})
        spec = common.build(case, high, common.RU)
        with output_format(dense) as outputs:
            start = time.perf_counter()
            pm = common.make_pmappings(spec, print_number_of_pmappings=False)
            elapsed = time.perf_counter()-start
        return pm, elapsed, outputs

    frozen = generate(False)[0] if a.join_only else None
    methods = ['direct_late','direct_early'] if a.join_only else ['dense_late','direct_late','direct_early']
    expected, input_id, last = None, None, {}
    for repeat in range(-1, a.repeats):
        order = methods if repeat < 0 else methods[repeat % len(methods):] + methods[:repeat % len(methods)]
        for method in order:
            if a.join_only:
                pm, make_s, outputs = copy.deepcopy(frozen), 0., []
            else:
                pm, make_s, outputs = generate(method == 'dense_late')
            signature = digest(input_signature(pm))
            if input_id is None:
                input_id = signature
            if signature != input_id:
                raise AssertionError('output construction changed the generated Join input')
            setup_join(method.split('_')[1])
            start = time.perf_counter()
            result = common.join_pmappings(pm)
            join_s = time.perf_counter()-start
            full, queries = live_frontiers(result.data, caps)
            ids = digest(full), digest(queries)
            report['semantic_frontiers'].setdefault(ids[0], dict(full=full, queries=queries))
            if expected is None:
                expected = ids
            row = dict(repeat=repeat, method=method, make_s=make_s, join_s=join_s, search_s=make_s+join_s,
                       input_signature=signature, input=input_stats(pm), output_payloads=outputs,
                       full_live_frontier=ids[0], per_target_frontiers=ids[1], exact=ids==expected,
                       rows_front=len(result.data))
            report['runs'].append(row)
            last[method] = result
            save()
            print('RUN', json.dumps({k:v for k,v in row.items() if k not in ('output_payloads','input')}), flush=True)
            if not row['exact']:
                return 2
    if frozen is None:
        frozen = generate(False)[0]
    # Separate instrumented replay measures REAL rows entering Reservation composition.
    for mode in ('late', 'early'):
        pm = copy.deepcopy(frozen)
        setup_join(mode)
        resource_rows = []
        original = frames.PmappingDataframe.adjust_reservations

        def adjust(self, *args, **kwargs):
            resource_rows.append(len(self.data))
            return original(self, *args, **kwargs)

        frames.PmappingDataframe.adjust_reservations = adjust
        try:
            with trace_materialized_pairs() as pairs:
                result = common.join_pmappings(pm)
        finally:
            frames.PmappingDataframe.adjust_reservations = original
        report['diagnostics'][mode] = dict(pair_joins=pairs, resource_rows=resource_rows,
            matched_pairs=sum(r['matched_pairs'] for r in pairs),
            no_common_target=sum(r['no_common_target'] for r in pairs),
            resource_composition_rows=sum(resource_rows),
            fully_dead_block_pairs=sum(r['matched_pairs'] for r in pairs if r['matched_pairs']==r['no_common_target']))
        if tuple(map(digest, live_frontiers(result.data, caps))) != expected:
            raise AssertionError('diagnostic replay changed the semantic frontier')
        save()
    for method, result in last.items():
        report['picks'][method] = [common.check_pick(case, cap, common.best_row(
            common.rows_for_capacity(result.data, cap, high))) for cap in caps]
    report['all_picks_valid'] = all(p['ok'] for picks in report['picks'].values() for p in picks)
    report['summary'] = {}
    for method in methods:
        rows = [r for r in report['runs'] if r['method']==method and r['repeat']>=0]
        report['summary'][method] = {k:statistics.median(r[k] for r in rows) for k in ('make_s','join_s','search_s')}
    save()
    print('SUMMARY',json.dumps(report['summary']),flush=True)
    return 0 if report['all_picks_valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
