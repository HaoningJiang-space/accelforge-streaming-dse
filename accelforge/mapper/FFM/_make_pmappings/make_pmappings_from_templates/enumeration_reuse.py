"""Explicit serial DSE scope for reuse of pure tile-enumeration operations.

This shares neither selected mappings nor fallback/Pareto histories. A prefix
expansion is reused only for identical ordered assignments, symbol relations,
and tiling mode. Every architecture still executes all its own constraints.
The byte budget bounds retained numeric/key payload, not Python overhead/RSS.
"""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar

import numpy as np

_current = ContextVar('ffm_enumeration_reuse', default=None)


def current():
    return _current.get()


class EnumerationReuse:
    def __init__(self, budget_bytes=64 * 2**20, max_compiled=2048):
        if budget_bytes < 0 or max_compiled < 0:
            raise ValueError('reuse budgets must be nonnegative')
        self.budget_bytes, self.max_compiled = budget_bytes, max_compiled
        self.entries, self.compiled = OrderedDict(), OrderedDict()
        self.stats = dict(expansion_requests=0, expansions=0, expansion_hits=0,
                          cross_target_hits=0, requested_rows=0, expanded_rows=0,
                          cross_target_rows=0, compile_requests=0, compilations=0,
                          compile_hits=0, cross_target_compile_hits=0,
                          payload_bytes=0, peak_payload_bytes=0, evictions=0)
        self._target = None
        self._token = None

    def __enter__(self):
        from accelforge.util import get_n_parallel_jobs
        if get_n_parallel_jobs() != 1:
            raise ValueError('EnumerationReuse currently requires one worker')
        if current() is not None or self._token is not None:
            raise ValueError('EnumerationReuse scopes cannot nest')
        self._token = _current.set(self)
        return self

    def __exit__(self, *exc):
        _current.reset(self._token)
        self._token = None
        self.entries.clear()
        self.compiled.clear()
        self.stats['payload_bytes'] = 0

    @contextmanager
    def target(self, label):
        """Label observations for attribution; labels never affect cache validity."""
        old, self._target = self._target, label
        try:
            yield self
        finally:
            self._target = old

    def expand(self, symbol, prefix, done, relations, imperfect, compute):
        from .symbol_relations import SymbolRelations
        self.stats['expansion_requests'] += 1
        key = None
        prefix_bytes = 0 if prefix is None else prefix.nbytes
        # Fail closed for extensions that may add dependencies to the relation API.
        if (type(relations) is SymbolRelations and self.budget_bytes
                and prefix_bytes <= self.budget_bytes
                and (prefix is None or prefix.dtype.kind in 'biuf')):
            relation_key = (tuple(relations.what_tiles_symbol),
                            tuple(relations.tile_shape_and_initial),
                            tuple((s, tuple(values)) for s, values in relations.delta_choices),
                            tuple(relations.bounds))
            content = None if prefix is None else (prefix.dtype.str, prefix.shape,
                                                   prefix.tobytes(order='C'))
            key = (symbol, tuple(done), relation_key, imperfect, content)
            if key in self.entries:
                result, size, owner = self.entries.pop(key)
                self.entries[key] = (result, size, owner)
                self.stats['expansion_hits'] += 1
                self.stats['requested_rows'] += len(result)
                if owner != self._target:
                    self.stats['cross_target_hits'] += 1
                    self.stats['cross_target_rows'] += len(result)
                # Read-only views prevent callers from modifying cached arrays.
                return result.view()
        result = compute()
        self.stats['expansions'] += 1
        self.stats['expanded_rows'] += len(result)
        self.stats['requested_rows'] += len(result)
        size = prefix_bytes + result.nbytes
        if key is not None and size <= self.budget_bytes:
            while self.entries and (self.stats['payload_bytes'] + size > self.budget_bytes
                                    or len(self.entries) >= 4096):
                _, (_, removed, _) = self.entries.popitem(last=False)
                self.stats['payload_bytes'] -= removed
                self.stats['evictions'] += 1
            result.flags.writeable = False
            self.entries[key] = (result, size, self._target)
            self.stats['payload_bytes'] += size
            self.stats['peak_payload_bytes'] = max(self.stats['peak_payload_bytes'],
                                                  self.stats['payload_bytes'])
            return result.view()
        return result

    def compile(self, symbols, formula, float_type, compiler):
        self.stats['compile_requests'] += 1
        key = (tuple(symbols), formula, np.dtype(float_type).str)
        try:
            hash(key)
        except TypeError:
            self.stats['compilations'] += 1
            return compiler()
        if key in self.compiled:
            result, owner = self.compiled.pop(key)
            self.compiled[key] = (result, owner)
            self.stats['compile_hits'] += 1
            if owner != self._target:
                self.stats['cross_target_compile_hits'] += 1
            return result
        result = compiler()
        self.stats['compilations'] += 1
        if self.max_compiled:
            if len(self.compiled) >= self.max_compiled:
                self.compiled.popitem(last=False)
            self.compiled[key] = (result, self._target)
        return result
