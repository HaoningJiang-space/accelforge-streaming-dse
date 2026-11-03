"""Experimental exact merging of already-reduced FFM frontiers."""
import numpy as np
import pandas as pd
import sympy

from accelforge.mapper.FFM._pareto_df.df_convention import (
    col_used_in_pareto, is_fused_loop_col, is_n_iterations_col, is_objective_col,
)
from accelforge.mapper.FFM._pareto_df import pareto as pareto_module
from accelforge.mapper.FFM._pareto_df.capacity_membership import is_membership_col, membership_mode


def prepare_frontier_schema(frame):
    """Derive static column roles and dtypes; return None for unsupported schema."""
    if pareto_module.TOLERANCE != 0 or not frame.columns.is_unique:
        return None
    # These reducers compare scalar minima. Fall back to the general frontier
    # path, which dispatches to membership superset dominance, never uint64 min.
    if any(is_membership_col(c) for c in frame) or membership_mode() == 'boolean':
        return None
    try:
        columns = list(frame.columns)
        dimensions = [c for c in columns if col_used_in_pareto(c)]
        diffs = [c for c in columns if is_fused_loop_col(c) and not is_n_iterations_col(c)
                 and not (c in dimensions and is_objective_col(c))]
        mins = [c for c in dimensions if c not in diffs]
        compare = diffs + mins
        return (tuple(columns), tuple(diffs), tuple(mins), tuple(frame[c].dtype for c in compare))
    except (TypeError, ValueError):
        return None


def validate_frontier_frame(frame, schema):
    """Validate schema and values without materializing a merge or grouping."""
    if schema is None or pareto_module.TOLERANCE != 0:
        return False
    columns, diffs, mins, dtypes = schema
    if tuple(frame.columns) != columns or frame.isna().to_numpy().any():
        return False
    compare = diffs + mins
    if tuple(frame[c].dtype for c in compare) != dtypes:
        return False
    for c in compare:
        try:
            arr = frame[c].to_numpy()
            if c in diffs and arr.dtype.kind == 'O':
                if not all(isinstance(x, (str, bytes, int, np.integer, sympy.Integer)) for x in arr):
                    return False
            elif arr.dtype.kind not in 'biuf' or not np.isfinite(arr).all():
                return False
        except (TypeError, ValueError):
            return False
    # Match paretoset's numerical matrix conversion, avoiding distinct large
    # integer values collapsing if mixed objectives promote to float.
    if mins and np.result_type(*(frame[c].dtype for c in mins)).kind == 'f':
        for c in mins:
            if frame[c].dtype.kind in 'iu' and len(frame):
                values = frame[c]
                if (values > 2**53).any() or (values.dtype.kind == 'i' and (values < -(2**53)).any()):
                    return False
    return True


def merge_one_boundary(left, right, mins, tile_size=128, stats=None):
    """Merge two validated reduced frontiers known to have the same boundary."""
    nleft, nright = len(left), len(right)
    keep_old, keep_new = np.ones(nleft, bool), np.ones(nright, bool)
    if stats is not None:
        stats['old_rows_scanned'] = stats.get('old_rows_scanned', 0) + nleft
        stats['new_rows_scanned'] = stats.get('new_rows_scanned', 0) + nright
        stats['overlap_groups'] = stats.get('overlap_groups', 0) + 1
        stats['cross_pairs'] = stats.get('cross_pairs', 0) + nleft * nright
    left_values = [left[c].to_numpy() for c in mins]
    right_values = [right[c].to_numpy() for c in mins]
    for oi in range(0, nleft, tile_size):
        for ni in range(0, nright, tile_size):
            na, nb = min(tile_size, nleft-oi), min(tile_size, nright-ni)
            old_le_new = np.ones((na, nb), bool)
            new_le_old = np.ones((na, nb), bool)
            new_strict = np.zeros((na, nb), bool)
            for a, b in zip(left_values, right_values):
                av, bv = a[oi:oi+na, None], b[None, ni:ni+nb]
                old_le_new &= av <= bv
                new_le_old &= bv <= av
                new_strict |= bv < av
            keep_new[ni:ni+nb] &= ~old_le_new.any(axis=0)
            keep_old[oi:oi+na] &= ~(new_le_old & new_strict).any(axis=1)
    frame = pd.concat([left, right], ignore_index=True)
    return frame.iloc[np.flatnonzero(np.concatenate([keep_old, keep_new]))].copy()


def cross_frontier_frame(left, right, tile_size=128, stats=None):
    """Merge reduced frontiers after checking schema, values and boundaries."""
    if tile_size < 1:
        return None
    schema = prepare_frontier_schema(left)
    if not validate_frontier_frame(left, schema) or not validate_frontier_frame(right, schema):
        return None
    columns, diffs, mins, _ = schema
    compare = pd.concat([left[list(diffs)], right[list(diffs)]], ignore_index=True)
    nleft, nright = len(left), len(right)
    if diffs:
        try:
            groups = list(compare.groupby(list(diffs), sort=False, observed=True, dropna=False).indices.values())
        except (TypeError, ValueError):
            return None
    else:
        groups = [np.arange(nleft+nright)]
    if stats is not None:
        stats['old_rows_scanned'] = stats.get('old_rows_scanned', 0) + nleft
        stats['new_rows_scanned'] = stats.get('new_rows_scanned', 0) + nright
    frame = pd.concat([left, right], ignore_index=True)
    outputs = []
    for indices in groups:
        indices = np.asarray(indices)
        old, new = indices[indices < nleft], indices[indices >= nleft]
        if len(old) and len(new):
            outputs.append(merge_one_boundary(frame.iloc[old], frame.iloc[new], mins, tile_size, stats=None))
            if stats is not None:
                stats['overlap_groups'] = stats.get('overlap_groups', 0) + 1
                stats['cross_pairs'] = stats.get('cross_pairs', 0) + len(old)*len(new)
        else:
            outputs.append(frame.iloc[indices])
    return pd.concat(outputs, ignore_index=True) if outputs else frame.iloc[:0].copy()
