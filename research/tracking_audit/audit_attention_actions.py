"""Trace the selected Attention mappings from local rows through reconstruction."""
import argparse
import copy
import json
import math
import importlib
from unittest.mock import patch
from contextlib import nullcontext
from pathlib import Path

from accelforge.frontend.mapping import Mapping, Sequential
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import row2pmappings
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, rows_fitting, mapping_structure, save


def numbers(row):
    return {c: float(row[c]) for c in row.index
            if any(s in c for s in ('action<SEP>', 'energy<SEP>', 'latency<SEP>'))
            or c in ('Total<SEP>energy', 'Total<SEP>latency')}


def reconstruct_stages(callback):
    parts = row2pmappings(callback.row, callback.einsum_names, callback.rank_variable_bounds)
    yield 'local_branches', Mapping(nodes=[Sequential(nodes=copy.deepcopy(parts))])
    parts = copy.deepcopy(parts)
    for part in parts:
        part._beautify_loops(callback.rank_variable_bounds)
    while len(parts) > 1:
        nshared, selected = 0, 0
        for i, part in enumerate(parts):
            shared = max((part._get_n_shared_loops(p) for p in parts[i+1:]), default=0)
            if shared > nshared:
                nshared, selected = shared, i
        parts[selected] = parts[selected]._merge(parts.pop(selected+1), nshared)
    mapping = Mapping(nodes=parts[0].nodes)
    yield 'merge', copy.deepcopy(mapping)
    for operation in ('_elevate_persistent_nodes_above_splits', '_elevate_tensor_holders_above_splits',
                      '_propagate_reservations_between_splits', '_consolidate_tensor_holders',
                      '_consolidate_reservations', '_move_tensor_holders_above_reservations',
                      '_remove_reservations_for_tolls'):
        getattr(mapping, operation)()
        yield operation, copy.deepcopy(mapping)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--legacy-matching', action='store_true',
                        help='diagnostic replay of the pre-fix matching bug')
    args = parser.parse_args()
    common.af.set_n_parallel_jobs(1)
    case = common.Case('attention', 'nvdla', (128, 1, 64))
    metrics = common.RU | common.af.Metrics.ACTIONS
    spec = build(case, (64, 96), 131072, metrics)
    module = importlib.import_module('accelforge.mapper.FFM._join_pmappings.join_pmappings')
    replay = patch.object(module, '_with_compatibility', lambda group, compatibility: group)
    with replay if args.legacy_matching else nullcontext():
        result, stats = common.search(spec, join_env={'AF_VARIABLE_RESOURCES': 'GlobalBuffer'})
    report = {'base': common.effective_config(case), 'legacy_matching': args.legacy_matching,
              'search': stats, 'cases': []}
    for cap in (8192, 24576):
        row = common.best_row(rows_fitting(result.data, cap))
        callback = row['Total<SEP>mapping']
        record = {'capacity_bytes': cap, 'search': numbers(row), 'stages': [],
                  'local_mappings': [mapping_structure(p) for p in row2pmappings(
                      callback.row, callback.einsum_names, callback.rank_variable_bounds)]}
        report['cases'].append(record)
        for name, mapping in reconstruct_stages(callback):
            target = build(case, (64, 96), cap, metrics)
            target.model.metrics = metrics
            target.mapping = copy.deepcopy(mapping)
            stage = {'name': name, 'mapping': mapping_structure(mapping)}
            try:
                evaluated = common.evaluate_mapping(target).data
                if len(evaluated) != 1:
                    raise ValueError(f'expected one row, got {len(evaluated)}')
                stage['values'] = numbers(evaluated.iloc[0])
                all_columns = record['search'].keys() | stage['values'].keys()
                stage['delta_from_search'] = {c: stage['values'].get(c, 0) - record['search'].get(c, 0)
                    for c in sorted(all_columns)
                    if abs(stage['values'].get(c, 0) - record['search'].get(c, 0)) > 1e-15}
                print(cap, name, {c:v for c,v in stage['delta_from_search'].items()
                                   if c.startswith('Total') or 'action<SEP>' in c}, flush=True)
            except Exception as error:
                stage['error'] = str(error)
                print(cap, name, 'ERROR', str(error), flush=True)
            record['stages'].append(stage)
            save(args.output, report)
        final = record['stages'][-1].get('values', {})
        record['actions_match'] = bool(final) and all(
            final.get(c, 0) == record['search'].get(c, 0)
            for c in final.keys() | record['search'].keys() if 'action<SEP>' in c)
        record['costs_match'] = bool(final) and all(
            math.isclose(final[c], record['search'][c], rel_tol=1e-6, abs_tol=0)
            for c in ('Total<SEP>energy', 'Total<SEP>latency'))
    report['all_final_valid'] = all(c['actions_match'] and c['costs_match'] for c in report['cases'])
    save(args.output, report)
    if not args.legacy_matching and not report['all_final_valid']:
        raise AssertionError('fixed matching still has an action/cost discrepancy')


if __name__ == '__main__':
    main()
