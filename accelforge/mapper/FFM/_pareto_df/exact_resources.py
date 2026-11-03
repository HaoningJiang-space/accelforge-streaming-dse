"""Integer-bit resource accounting. Normalized reservations are output views only.

Old captured frames without capacity metadata retain their original units. New
model frames carry absolute bits through the existing reservation lifecycle.
"""
from fractions import Fraction
from functools import lru_cache
import math
import os

import numpy as np
import sympy
from sympy.printing.numpy import NumPyPrinter

CAPACITY_PREFIX = 'resource_capacity_bits<SEP>'
PUBLIC_CAPACITY_PREFIX = 'capacity_reference_bits<SEP>'
BITS_PREFIX = 'reservation_bits<SEP>'
MAX_EXACT = 2**52


class ExactResourceError(RuntimeError):
    """Unsupported exact expression/range; never silently defer feasibility."""


def enabled():
    mode = os.environ.get('AF_RESOURCE_UNITS', 'bits')
    if mode not in ('bits', 'legacy'):
        raise ValueError('AF_RESOURCE_UNITS must be bits or legacy')
    return mode == 'bits'


def capacity_column(memory):
    return CAPACITY_PREFIX + str(memory)


def is_capacity_column(column):
    return isinstance(column, str) and column.startswith(CAPACITY_PREFIX)


def integer_bits(value):
    if not math.isfinite(value) or value < 0 or value != int(value) or value > MAX_EXACT:
        raise ExactResourceError('resource bits must be integral, nonnegative and <= 2**52')
    return int(value)


def capacity_bits(value):
    """An integer occupancy fits a fractional capacity iff it fits its floor."""
    if not math.isfinite(value) or value < 0:
        raise ExactResourceError('finite nonnegative capacity required')
    return integer_bits(math.floor(value))


def capacity(frame, memory):
    column = capacity_column(memory)
    if column not in frame:
        return 1  # Legacy normalized capture.
    values = frame[column].unique()
    if len(values) > 1:
        raise ExactResourceError(f'inconsistent capacity for {memory}')
    return integer_bits(values[0]) if len(values) else 0


def check_units(frames):
    schemas = [{c for c in f if is_capacity_column(c)} for f in frames]
    if any(s != schemas[0] for s in schemas):
        raise ExactResourceError('cannot combine absolute-bit and legacy/different resource schemas')
    for c in schemas[0]:
        values = {integer_bits(v) for f in frames for v in f[c].unique()}
        if len(values) > 1:
            raise ExactResourceError(f'cannot combine different capacities: {c}')


class _Printer(NumPyPrinter):
    def _print_Rational(self, expr):
        return f'Fraction({expr.p}, {expr.q})'

    def _print_Float(self, expr):
        # Resource expressions must originate in exact model counts. Integral
        # constants written as 8.0 are harmless; do not guess other coefficients.
        if expr % 1 != 0:
            raise ExactResourceError(f'inexact coefficient in resource expression: {expr}')
        return str(int(expr))

    def _print_Pow(self, expr):
        base, exponent = expr.args
        if not exponent.is_Integer:
            raise ExactResourceError(f'unsupported resource power: {expr}')
        if exponent < 0:
            return f'(Fraction(1,1) / ({self._print(base)} ** {int(-exponent)}))'
        return f'({self._print(base)} ** {int(exponent)})'

    def _print_Max(self, expr):
        return 'exact_max(' + ','.join(map(self._print,expr.args)) + ')'

    def _print_Min(self, expr):
        return 'exact_min(' + ','.join(map(self._print,expr.args)) + ')'

    def _print_ceiling(self, expr):
        return f'exact_ceil({self._print(expr.args[0])})'

    def _print_floor(self, expr):
        return f'exact_floor({self._print(expr.args[0])})'


