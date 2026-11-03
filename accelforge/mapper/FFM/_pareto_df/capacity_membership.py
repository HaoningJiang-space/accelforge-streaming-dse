"""Finite capacity membership: uint64 words, intersection and superset dominance.

Column names carry the ordered target labels, so pandas joins/copies do not rely
on fragile DataFrame attrs. A 1 bit means policy membership, not capacity fit;
Reservation feasibility is still checked independently by FFM.
"""
from functools import lru_cache
import json
import math
import os

import numpy as np
from .target_membership import PackedMembership

PREFIX = 'capacity_membership<SEP>'
EXCLUDED_PREFIX = 'Total<SEP>capacity_excluded<SEP>'


def membership_mode():
    mode = os.environ.get('AF_CAPACITY_MEMBERSHIP', 'counts')
    if mode not in ('counts', 'boolean', 'bitset'):
        raise ValueError('AF_CAPACITY_MEMBERSHIP must be counts, boolean or bitset')
    return mode


def is_membership_col(column):
    return isinstance(column, str) and column.startswith(PREFIX)


def is_excluded_col(column):
    return isinstance(column, str) and column.startswith(EXCLUDED_PREFIX)


@lru_cache(maxsize=2048)
def decode_column(column):
    if not is_membership_col(column):
        raise ValueError('not a capacity membership column')
    try:
        memory, labels = json.loads(column[len(PREFIX):])
        if not isinstance(memory, str) or not memory or not isinstance(labels, list) or not 1 <= len(labels) <= 64:
            raise ValueError()
        fractions = [float(s) for s in labels]
        if (any(not math.isfinite(f) or not 0 < f <= 1 for f in fractions)
                or labels != [repr(f) for f in fractions]
                or fractions != sorted(set(fractions))):
            raise ValueError()
        return memory, tuple(labels)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError('invalid capacity membership schema') from error


