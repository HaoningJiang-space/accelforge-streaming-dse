"""Experimental shared prefix IDs and per-row formula cache.

Region choices and history remain independent arrays. This isolates whether
sharing evaluation work is worthwhile before changing region representation.
It is not the default FFM mapper and does not claim memory-bounded execution.
"""
from dataclasses import replace

import numpy as np

from research.tracking_audit.parametric_template import RegionEnumerator


class CandidatePool:
    """Stable IDs for an ordered enumeration prefix and its exact dtype."""
    def __init__(self):
        self.ids = {}
        self.count = 0

    def intern(self, done, choices):
        if choices.dtype.hasobject:
            return None
        prefix = (tuple(done), choices.dtype.str, choices.shape[1])
        rows = np.ascontiguousarray(choices)
        result = np.empty(len(rows), dtype=np.int64)
        for i, row in enumerate(rows):
            key = (prefix, row.tobytes())
            if key not in self.ids:
                self.ids[key] = self.count
                self.count += 1
            result[i] = self.ids[key]
        return result


class SharedEvaluationRegions(RegionEnumerator):
    """Reuse elementwise objective values without combining region decisions."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool = CandidatePool()
        self.values = {}
        self.cache_stats = dict(requested_rows=0, evaluated_rows=0, hits=0, fallback_calls=0)

    def evaluate(self, formula, state, minimize=None, maximize=None, exact_evaluation=False):
        choices = state.choices
        if not len(choices) or choices.dtype.hasobject:
            self.cache_stats['fallback_calls'] += 1
            return super().evaluate(formula, state, minimize, maximize, exact_evaluation)
        ids = self.pool.intern(self.done, choices)
        context = (tuple(self.done), formula, minimize, maximize, bool(exact_evaluation), choices.dtype.str)
        cache = self.values.setdefault(context, {})
        # Preserve first-occurrence order and evaluate every new ID exactly once.
        missing = {}
        for i, ident in enumerate(ids):
            ident = int(ident)
            if ident not in cache and ident not in missing:
                missing[ident] = i
        self.cache_stats['requested_rows'] += len(ids)
        if missing:
            positions = np.fromiter(missing.values(), dtype=np.int64)
            subset = replace(state, choices=choices[positions])
            result = super().evaluate(formula, subset, minimize, maximize, exact_evaluation)
            result = np.asarray(result)
            if result.ndim == 0:
                result = np.full(len(positions), result, dtype=result.dtype)
            if result.ndim != 1 or len(result) != len(positions):
                raise ValueError('experimental cache requires an elementwise scalar formula')
            cache.update(zip(missing, result))
            self.cache_stats['evaluated_rows'] += len(positions)
        self.cache_stats['hits'] += len(ids) - len(missing)
        return np.asarray([cache[int(i)] for i in ids])
