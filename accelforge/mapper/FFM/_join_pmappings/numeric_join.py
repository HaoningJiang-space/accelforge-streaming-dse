"""Experimental numeric execution of prepared FFM column additions.

This module does not implement matching, tensor lifetime adjustments, capacity
checks, or Pareto pruning. The caller must retain the original FFM ordering.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ColumnProgram:
    names: tuple[str, ...]
    steps: tuple[tuple[int, int], ...]


def compile_column_program(operations) -> ColumnProgram:
    names = []
    ids = {}

    def col_id(name):
        if name not in ids:
            ids[name] = len(names)
            names.append(name)
        return ids[name]

    steps = tuple((col_id(target), col_id(source)) for target, source in operations)
    return ColumnProgram(tuple(names), steps)


def numeric_inputs(df, program):
    """Copy numeric inputs, returning None if a dtype is unsupported."""
    arrays = []
    for name in program.names:
        if name not in df:
            arrays.append(None)
            continue
        arr = np.ascontiguousarray(df[name].to_numpy(copy=True))
        if arr.dtype.kind not in 'biuf':
            return None
        arrays.append(arr)
    return arrays


def execute_column_program(xp, arrays, program):
    """Run integer-indexed additions on NumPy- or CuPy-compatible arrays."""
    for target, source in program.steps:
        if arrays[source] is None:
            raise ValueError(f'missing source column {program.names[source]}')
        if arrays[target] is None:
            arrays[target] = arrays[source].copy()
            continue
        # Match the tag 1.0 add_to_col dtype-promotion rule, including its
        # mutation of the source column when the two dtypes differ.
        if arrays[target].dtype != arrays[source].dtype:
            arrays[target] = arrays[target].astype(xp.float64)
            arrays[source] = arrays[source].astype(xp.float64)
        arrays[target] = arrays[target] + arrays[source]
    return arrays


def apply_numpy_program(df, program) -> bool:
    arrays = numeric_inputs(df, program)
    if arrays is None:
        return False
    execute_column_program(np, arrays, program)
    for name, arr in zip(program.names, arrays):
        if arr is None:
            raise ValueError(f'column {name} was not produced')
        df[name] = arr
    return True
