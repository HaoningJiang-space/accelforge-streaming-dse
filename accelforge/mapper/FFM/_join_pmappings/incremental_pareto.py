"""Experimental exact cross-frontier comparison for identical numeric schemas.

Inputs must already be FFM Pareto frontiers. Unsupported schemas return None,
so the caller can use the original general-purpose concat and Pareto path.
"""
import numpy as np
import pandas as pd
import sympy

from accelforge.mapper.FFM._pareto_df.df_convention import (
    col_used_in_pareto, is_fused_loop_col, is_n_iterations_col, is_objective_col,
)
from accelforge.mapper.FFM._pareto_df import pareto as pareto_module


def cross_frontier_frame(left, right, tile_size=128, stats=None):
    """Return the exact union frontier, or None when the fast path is unsupported.

    Only old-versus-new comparisons are performed. Equal rows prefer the old
    provenance; both inputs must already be internally reduced. Pairwise scratch
    matrices are at most tile_size squared, never the full cross product.
    """
    if pareto_module.TOLERANCE != 0 or tile_size < 1:
        return None
    if list(left.columns) != list(right.columns) or not left.columns.is_unique:
        return None
    if left.isna().to_numpy().any() or right.isna().to_numpy().any():
        return None
    columns = list(left.columns)
    dimensions = [c for c in columns if col_used_in_pareto(c)]
    diffs = [c for c in columns if is_fused_loop_col(c) and not is_n_iterations_col(c)
             and not (c in dimensions and is_objective_col(c))]
    mins = [c for c in dimensions if c not in diffs]
    compare_columns = diffs + mins
    if any(left[c].dtype != right[c].dtype for c in compare_columns):
        return None
    for frame in (left, right):
        for c in compare_columns:
            try:
                arr = frame[c].to_numpy()
                if c in diffs and arr.dtype.kind == 'O':
                    if not all(isinstance(x, (str, bytes, int, np.integer, sympy.Integer)) for x in arr):
                        return None
                elif arr.dtype.kind not in 'biuf' or not np.isfinite(arr).all():
                    return None
            except (TypeError, ValueError):
                return None
    # paretoset can coerce mixed numeric columns to float when it receives a
    # DataFrame. Fall back when this could collapse distinct integer values.
    compare = pd.concat([left[compare_columns], right[compare_columns]], ignore_index=True)
    if mins and np.result_type(*(compare[c].dtype for c in mins)).kind == 'f':
        for c in mins:
            if compare[c].dtype.kind in 'iu' and len(compare):
                values = compare[c]
                if (values > 2**53).any() or (values.dtype.kind == 'i' and (values < -(2**53)).any()):
                    return None
    nleft, nright = len(left), len(right)
    keep_old, keep_new = np.ones(nleft, bool), np.ones(nright, bool)
    if diffs:
        try:
            groups = list(compare.groupby(diffs, sort=False, observed=True, dropna=False).indices.values())
        except (TypeError, ValueError):
            return None
    else:
        groups = [np.arange(nleft + nright)]
    if stats is not None:
        stats['old_rows_scanned'] = stats.get('old_rows_scanned', 0) + nleft
        stats['new_rows_scanned'] = stats.get('new_rows_scanned', 0) + nright
    for indices in groups:
        indices = np.asarray(indices)
        old = indices[indices < nleft]
        new = indices[indices >= nleft]
        if not len(old) or not len(new):
            continue
        if stats is not None:
            stats['overlap_groups'] = stats.get('overlap_groups', 0) + 1
            stats['cross_pairs'] = stats.get('cross_pairs', 0) + len(old) * len(new)
        # Each pair is compared in bounded tiles. Strict inequality protects the
        # old row when comparison coordinates are equal.
        for oi in range(0, len(old), tile_size):
            a = old[oi:oi + tile_size]
            for ni in range(0, len(new), tile_size):
                b = new[ni:ni + tile_size]
                old_le_new = np.ones((len(a), len(b)), bool)
                new_le_old = np.ones((len(a), len(b)), bool)
                new_strict = np.zeros((len(a), len(b)), bool)
                for c in mins:
                    values = compare[c].to_numpy()
                    av, bv = values[a, None], values[None, b]
                    old_le_new &= av <= bv
                    new_le_old &= bv <= av
                    new_strict |= bv < av
                keep_new[b - nleft] &= ~old_le_new.any(axis=0)
                keep_old[a] &= ~(new_le_old & new_strict).any(axis=1)
    frame = pd.concat([left, right], ignore_index=True)
    return frame.iloc[np.flatnonzero(np.concatenate([keep_old, keep_new]))].copy()
