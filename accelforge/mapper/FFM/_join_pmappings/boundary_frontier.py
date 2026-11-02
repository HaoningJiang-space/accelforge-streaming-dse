"""Experimental persistent frontier partitioned by FFM output boundary."""
import numpy as np
import pandas as pd

from accelforge.mapper.FFM._join_pmappings.incremental_pareto import (
    prepare_frontier_schema, validate_frontier_frame, merge_one_boundary,
)


class BoundaryFrontier:
    """Each input must already be Pareto-reduced. Unsupported inputs return False."""
    def __init__(self, stats=None):
        self.groups = {}
        self.columns = None
        self.dtypes = None
        self.diffs = None
        self.schema = None
        self.template = None
        self.stats = stats if stats is not None else {}

    def add(self, data):
        # Column roles and dtype checks are prepared once. Only values in the
        # incoming frame are checked; validation does not execute a merge.
        schema = self.schema if self.schema is not None else prepare_frontier_schema(data)
        if not validate_frontier_frame(data, schema):
            return False
        cols, diffs, mins, dtypes = schema
        if self.columns is None:
            self.columns, self.dtypes, self.diffs, self.schema = cols, dtypes, diffs, schema
            self.template = data.iloc[:0].copy()
        if not len(data):
            return True
        try:
            groups = (list(data.groupby(list(diffs), sort=False, observed=True, dropna=False).indices.items())
                      if diffs else [((), np.arange(len(data)))])
        except (TypeError, ValueError):
            return False
        updates = {}
        for key, indices in groups:
            # Uniform keys across pandas versions for single-column grouping.
            if diffs and len(diffs) == 1 and not isinstance(key, tuple):
                key = (key,)
            new = data.iloc[indices].copy()
            old = self.groups.get(key)
            if old is None:
                updates[key] = new
                self.stats['new_groups'] = self.stats.get('new_groups', 0) + 1
                continue
            merged = merge_one_boundary(old, new, mins, stats=self.stats)
            if merged is None:
                return False
            updates[key] = merged
            self.stats['touched_groups'] = self.stats.get('touched_groups', 0) + 1
        self.groups.update(updates)
        return True

    def finish(self):
        if self.template is None:
            return None
        if not self.groups:
            return self.template.copy()
        return pd.concat(list(self.groups.values()), ignore_index=True)