def pack_exclusions(memory, fractions, excluded, nrows):
    """Label packed output, or pack the reference Boolean exclusion matrix.

    Packed input uses original target order. The usual sorted-target case shares
    word views without decoding them; arbitrary target order is permuted by bits.
    """
    order = sorted(range(len(fractions)), key=lambda i: float(fractions[i]))
    labels = [repr(float(fractions[i])) for i in order]
    if len(set(labels)) != len(labels):
        raise ValueError('duplicate capacity targets')
    packed = excluded if isinstance(excluded, PackedMembership) else None
    if packed is not None:
        if packed.n_targets != len(labels) or packed.words.shape[0] != nrows:
            raise ValueError('packed output does not match target/row count')
        packed.__post_init__()
    elif excluded is not None:
        excluded = np.asarray(excluded)
        if excluded.dtype != np.bool_ or excluded.shape != (nrows, len(labels)):
            raise ValueError('exclusions must be a boolean row/target matrix')
    result = {}
    for start in range(0, len(labels), 64):
        chunk = labels[start:start + 64]
        column = PREFIX + json.dumps([memory, chunk], separators=(',', ':'))
        decode_column(column)
        if packed is not None and order == list(range(len(labels))):
            result[column] = packed.words[:, start // 64]
            continue
        word = np.zeros(nrows, dtype=np.uint64)
        for bit, source in enumerate(order[start:start + 64]):
            if packed is not None:
                allowed = (packed.words[:, source // 64] >> np.uint64(source % 64)) & np.uint64(1)
            else:
                allowed = np.ones(nrows, dtype=np.uint64) if excluded is None else (~excluded[:, source]).astype(np.uint64)
            word |= allowed << np.uint64(bit)
        result[column] = word
    return result


def validate_membership(frame):
    if not frame.columns.is_unique:
        raise ValueError('duplicate columns in membership frame')
    columns = sorted(c for c in frame if is_membership_col(c))
    if columns and any(is_excluded_col(c) for c in frame):
        raise ValueError('mixed packed membership and exclusion counts')
    seen = set()
    for column in columns:
        memory, labels = decode_column(column)
        keys = {(memory, s) for s in labels}
        if seen & keys:
            raise ValueError('overlapping capacity membership words')
        seen.update(keys)
        if frame[column].dtype != np.dtype('uint64'):
            raise ValueError('membership words must remain uint64; float conversion loses bits')
        if len(labels) < 64 and (frame[column].to_numpy() >> np.uint64(len(labels))).any():
            raise ValueError('membership word has bits outside its target schema')
    return tuple(columns)


def validate_same_membership(frames):
    if not frames:
        raise ValueError('no membership frames to combine')
    schemas = [validate_membership(frame) for frame in frames]
    if any(schema != schemas[0] for schema in schemas[1:]):
        raise ValueError('cannot combine different capacity membership schemas')
    return schemas[0]


def membership_for_target(frame, memory, fraction):
    """Return allowed rows; missing targets fail instead of bypassing membership."""
    label = repr(float(fraction))
    for column in validate_membership(frame):
        name, labels = decode_column(column)
        if name == memory and label in labels:
            bit = np.uint64(labels.index(label))
            return ((frame[column].to_numpy() >> bit) & np.uint64(1)).astype(bool)
    raise ValueError(f'shared search lacks membership for {memory}:{label}')


def expand_membership(frame):
    """Diagnostic Boolean oracle representation; never recover exclusion counts."""
    columns = validate_membership(frame)
    result = frame.drop(columns=list(columns)).copy()
    decoded = {}
    for column in columns:
        memory, labels = decode_column(column)
        word = frame[column].to_numpy()
        for bit, label in enumerate(labels):
            decoded[EXCLUDED_PREFIX + memory + '<SEP>' + label] = (
                1 - ((word >> np.uint64(bit)) & np.uint64(1))).astype(np.float32)
    if decoded:
        import pandas as pd
        result = pd.concat([result, pd.DataFrame(decoded, index=frame.index)], axis=1)
    return result


def booleanize_exclusions(frame):
    """Unpacked baseline for the same membership partial order as packed words."""
    columns = [c for c in frame if is_excluded_col(c)]
    if not columns:
        return frame
    values = frame[columns].to_numpy()
    if values.dtype.kind not in 'biuf' or not np.isfinite(values).all() or (values < 0).any() or (values != np.floor(values)).any():
        raise ValueError('capacity exclusions must be finite nonnegative integers')
    if not (values > 1).any():
        return frame
    result = frame.copy()
    for column in columns:
        result[column] = (frame[column] != 0).astype(frame[column].dtype)
    return result


def intersect_join_membership(frame, columns, *, filter_empty=False):
    """Compose validated Join words, optionally discard target-dead pairs early.

    Input schemas/dtypes are checked on both sides before pd.merge. Capacity and
    Reservation composition still run normally for surviving rows. This is a
    post-materialization filter, not a memory-bounded candidate Join.
    """
    live = np.zeros(len(frame), dtype=bool) if filter_empty else None
    for column in columns:
        frame[column] = frame[column].to_numpy() & frame[column + '_RIGHT_MERGE'].to_numpy()
        if filter_empty:
            live |= frame[column].to_numpy() != 0
    if filter_empty and columns and not live.all():
        return frame.iloc[np.flatnonzero(live)].copy()
    return frame


def _frontier_mask(costs, masks):
    """Window skyline with stable first-equal provenance; O(n) index storage."""
    n, dimensions = costs.shape
    words = masks.shape[1]
    window = np.empty(n, dtype=np.int64)
    size = 0
    for candidate in range(n):
        dominated = False
        for k in range(size):
            previous = window[k]
            no_worse = True
            for w in range(words):
                if masks[previous, w] & masks[candidate, w] != masks[candidate, w]:
                    no_worse = False
                    break
            if no_worse:
                for d in range(dimensions):
                    if costs[previous, d] > costs[candidate, d]:
                        no_worse = False
                        break
            if no_worse:
                dominated = True
                break
        if dominated:
            continue
        kept = 0
        for k in range(size):
            previous = window[k]
            no_worse = True
            for w in range(words):
                if masks[candidate, w] & masks[previous, w] != masks[previous, w]:
                    no_worse = False
                    break
            if no_worse:
                for d in range(dimensions):
                    if costs[candidate, d] > costs[previous, d]:
                        no_worse = False
                        break
            if not no_worse:
                window[kept] = previous
                kept += 1
        window[kept] = candidate
        size = kept + 1
    keep = np.zeros(n, dtype=np.bool_)
    for k in range(size):
        keep[window[k]] = True
    return keep


# Numba is optional in paretoset/AccelForge. Keep a correct CPU fallback without
# adding a mandatory dependency, and never use fastmath for dominance decisions.
try:
    from numba import njit
except ImportError:
    frontier_mask = _frontier_mask
else:
    frontier_mask = njit(cache=True)(_frontier_mask)


def make_membership_pareto(frame, columns, split_by_cols, tolerance):
    from .df_convention import is_fused_loop_col, is_n_iterations_col, is_objective_col
    if tolerance != 0:
        raise ValueError('packed membership requires zero Pareto tolerance')
    words = validate_membership(frame)
    if not set(words).issubset(columns):
        raise ValueError('Pareto columns cannot omit packed target membership')
    if set(words).intersection(split_by_cols):
        raise ValueError('packed membership cannot be a scalar boundary key')
    diffs = set(split_by_cols) | {c for c in frame if is_fused_loop_col(c) and not is_n_iterations_col(c)}
    costs, boundaries = [], []
    for c in frame:
        if c in words:
            continue
        is_cost = c in columns and (is_objective_col(c) or c not in diffs)
        if is_cost and (frame[c].dtype.kind not in 'biuf' or not np.isfinite(frame[c].to_numpy()).all()):
            raise ValueError('packed Pareto requires finite numeric costs')
        if c in diffs and frame[c].isna().any():
            raise ValueError('packed Pareto requires non-null boundary keys')
        if frame[c].nunique() <= 1:
            continue
        if c in columns and is_objective_col(c):
            costs.append(c)
        elif c in diffs:
            boundaries.append(c)
        elif c in columns:
            costs.append(c)
    # Keep uint64 words separate from floating costs, including bit 63.
    masks = frame[list(words)].to_numpy(dtype=np.uint64)
    numeric = frame[costs].to_numpy() if costs else np.empty((len(frame), 0), dtype=np.float64)
    if numeric.dtype.kind not in 'biuf' or not np.isfinite(numeric).all():
        raise ValueError('packed Pareto requires finite numeric costs')
    if numeric.dtype.kind == 'f':
        for c in costs:
            if frame[c].dtype.kind in 'iu' and ((frame[c] > 2**53).any() or (frame[c] < -(2**53)).any()):
                raise ValueError('mixed floating costs would lose integer precision')
        if numeric.dtype.itemsize < 4:
            numeric = numeric.astype(np.float32)
    keep = np.zeros(len(frame), dtype=bool)
    groups = (frame.groupby(boundaries, sort=False, observed=True, dropna=False).indices.values()
              if boundaries else [np.arange(len(frame))])
    for indices in groups:
        keep[indices] = frontier_mask(numeric[indices], masks[indices])
    return frame.iloc[np.flatnonzero(keep)]