@lru_cache(maxsize=4096)
def _compile(symbols, expression):
    modules = dict(Fraction=Fraction,
        exact_max=lambda *a: np.maximum.reduce(np.broadcast_arrays(*a)),
        exact_min=lambda *a: np.minimum.reduce(np.broadcast_arrays(*a)),
        exact_ceil=np.frompyfunc(math.ceil,1,1), exact_floor=np.frompyfunc(math.floor,1,1))
    return sympy.lambdify(symbols, expression, modules=[modules,'numpy'],printer=_Printer())


def evaluate(expression, bindings):
    expression = sympy.sympify(expression)
    symbols = tuple(sorted(expression.free_symbols,key=str))
    values = []
    for symbol in symbols:
        value = np.asarray(bindings[symbol], dtype=object)
        # Enumeration may have promoted its integer Tile union to float64 due
        # to an empty target. Convert only exact integral assignments.
        value = np.frompyfunc(lambda x: int(x) if x == int(x) else Fraction(x),1,1)(value)
        values.append(value)
    return _compile(symbols,expression)(*values)


def bit_array(expression, bindings, nrows):
    values = np.broadcast_to(evaluate(expression,bindings),(nrows,))
    return np.fromiter((integer_bits(v) for v in values),dtype=np.int64,count=nrows)


def comparison_values(values):
    """Embed exact local comparison values only if float64 preserves their order."""
    values = np.asarray(values,dtype=object)
    unique = np.unique(values)
    converted = np.asarray(unique,dtype=np.float64)
    if not np.isfinite(converted).all() or (np.diff(converted) <= 0).any():
        raise ExactResourceError('exact prefix objectives cannot be ordered safely by the numeric Pareto backend')
    return np.asarray(values,dtype=np.float64)


def target_bits(size, fraction):
    """Decode an integer target when its ratio round-trips exactly; else floor.

    This concerns input target syntax, never resource feasibility tolerance.
    Physical targets can avoid ratios entirely via AF_GENERATION_CAPACITY_BITS.
    """
    size = integer_bits(size)
    nearest = round(float(fraction)*size)
    if size and float(fraction) == nearest/size:
        return nearest
    return math.floor(Fraction.from_float(float(fraction))*size)


def validate_reservations(frame):
    """Check before numeric Pareto or conversion to a public normalized view.

    Inputs are limited to 2**52; binary sums fit exactly in float64 as well as
    int64. Reject larger intermediate states rather than silently rounding.
    """
    memories = {c[len(CAPACITY_PREFIX):] for c in frame if is_capacity_column(c)}
    for c in frame:
        if c.startswith('reservation<SEP>') and c.split('<SEP>')[1] in memories:
            checked_values(frame[c].to_numpy())


def checked_values(values, signed=False):
    """Bound each arithmetic step before its result can become a later operand."""
    a = np.asarray(values)
    lower = -MAX_EXACT if signed else 0
    if (a.dtype.kind not in 'iuf' or not np.isfinite(a).all()
            or (a < lower).any() or (a > MAX_EXACT).any()
            or (a != np.floor(a)).any()):
        raise ExactResourceError('invalid or unsupported integer-bit reservation')
    return a.astype(np.int64, copy=False)


def public_frame(frame):
    """Retain exact bits and add normalized compatibility views at the API edge."""
    validate_reservations(frame)
    result = frame.copy()
    capacities = {c[len(CAPACITY_PREFIX):]:capacity(frame,c[len(CAPACITY_PREFIX):])
                  for c in frame if is_capacity_column(c)}
    for c in list(frame):
        if c.startswith('reservation<SEP>'):
            memory = c.split('<SEP>')[1]
            if memory in capacities:
                raw = BITS_PREFIX + c[len('reservation<SEP>'):]
                result[raw] = frame[c].astype(np.int64)
                size = capacities[memory]
                result[c] = frame[c].astype(np.float64)/size if size else 0.
    for memory,size in capacities.items():
        result[PUBLIC_CAPACITY_PREFIX+memory] = np.int64(size)
        result = result.drop(columns=[capacity_column(memory)])
    return result
