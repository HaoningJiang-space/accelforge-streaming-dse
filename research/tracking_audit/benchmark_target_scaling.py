"""Capacity-event K sweep with every target checked against independent enumeration.

Counts actual batch expansion calls/rows, padding calls and Pareto calls. These
are execution work units, not unique nodes of the full FFM search space.
"""
import argparse
from contextlib import contextmanager
import importlib
import json
import os
from pathlib import Path
import time

import numpy as np
from sympy import Symbol

from benchmark_prefix_scaling import new_job

tiles = importlib.import_module(
    'accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')


@contextmanager
def work_counters():
    result = dict(expansions=0, expanded_rows=0, padding_calls=0, pareto_calls=0)
    original = {name: getattr(tiles, name) for name in
                ('_expand_symbol_choices', 'get_padded_choices', 'makepareto_numpy')}

    def expand(*args, **kwargs):
        value = original['_expand_symbol_choices'](*args, **kwargs)
        result['expansions'] += 1
        result['expanded_rows'] += len(value)
        return value

    def padding(*args, **kwargs):
        result['padding_calls'] += 1
        return original['get_padded_choices'](*args, **kwargs)

    def pareto(*args, **kwargs):
        result['pareto_calls'] += 1
        return original['makepareto_numpy'](*args, **kwargs)

    tiles._expand_symbol_choices, tiles.get_padded_choices, tiles.makepareto_numpy = expand, padding, pareto
    try:
        yield result
    finally:
        for name, function in original.items():
            setattr(tiles, name, function)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    a = parser.parse_args()
    if a.repeats < 1:
        parser.error('repeats must be positive')
    x, y, z = [Symbol(s, positive=True, integer=True) for s in ('tx', 'ty', 'tz')]
    bound = 360
    relations = tiles.SymbolRelations()
    relations.what_tiles_symbol = [(bound, x), (x, y), (y, 1), (bound, z), (z, 1)]
    relations.make_bounds()
    memory = (x * z + y) / (bound * bound + bound)
    objectives = [tiles.Objective('memory', memory, max_value=1),
                  tiles.Objective('first_usage', y / x, min_value=2., only_care_if_valid=True,
                                  try_best_if_none_reaches_min=True),
                  tiles.Objective('second_usage', 1 / z, min_value=2., only_care_if_valid=True,
                                  try_best_if_none_reaches_min=True)]
    kwargs = dict(symbols=[x, y, z], what_tiles_symbol=relations)
    switches = ('AF_TARGET_ENUMERATION', 'AF_ENUMERATION_PREFIX_BYTES', 'AF_ENUMERATION_PARETO_BYTES')
    previous = {k: os.environ.get(k) for k in switches}
    report = dict(description=__doc__, bound=bound, runs=[])
    try:
        os.environ['AF_ENUMERATION_PREFIX_BYTES'] = '0'
        for k in (2, 4, 8, 16, 32, 64):
            targets = [(memory, float(b)) for b in np.geomspace(1e-5, 1., k)]
            # The plain enumerator has neither target grouping nor execution caches.
            expected = []
            for formula, limit in targets:
                cap = tiles.Objective('capacity', formula, max_value=limit, only_care_if_valid=True)
                expected.append(np.unique(tiles.get_tile_shape_choices(
                    objectives[:1] + [cap] + objectives[1:], job=new_job(), **kwargs), axis=0))
            methods = [('independent', 0), ('independent', 8 * 2**20), ('events', 0)]
            for repeat in range(a.repeats):
                for mode, budget in methods[repeat % 3:] + methods[:repeat % 3]:
                    os.environ['AF_TARGET_ENUMERATION'] = mode
                    os.environ['AF_ENUMERATION_PARETO_BYTES'] = str(budget)
                    j = new_job()
                    with work_counters() as work:
                        start = time.perf_counter()
                        choices, excluded = tiles.get_tile_shape_choices_for_targets(objectives, targets, job=j, **kwargs)
                        elapsed = time.perf_counter() - start
                    for i, oracle in enumerate(expected):
                        np.testing.assert_array_equal(choices[~excluded[:, i]], oracle)
                    assert choices.dtype == np.concatenate(expected).dtype
                    record = dict(k=k, repeat=repeat, mode=mode, pareto_bytes=budget,
                                  seconds=elapsed, candidates=len(choices), exact_targets=True,
                                  work=work, events=getattr(j, 'target_enumeration_stats', None))
                    report['runs'].append(record)
                    a.output.parent.mkdir(parents=True, exist_ok=True)
                    a.output.write_text(json.dumps(report, indent=2) + '\n')
            runs = [r for r in report['runs'] if r['k'] == k]
            reference = next(r['work'] for r in runs if r['mode'] == 'independent' and r['pareto_bytes'] == 0)
            event = next(r for r in runs if r['mode'] == 'events')
            assert reference['expansions'] == event['events']['target_expansions']
            assert reference['expanded_rows'] == event['events']['target_expanded_rows']
            assert reference['pareto_calls'] == event['events']['target_pareto_calls']
            print(json.dumps(dict(k=k, reference=reference, shared=event['work'])), flush=True)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == '__main__':
    main()
