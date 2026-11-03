"""Controlled K sweep for prefix reuse; not an end-to-end DSE speedup benchmark.

The fixed template has three tile variables and two ordered min-usage fallbacks.
Every target is checked against the plain enumerator before reporting a result.
"""
import argparse
import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import time

import numpy as np
from sympy import Symbol

tiles = importlib.import_module(
    'accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')


def new_job():
    return SimpleNamespace(
        spec=SimpleNamespace(mapper=SimpleNamespace(ffm=SimpleNamespace(
            _count_option_for_mapsapce_size_evaluation=()))),
        n_total_pmappings=1, n_evaluated_pmappings=0, pmapping_keep_rates={},
        log_message=lambda *a: None, log_porp_pmappings_kept=lambda *a: None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('repeats must be positive')
    x, y, z = [Symbol(s, integer=True, positive=True) for s in ('bx', 'by', 'bz')]
    bound = 360
    relations = tiles.SymbolRelations()
    relations.what_tiles_symbol = [(bound, x), (x, y), (y, 1), (bound, z), (z, 1)]
    relations.make_bounds()
    memory = (x * z + y) / (bound * bound + bound)
    objectives = [tiles.Objective('memory', memory, max_value=1),
                  tiles.Objective('usage_a', y / x, min_value=2.,
                                  try_best_if_none_reaches_min=True, only_care_if_valid=True),
                  tiles.Objective('usage_b', 1 / z, min_value=2.,
                                  try_best_if_none_reaches_min=True, only_care_if_valid=True)]
    kwargs = dict(symbols=[x, y, z], what_tiles_symbol=relations)
    report = {'description': __doc__, 'bound': bound, 'runs': []}
    previous = os.environ.get('AF_ENUMERATION_PREFIX_BYTES')
    try:
        for k in (2, 4, 8, 16, 32, 64):
            fractions = np.geomspace(1e-5, 1., k)
            targets = [(memory, float(f)) for f in fractions]
            expected = []
            for formula, limit in targets:
                capacity = tiles.Objective('capacity', formula, max_value=limit, only_care_if_valid=True)
                expected.append(np.unique(tiles.get_tile_shape_choices(
                    objectives[:1] + [capacity] + objectives[1:], job=new_job(), **kwargs), axis=0))
            for repeat in range(args.repeats):
                # Alternate order; symbolic preparation has been warmed by the oracle.
                budgets = (0, 8 * 2**20) if repeat % 2 == 0 else (8 * 2**20, 0)
                for budget in budgets:
                    os.environ['AF_ENUMERATION_PREFIX_BYTES'] = str(budget)
                    job = new_job()
                    start = time.perf_counter()
                    choices, excluded = tiles.get_tile_shape_choices_for_targets(
                        objectives, targets, job=job, **kwargs)
                    elapsed = time.perf_counter() - start
                    for i, oracle in enumerate(expected):
                        np.testing.assert_array_equal(choices[~excluded[:, i]], oracle)
                    report['runs'].append(dict(k=k, repeat=repeat, budget=budget,
                                               seconds=elapsed, candidates=len(choices),
                                               exact_targets=True, **job.enumeration_stats))
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(json.dumps(report, indent=2))
            print(json.dumps({'k': k, 'last': report['runs'][-1]}), flush=True)
    finally:
        if previous is None:
            os.environ.pop('AF_ENUMERATION_PREFIX_BYTES', None)
        else:
            os.environ['AF_ENUMERATION_PREFIX_BYTES'] = previous


if __name__ == '__main__':
    main()
