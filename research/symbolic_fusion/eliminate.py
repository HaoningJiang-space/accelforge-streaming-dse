"""Eliminate stage-internal decisions with a fixed, sufficient separator.

No calls to FFM generation/model/Join, or the independent event interpreter.
All pruning is within this finite grammar. s fixes T1 geometry, T2 identity and
lifetime, loop alignment, ownership, layout, and future allocation obligations.
"""
from fractions import Fraction
from itertools import product
from .model import State, Plan, combine, frontier


def flat(family, capacity=None, cache_factors=False):
    states = []; cache = {}; stats = dict(full_plans=0, compositions=0, budget_rejections=0, factor_evaluations=0)
    for plan in family.plans():
        state = State(0, 0, Fraction(0), ())
        for stage, (k, j) in enumerate(plan.tiles):
            key = family.factor_key(stage, plan.stripe, k, j) if cache_factors else None
            if not cache_factors or key not in cache:
                factor = family.factor(stage, plan.stripe, k, j)
                stats['factor_evaluations'] += 1
                if cache_factors:
                    cache[key] = factor
            else:
                factor = cache[key]
            state = combine(state, factor)
            stats['compositions'] += 1
        stats['full_plans'] += 1
        if capacity is None or state.peak <= capacity:
            states.append((state, plan))
        else:
            stats['budget_rejections'] += 1
    return [(s, next(p for t, p in states if t is s)) for s in frontier((s for s, _ in states),grounded=True)], stats


def eliminate(family, capacity=None, reverse=False, conditional=False):
    if conditional and capacity is not None:
        raise ValueError('a budget-bound search cannot claim a universal effect frontier')
    cache = {}; roots = []; stats = dict(factor_evaluations=0, compositions=0,
        peak_partial_frontier=0, local_alternatives=0, local_frontier_states=0,
        root_materializations=0, root_survivors=0, skipped_stripes=[], dominance_witnesses=0, separator_trace=[])
    stripes = family.stripes[::-1] if reverse else family.stripes
    for stripe in stripes:
        # Entire consumer-family minimum peak is a necessary bound with a
        # simultaneous allocation proof; it contains no invented E/T minima.
        minimum_weight = min(k*j for k, j in family.legal_tiles(1, stripe))
        if capacity is not None and family.n*stripe + family.n**2 + minimum_weight > capacity:
            stats['skipped_stripes'].append(stripe)
            continue
        partial = [State(0, 0, Fraction(0), ())]
        for stage in range(3):
            local = []
            choices = tuple(family.legal_tiles(stage, stripe))
            if reverse:
                choices = choices[::-1]
            for k, j in choices:
                key = family.factor_key(stage, stripe, k, j)
                if key not in cache:
                    cache[key] = family.factor(stage, stripe, k, j)
                    stats['factor_evaluations'] += 1
                state = cache[key]
                if capacity is None or state.peak <= capacity:
                    local.append(state)
            stats['local_alternatives'] += len(local)
            kept = frontier(local)
            stats['local_frontier_states'] += len(kept)
            stats['dominance_witnesses'] += len(local)-len(kept)
            input_states = len(partial)
            candidates = []
            for left, right in product(partial, kept):
                stats['compositions'] += 1
                candidates.append(combine(left, right))
            if stage==2:
                stats['root_materializations'] += len(candidates)
            partial = frontier(candidates)
            stats['separator_trace'].append(dict(stripe=stripe,stage=stage,
                input_states=input_states,local_alternatives=len(local),local_frontier=len(kept),
                partial_materializations=len(candidates),kept_states=len(partial)))
            stats['peak_partial_frontier'] = max(stats['peak_partial_frontier'], len(partial))
        stats['root_survivors'] += len(partial)
        roots.extend((s, Plan(stripe, s.tiles)) for s in partial)
    effects = frontier(s for s, _ in roots)
    stats['conditional_root_states'] = len(effects)
    kept = effects if conditional else frontier(effects,grounded=True)
    return [(s, next(p for t, p in roots if t is s)) for s in kept], stats
