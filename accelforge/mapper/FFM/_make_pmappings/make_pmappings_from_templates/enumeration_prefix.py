"""Bounded reuse of exact tile-prefix expansions within a single template.

This is an execution cache, not a union of target-specific fallback states. The
caller owns constraints and history independently for every target. Keys include
the complete ordered prefix, so equal sets in different orders are not conflated.
The budget counts retained array/key payload, not Python overhead or process RSS.
"""
from collections import OrderedDict

import numpy as np


class EnumerationPrefixCache:
    def __init__(self, budget_bytes: int):
        if budget_bytes < 0:
            raise ValueError("AF_ENUMERATION_PREFIX_BYTES must be nonnegative")
        self.budget_bytes = budget_bytes
        self._entries = OrderedDict()
        self.stats = dict(requests=0, expansions=0, hits=0, requested_rows=0,
                          expanded_rows=0, evictions=0, payload_bytes=0,
                          peak_payload_bytes=0)

    def expand(self, symbol, symbols_enumerated, prefix, compute):
        """Reuse a pure expansion, for fixed symbol relations and enumeration mode.

        Instances must not cross templates or change relations/IMPERFECT mode.
        Cached results are read-only. Budget zero executes the reference path
        while collecting the same counters, without serializing prefix arrays.
        """
        self.stats['requests'] += 1
        key = None
        prefix_bytes = 0 if prefix is None else prefix.nbytes
        if self.budget_bytes and prefix_bytes <= self.budget_bytes:
            # Exact bytes, not a digest: no hash-collision correctness assumption.
            content = None if prefix is None else (prefix.dtype.str, prefix.shape,
                                                   prefix.tobytes(order='C'))
            key = (symbol, tuple(symbols_enumerated), content)
            if key in self._entries:
                result, size = self._entries.pop(key)
                self._entries[key] = (result, size)
                self.stats['hits'] += 1
                self.stats['requested_rows'] += len(result)
                return result

        result = compute()
        self.stats['expansions'] += 1
        self.stats['expanded_rows'] += len(result)
        self.stats['requested_rows'] += len(result)
        size = prefix_bytes + result.nbytes
        if key is not None and size <= self.budget_bytes:
            # Bound the number of empty/tiny entries as well as numeric payload.
            while self._entries and (self.stats['payload_bytes'] + size > self.budget_bytes
                                     or len(self._entries) >= 1024):
                _, (_, old_size) = self._entries.popitem(last=False)
                self.stats['payload_bytes'] -= old_size
                self.stats['evictions'] += 1
            result.flags.writeable = False
            self._entries[key] = (result, size)
            self.stats['payload_bytes'] += size
            self.stats['peak_payload_bytes'] = max(self.stats['peak_payload_bytes'],
                                                  self.stats['payload_bytes'])
        return result
