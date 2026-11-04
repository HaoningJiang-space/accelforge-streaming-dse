"""Offline, intrusive diagnostics for duplicated region-enumerator prefixes.

The profiled execution retains peak snapshots and optionally hashes formula
inputs; timings and RSS must not be compared to normal benchmark runs.
"""
import argparse
import copy
import json
import time
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

import numpy as np

from research.tracking_audit import benchmark_parametric_template as b
from research.tracking_audit import parametric_operator as op
from research.tracking_audit import parametric_template as region_module
from research.tracking_audit.parametric_template import Box, RegionEnumerator


class ProfiledRegions(RegionEnumerator):
    def __init__(self, *args, formula_distinct=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.snapshots = {}
        self.formulas = {}
        self.formula_distinct = formula_distinct
        self.times = defaultdict(float)
        self.mask_bytes = 0
        self.hash_bytes = 0

    def record_peak(self, states):
        super().record_peak(states)
        depth = len(self.done)
        rows = sum(len(s.choices) for s in states)
        if depth not in self.snapshots or rows > self.snapshots[depth][0]:
            # Arrays are immutable after assignment in the current interpreter.
            # Retaining references deliberately makes this an intrusive profile.
            self.snapshots[depth] = (rows, tuple(s.choices for s in states))

    def mask_rows(self, state, valid):
        result = super().mask_rows(state, valid)
        self.mask_bytes += result.choices.nbytes
        return result

    def merge(self, states):
        self.hash_bytes += sum(s.choices.nbytes for s in states if len(s.choices))
        start = time.perf_counter()
        try:
            return super().merge(states)
        finally:
            self.times['merge_inclusive_s'] += time.perf_counter() - start

    def constrain(self, state, objective, complete):
        start = time.perf_counter()
        try:
            return super().constrain(state, objective, complete)
        finally:
            self.times['constrain_inclusive_s'] += time.perf_counter() - start

    def pareto(self, state, goals):
        start = time.perf_counter()
        try:
            return super().pareto(state, goals)
        finally:
            self.times['pareto_inclusive_s'] += time.perf_counter() - start

    def evaluate(self, formula, state, minimize=None, maximize=None, exact_evaluation=False):
        key = (tuple(map(str, self.done)), str(formula), str(minimize), str(maximize),
               bool(exact_evaluation), state.choices.dtype.str)
        info = self.formulas.setdefault(key, {'calls': 0, 'rows': 0, 'inputs': set()})
        info['calls'] += 1
        info['rows'] += len(state.choices)
        if self.formula_distinct:
            # Full row and context, not just the formula's apparent free symbols:
            # padding and exact numeric dtype can affect evaluation.
            rows = np.ascontiguousarray(state.choices)
            if rows.dtype.hasobject:
                info['inputs'].update(tuple(row) for row in rows.tolist())
            else:
                unique = np.unique(rows, axis=0)
                info['inputs'].update(row.tobytes() for row in unique)
        start = time.perf_counter()
        try:
            return super().evaluate(formula, state, minimize, maximize, exact_evaluation)
        finally:
            self.times['evaluate_inclusive_s'] += time.perf_counter() - start

    def report(self):
        depths = []
        for depth, (rows, arrays) in sorted(self.snapshots.items()):
            # Do not combine dtypes: dtype participates in the state semantics.
            by_dtype = defaultdict(list)
            for arr in arrays:
                by_dtype[(arr.dtype.str, arr.shape[1])].append(arr)
            unique = sum(len(np.unique(np.concatenate(parts), axis=0)) for parts in by_dtype.values())
            depths.append(dict(depth=depth, live_row_occurrences=rows, unique_prefix_rows=unique,
                               duplicate_factor=rows / unique if unique else None,
                               states=len(arrays)))
        contexts = [dict(depth=len(k[0]), formula=k[1], minimize=k[2], maximize=k[3],
                         exact=k[4], dtype=k[5], calls=v['calls'], formula_rows_evaluated=v['rows'],
                         unique_formula_inputs=len(v['inputs']) if self.formula_distinct else None)
                    for k,v in self.formulas.items()]
        return dict(depth_peaks=depths, formula_contexts=contexts, timing=self.times,
                    mask_result_bytes=self.mask_bytes, merge_input_bytes=self.hash_bytes,
                    counters=self.stats)


def run(output, indices, formula_distinct):
    b.common.af.set_n_parallel_jobs(1)
    b.common.clear_switches()
    from research.tracking_audit.benchmark_parametric_operator import FAMILY
    programs = op.prepare_all(256, tuple(hi for _, hi in FAMILY.ranges))
    reports = []
    for index in indices:
        program = programs[index]
        objectives, axes = b.parameterize(program)
        lo, hi = FAMILY.ranges[2]
        family = Box((*FAMILY.ranges[:2], (8*lo, 8*hi)))
        engine = ProfiledRegions(b.tiles, objectives, family, axes=axes,
                                 formula_distinct=formula_distinct, **copy.deepcopy(program.kwargs))
        original = b.tiles._expand_symbol_choices
        original_split = region_module.split_events
        def expand(*args, **kwargs):
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                engine.times['expand_inclusive_s'] += time.perf_counter() - start
        def split(*args, **kwargs):
            start = time.perf_counter()
            try:
                return original_split(*args, **kwargs)
            finally:
                engine.times['split_events_inclusive_s'] += time.perf_counter() - start
        with patch.object(b.tiles, '_expand_symbol_choices', expand), patch.object(region_module, 'split_events', split):
            engine.build()
        report = engine.report()
        report['template_index'] = index
        reports.append(report)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(dict(formula_distinct=formula_distinct, templates=reports), indent=2)+'\n')
        print(json.dumps(dict(template=index, peak=report['depth_peaks'], timing=report['timing'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--templates', type=int, nargs='+', default=[1, 3])
    parser.add_argument('--formula-distinct', action='store_true')
    args = parser.parse_args()
    run(args.output, args.templates, args.formula_distinct)
