"""Exact intervals of DECLARED target indices, not continuous capacity regions.

Every frame uses either this two-column codec or bitsets. Noncontiguous masks
fall back to bitsets; mixed-codec Join/concat also use bitsets, never interval hulls.
"""
from functools import lru_cache
import json
import math

import numpy as np

PREFIX = 'capacity_interval<SEP>'
LOWER_PREFIX = PREFIX + 'lo<SEP>'
UPPER_COLUMN = PREFIX + 'hi'


def is_interval_col(column):
    return isinstance(column, str) and column.startswith(PREFIX)


@lru_cache(maxsize=2048)
def decode_interval(column):
    try:
        if not column.startswith(LOWER_PREFIX):
            raise ValueError()
        memory, labels = json.loads(column[len(LOWER_PREFIX):])
        if not isinstance(memory, str) or not memory or not isinstance(labels, list) or not 1 <= len(labels) < 2**32:
            raise ValueError()
        fractions = [float(x) for x in labels]
        if (any(not math.isfinite(x) or not 0 < x <= 1 for x in fractions)
                or labels != [repr(x) for x in fractions]
                or fractions != sorted(set(fractions))):
            raise ValueError()
        return memory, tuple(labels)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError('invalid finite interval membership schema') from error


def validate_interval(frame):
    columns = [c for c in frame if is_interval_col(c)]
    lowers = [c for c in columns if c.startswith(LOWER_PREFIX)]
    if len(columns) != 2 or len(lowers) != 1 or UPPER_COLUMN not in columns:
        raise ValueError('finite interval requires one lower/schema column and one upper column')
    lo = lowers[0]
    _, labels = decode_interval(lo)
    for c in (lo, UPPER_COLUMN):
        if frame[c].dtype != np.dtype('uint32'):
            raise ValueError('interval endpoints must remain uint32 target indices')
    lower, upper = frame[lo].to_numpy(), frame[UPPER_COLUMN].to_numpy()
    valid = ((lower < upper) & (upper <= len(labels))) | ((lower == 0) & (upper == 0))
    if not valid.all():
        raise ValueError('invalid interval bounds; empty membership must be [0,0)')
    return lo, UPPER_COLUMN


def intervalize_columns(words):
    """Return interval columns iff EVERY row is contiguous; otherwise return None."""
    from .capacity_membership import decode_column
    entries, memories = [], set()
    for column, values in words.items():
        memory, labels = decode_column(column)
        memories.add(memory)
        entries.extend((float(label), label, values, bit) for bit, label in enumerate(labels))
    if len(memories) != 1:
        return None
    entries.sort(key=lambda entry: entry[0])
    labels = [entry[1] for entry in entries]
    column = LOWER_PREFIX + json.dumps([next(iter(memories)), labels], separators=(',', ':'))
    decode_interval(column)
    n = len(entries[0][2])
    lower, upper = np.zeros(n, dtype=np.uint32), np.zeros(n, dtype=np.uint32)
    previous, seen = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
    for i, (_, _, word, bit) in enumerate(entries):
        allowed = ((word >> np.uint64(bit)) & np.uint64(1)).astype(bool)
        starts = allowed & ~previous
        if (starts & seen).any():
            return None  # A hull would incorrectly admit targets in the hole.
        lower[starts] = i
        upper[allowed] = i + 1
        seen |= allowed
        previous = allowed
    return {column: lower, UPPER_COLUMN: upper}


def interval_to_words(frame):
    """Lossless fallback for mixed-codec operations, with no NxK Boolean table."""
    from .capacity_membership import PREFIX as WORD_PREFIX
    lo, hi = validate_interval(frame)
    memory, labels = decode_interval(lo)
    result = frame.drop(columns=[lo, hi]).copy()
    lower = frame[lo].to_numpy().astype(np.int64)
    upper = frame[hi].to_numpy().astype(np.int64)
    for start in range(0, len(labels), 64):
        a = np.clip(lower - start, 0, 64).astype(np.uint64)
        b = np.clip(upper - start, 0, 64).astype(np.uint64)
        # uint64 shift by 64 gives 0; unsigned subtraction produces all 64 bits.
        word = ((np.uint64(1) << b) - np.uint64(1)) ^ ((np.uint64(1) << a) - np.uint64(1))
        column = WORD_PREFIX + json.dumps([memory, list(labels[start:start + 64])], separators=(',', ':'))
        result[column] = word
    return result


def align_membership_frames(frames):
    """Normalize mixed codecs only after proving their declared domains agree."""
    from .capacity_membership import validate_membership, decode_column
    schemas = [validate_membership(f) for f in frames]
    if not schemas or all(s == schemas[0] for s in schemas):
        return frames
    domains = []
    for frame, schema in zip(frames, schemas):
        if any(is_interval_col(c) for c in schema):
            memory, labels = decode_interval(schema[0])
            entries = [(memory, label) for label in labels]
        else:
            entries = [(memory, label) for c in schema for memory, labels in [decode_column(c)] for label in labels]
        domains.append(tuple(sorted(entries)))
    if any(domain != domains[0] for domain in domains):
        raise ValueError('cannot combine different capacity membership domains')
    return [interval_to_words(f) if any(is_interval_col(c) for c in s) else f
            for f, s in zip(frames, schemas)]
