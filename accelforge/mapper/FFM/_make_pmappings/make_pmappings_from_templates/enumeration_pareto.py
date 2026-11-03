"""Template-local reuse of identical exact numerical Pareto requests.

Masks contain positions, not candidate IDs or capacity membership. Callers apply
them to their own candidates. No target's fallback or pruning history is shared.
"""
from collections import OrderedDict

import numpy as np


class EnumerationParetoCache:
    def __init__(self, budget_bytes):
        if budget_bytes < 0:
            raise ValueError('AF_ENUMERATION_PARETO_BYTES must be nonnegative')
        self.budget_bytes = budget_bytes
        self._entries = OrderedDict()
        self.stats = dict(requests=0, computations=0, hits=0, requested_rows=0,
                          computed_rows=0, evictions=0, payload_bytes=0,
                          peak_payload_bytes=0)

    def prune(self, matrix, goals, tolerance, compute):
        self.stats['requests'] += 1
        self.stats['requested_rows'] += len(matrix)
        key = None
        # Check the entry payload before copying its key. Eviction below bounds
        # retained numeric payload, not temporary copies or whole-process memory.
        size = matrix.nbytes + len(matrix)
        if (self.budget_bytes and size <= self.budget_bytes and tolerance == 0
                and matrix.dtype.kind in 'biuf' and np.isfinite(matrix).all()):
            key = (tuple(goals), matrix.dtype.str, matrix.shape, matrix.tobytes(order='C'))
            if key in self._entries:
                mask, retained = self._entries.pop(key)
                self._entries[key] = (mask, retained)
                self.stats['hits'] += 1
                return mask
        mask = compute()
        self.stats['computations'] += 1
        self.stats['computed_rows'] += len(matrix)
        if key is not None:
            # This cache has one contract: the ordered boolean mask of dirty=True
            # makepareto_numpy. A different backend result is safely bypassed.
            if not isinstance(mask, np.ndarray) or mask.dtype != np.bool_ or mask.shape != (len(matrix),):
                return mask
            while self._entries and (self.stats['payload_bytes'] + size > self.budget_bytes
                                     or len(self._entries) >= 1024):
                _, (_, removed) = self._entries.popitem(last=False)
                self.stats['payload_bytes'] -= removed
                self.stats['evictions'] += 1
            mask.flags.writeable = False
            self._entries[key] = (mask, size)
            self.stats['payload_bytes'] += size
            self.stats['peak_payload_bytes'] = max(self.stats['peak_payload_bytes'],
                                                  self.stats['payload_bytes'])
        return mask
