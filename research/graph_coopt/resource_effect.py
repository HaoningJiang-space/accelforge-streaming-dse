"""Bounded max-plus shadow of a restricted native terminal resource program.

No reservations are allocated/freed, aliases adjusted or operator order changed.
Finite resources use exact nonnegative bits; unbounded legacy resources must be
identically zero. Consumer resource coordinates are nonnegative variables.
"""
import itertools
from numbers import Integral

import pandas as pd

from accelforge.mapper.FFM._pareto_df.df_convention import (
    col2nameloop, is_fused_loop_col, is_left_col, nameloop2col,
)
from accelforge.mapper.FFM._pareto_df import exact_resources as exact


class UnsupportedEffect(ValueError):
    pass


def normalize(terms, budget=128):
    terms = sorted(set(terms))
    if not terms or len({len(t[0]) for t in terms}) != 1 or any(
            not isinstance(v, Integral) or v < 0 for t in terms for v in (*t[0], t[1])):
        raise UnsupportedEffect('nonnegative_integer_effect_required')
    if len(terms) > budget:
        raise UnsupportedEffect('effect_term_budget')
    # Larger coefficients and intercept dominate on the nonnegative orthant.
    return tuple(t for t in terms if not any(
        t != u and t[1] <= u[1] and all(a <= b for a, b in zip(t[0], u[0]))
        for u in terms))


def add(a, b):
    return normalize((tuple(x + y for x, y in zip(ca, cb)), va + vb)
                     for (ca, va), (cb, vb) in itertools.product(a, b))


def maximum(polynomials):
    return normalize(t for poly in polynomials for t in poly)


def covered(a, b):
    """Sufficient (not necessary) proof a(x)<=b(x) for EVERY x>=0."""
    if len(a[0][0]) != len(b[0][0]):
        raise UnsupportedEffect('effect_variable_arity_mismatch')
    return all(any(va <= vb and all(x <= y for x, y in zip(ca, cb))
                   for cb, vb in b) for ca, va in a)


def evaluate(poly, values):
    return max(v + sum(c * x for c, x in zip(coefficients, values))
               for coefficients, v in poly)


def compile_effects(left, right, plan):
    """Translate native prepared column operations and terminal max folding.

    Returns one resource-function dictionary per producer row. This translation
    has its own restricted contract; validation against native rows is separate.
    """
    if plan['shared_to_free'] or plan['live_to_alloc']:
        raise UnsupportedEffect('reservation_adjustment_not_compiled')
    if any(a == b for a, b in zip(plan['left_match'], plan['right_match'])):
        raise UnsupportedEffect('coalesced_join_key_schema')
    if any(c.endswith('_RIGHT_MERGE') for frame in (left.data, right.data) for c in frame):
        raise UnsupportedEffect('preexisting_merge_suffix')
    resource_names = {col2nameloop(c)[0] for frame in (left.data, right.data)
                      for c in frame if col2nameloop(c) is not None}
    finite = {r for r in resource_names if exact.capacity_column(r) in left.data and
              exact.capacity_column(r) in right.data}
    for frame in (left.data, right.data):
        for c in frame:
            parsed = col2nameloop(c)
            if parsed is None:
                continue
            resource, level = parsed
            if level < 0:
                raise UnsupportedEffect('negative_reservation_level')
            if resource in finite:
                if any(value < 0 or value != int(value) or value > exact.MAX_EXACT for value in frame[c]):
                    raise UnsupportedEffect('nonexact_resource_operand')
            elif any(value != 0 for value in frame[c]):
                raise UnsupportedEffect('nonzero_resource_without_exact_metadata')
    variables = tuple(sorted(c for c in right.data if col2nameloop(c) is not None and
                             col2nameloop(c)[0] in finite))
    zero_coeff = (0,) * len(variables)
    constant = lambda value: ((zero_coeff, int(value)),)
    def variable(c):
        return ((tuple(int(i == variables.index(c)) for i in range(len(variables))), 0),)
    columns = list(left.data) + [c + '_RIGHT_MERGE' if c in left.data else c for c in right.data]
    columns = [c for c in columns if not is_fused_loop_col(c) or c in plan['remaining_symbols']]
    operations, dropped = left._prepare_column_operations(
        right, pd.DataFrame(columns=columns), plan['max_nloops'], plan['min_nloops'])
    if sorted((a, b) for a, b in operations if a.startswith('Total<SEP>')) != [
            ('Total<SEP>energy', 'Total<SEP>energy_RIGHT_MERGE'),
            ('Total<SEP>latency', 'Total<SEP>latency_RIGHT_MERGE')]:
        raise UnsupportedEffect('nonadditive_native_cost_program')
    profiles = []
    for position in range(len(left.data)):
        env = {c: constant(left.data[c].iloc[position]) for c in left.data if col2nameloop(c) is not None}
        for c in right.data:
            if col2nameloop(c) is None:
                continue
            target = c + '_RIGHT_MERGE' if c in left.data else c
            env[target] = variable(c) if c in variables else constant(0)
        for target, source in operations:
            if col2nameloop(target) is not None:
                if source not in env:
                    raise UnsupportedEffect('unknown_resource_operand')
                env[target] = add(env.get(target, constant(0)), env[source])
        for c in dropped:
            env.pop(c, None)
        # Exactly mirror free_to_loop_index(-1): right levels below the
        # deepest are redundant by the native nested-reservation invariant.
        for resource in sorted(resource_names):
            lhs = sorted(c for c in env if col2nameloop(c)[0] == resource and is_left_col(c))
            rhs = sorted((c for c in env if col2nameloop(c)[0] == resource and not is_left_col(c)
                          and col2nameloop(c)[1] >= 1), key=lambda c: col2nameloop(c)[1])
            selected = [*lhs, *rhs[-1:]]
            target = nameloop2col(resource, 0)
            if selected:
                if target in env:
                    selected.append(target)
                new = maximum(env[c] for c in selected)
                for c in [*lhs, *rhs]:
                    env.pop(c, None)
                env[target] = new
        if any(col2nameloop(c)[1] != 0 or is_left_col(c) for c in env):
            raise UnsupportedEffect('unclosed_terminal_resource_state')
        profiles.append(env)
    return variables, profiles
