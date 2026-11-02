"""Experimental persistent frontier partitioned by FFM output boundary."""
import numpy as np
import pandas as pd

from accelforge.mapper.FFM._pareto_df.df_convention import (
    col_used_in_pareto, is_fused_loop_col, is_n_iterations_col, is_objective_col,
)
from accelforge.mapper.FFM._join_pmappings.incremental_pareto import cross_frontier_frame


class BoundaryFrontier:
    """Each input must already be Pareto-reduced. Unsupported inputs return False."""
    def __init__(self, stats=None):
        self.groups = {}
        self.columns = None
        self.dtypes = None
        self.diffs = None
        self.template = None
        self.stats = stats if stats is not None else {}

    def add(self, data):
        # Reuse the exact existing fast-path guards before changing state.
        # This validates even when no old boundary overlaps the new chunk.
        checked = cross_frontier_frame(data.iloc[:0], data)
        if checked is None:
            return False
        cols = list(data.columns)
        dims = [c for c in cols if col_used_in_pareto(c)]
        diffs = [c for c in cols if is_fused_loop_col(c) and not is_n_iterations_col(c)
                 and not (c in dims and is_objective_col(c))]
        comparison_cols = list(dict.fromkeys(diffs + dims))
        dtype_signature = tuple(data[c].dtype for c in comparison_cols)
        if self.columns is not None and (cols != self.columns or dtype_signature != self.dtypes):
            return False
        if self.columns is None:
            self.columns, self.dtypes, self.diffs = cols, dtype_signature, diffs
            self.template = data.iloc[:0].copy()
        if not len(data):
            return True
        try:
            groups = (list(data.groupby(diffs, sort=False, observed=True, dropna=False).indices.items())
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
            merged = cross_frontier_frame(old, new, stats=self.stats)
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
