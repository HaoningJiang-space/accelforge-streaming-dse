"""Shared, finite-target Tile enumeration with capacity-event partitions.

A cohort has identical ordered partial assignments and Pareto history, but can
serve several capacity targets. It expands once. A capacity check splits the
cohort at attained resource thresholds, *before* subsequent ordered fallbacks.
Only identical states may merge again. This is a live search frontier, not a
cache of completed per-target enumerations or a union used for fallback.

The independent enumerator remains the oracle. This first backend handles one
capacity formula and exact, perfect-tiling searches; other modes fall back.
"""
from dataclasses import dataclass, replace
import copy

import numpy as np
import sympy
from accelforge.mapper.FFM._pareto_df.target_membership import build_target_membership


@dataclass
class Cohort:
    choices: np.ndarray | None
    targets: tuple[int, ...]
    history: tuple = ()


def capacity_events(values, targets, bounds):
    """Partition target IDs by the exact mask of ``values <= bounds[target]``.

    Float-array events use sorted attained values and NumPy's scalar promotion
    rules, so Python float thresholds retain the oracle's float32 rounding. Only
    one row mask is materialized per distinct event, not one per target. Other
    numeric forms use direct comparisons and group equal masks conservatively.
    Returned masks preserve candidate order; target order is also preserved.
    """
    original = values
    values = np.asarray(values)
    groups = {}
    thresholds = None
    if values.ndim == 1 and values.dtype.kind == 'f' and np.isfinite(values).all():
        try:
            thresholds = [(t, np.result_type(values, bounds[t])) for t in targets]
            thresholds = [(t, dtype, np.asarray(bounds[t], dtype=dtype)[()])
                          for t, dtype in thresholds]
            if any(dtype.kind != 'f' or np.isnan(bound) for _, dtype, bound in thresholds):
                thresholds = None
        except (TypeError, ValueError):
            thresholds = None
    if thresholds is not None:
        events = np.unique(values)
        promoted_events = {}
        for target, dtype, threshold in thresholds:
            # Conversions between supported float types are monotone; the event
            # count identifies a prefix of the same ordered attained values.
            if dtype not in promoted_events:
                promoted_events[dtype] = events.astype(dtype, copy=False)
            count = int(np.searchsorted(promoted_events[dtype], threshold, side='right'))
            groups.setdefault(count, []).append(target)
        return [(tuple(ids), values <= bounds[ids[0]]) for ids in groups.values()]

    for target in targets:
        try:
            mask = np.asarray(original <= bounds[target], dtype=bool)
        except (TypeError, ValueError):
            # The oracle defers this target's unsupported comparison only. Do
            # not accidentally defer every other target in the same cohort.
            mask = np.ones(values.shape, dtype=bool)
        key = (mask.shape, mask.tobytes())
        if key not in groups:
            groups[key] = ([], mask)
        groups[key][0].append(target)
    return [(tuple(ids), mask) for ids, mask in groups.values()]


def merge_cohorts(states, stats):
    """Future substitution requires row order, dtype AND pruning history."""
    merged = {}
    for state in states:
        if not len(state.choices):
            continue
        key = (state.choices.dtype.str, state.choices.shape,
               state.choices.tobytes(order='C'), state.history)
        if key in merged:
            old = merged[key]
            old.targets += state.targets
            stats['state_merges'] += 1
        else:
            merged[key] = state
    return list(merged.values())


def _symbol_order(symbols, relations):
    """The oracle's inner-to-outer, one-rank-variable-at-a-time order."""
    remaining, last = list(symbols), None
    while remaining:
        outer = relations.get_outer_tiles(last, none_if_fail=True)
        if outer is not None and outer in remaining:
            symbol = outer
            remaining.remove(symbol)
        else:
            strides = [s for s in remaining if relations.is_stride(s)]
            index = -1
            if strides:
                maximum = relations.get_max_size(strides[index])
                for i, s in enumerate(strides):
                    if relations.get_inner_tiles(s, none_if_fail=True) is None:
                        if relations.get_max_size(s) < maximum:
                            index, maximum = i, relations.get_max_size(s)
                index = remaining.index(strides[index])
            symbol = remaining.pop(index)
        if relations.is_stride(symbol):
            last = symbol
        yield symbol


class TargetEnumerator:
    def __init__(self, api, objectives, targets, symbols, what_tiles_symbol, job,
                 keep_symbols=(), max_loop_check_groups=(), membership_format='excluded'):
        self.api, self.job, self.relations = api, job, what_tiles_symbol
        self.symbols, self.keep = tuple(symbols), set(keep_symbols)
        self.loop_groups = max_loop_check_groups
        self.bounds = [bound for _, bound in targets]
        self.membership_format = membership_format
        self.full_target = next((i for i, b in reversed(list(enumerate(self.bounds))) if b == 1), None)
        first_min = next((i for i, o in enumerate(objectives) if o.try_best_if_none_reaches_min), len(objectives))
        # The target's name and threshold are metadata; the formula/position are
        # the same as each independent invocation. Distinguish it by identity.
        self.capacity = api.Objective('capacity_target', targets[0][0], max_value=1,
                                      only_care_if_valid=True, symbols=symbols)
        self.active = [copy.copy(o) for o in objectives]
        self.active.insert(first_min, self.capacity)
        self.done, self.compiled = [], {}
        self.text = api.SymbolicText()
        self.stats = dict(supported=1, state_expansions=0, expanded_rows=0,
                          target_expansions=0, target_expanded_rows=0,
                          value_evaluations=0, target_value_evaluations=0,
                          capacity_partitions=0, capacity_masks=0,
                          pareto_calls=0, target_pareto_calls=0, state_merges=0,
                          peak_cohorts=1, peak_state_rows=0, peak_state_bytes=0)

    def record_peak(self, states):
        self.stats['peak_cohorts'] = max(self.stats['peak_cohorts'], len(states))
        self.stats['peak_state_rows'] = max(self.stats['peak_state_rows'], sum(len(s.choices) for s in states))
        self.stats['peak_state_bytes'] = max(self.stats['peak_state_bytes'], sum(s.choices.nbytes for s in states))

    def log_keep(self, state, name, before, after):
        if self.full_target in state.targets:
            self.job.log_porp_pmappings_kept(name, after / max(1, before))

    def evaluate(self, formula, state, minimize=None, maximize=None):
        self.stats['value_evaluations'] += 1
        self.stats['target_value_evaluations'] += len(state.targets)
        values = state.choices.astype(self.api.util.NUMPY_FLOAT_TYPE)
        if formula in self.done:
            return values[:, self.done.index(formula)]
        padded = self.api.get_padded_choices(
            symbols_enumerated=self.done,
            symbols_non_enumerated_set=set(self.symbols) - set(self.done),
            choices_enumerated=values, what_tiles_symbol=self.relations,
            minimize_formula=minimize, maximize_formula=maximize)
        if formula not in self.compiled:
            self.compiled[formula] = self.api.util._lambdify_type_check(self.symbols, formula)
        return self.compiled[formula](**{str(k): v for k, v in padded.items()})

    @staticmethod
    def mask_rows(state, valid):
        if np.ndim(valid) == 0:
            valid = np.full(len(state.choices), bool(valid), dtype=bool)
        return replace(state, choices=state.choices[valid])

    def constrain(self, state, objective, complete):
        before = len(state.choices)
        if objective is self.capacity:
            if objective.max_value is None:
                return [state]
            try:
                values = self.evaluate(objective.formula, state, minimize=objective.formula)
            except (TypeError, ValueError):
                # Same unsupported-bound deferral as the independent enumerator.
                return [state]
            partitions = capacity_events(values, state.targets, self.bounds)
            self.stats['capacity_partitions'] += 1
            self.stats['capacity_masks'] += len(partitions)
            result = []
            for ids, mask in partitions:
                child = self.mask_rows(replace(state, targets=ids), mask)
                self.log_keep(child, f'capacity_target_{self.bounds[self.full_target]!r}'
                              if self.full_target is not None else 'capacity_target', before, len(child.choices))
                result.append(child)
            return result

        if objective.max_value is not None:
            try:
                values = self.evaluate(objective.formula, state, minimize=objective.formula)
                valid = values <= objective.max_value if objective.inclusive else values < objective.max_value
                state = self.mask_rows(state, valid)
            except (TypeError, ValueError):
                pass
        if objective.min_value is not None:
            try:
                values = self.evaluate(objective.formula, state, maximize=objective.formula)
                valid = values >= objective.min_value if objective.inclusive else values > objective.min_value
                if np.ndim(valid) == 0:
                    valid = np.full(len(state.choices), bool(valid), dtype=bool)
                if not objective.try_best_if_none_reaches_min or valid.any():
                    state = self.mask_rows(state, valid)
                elif complete:
                    valid |= values == np.max(values)
                    state = self.mask_rows(state, valid)
            except (TypeError, ValueError):
                pass
        self.log_keep(state, objective.name, before, len(state.choices))
        return [state]

    def base_goals(self):
        goals = {}
        for symbol in self.done:
            per_prime = not (self.api.IMPERFECT or self.api._get_n_prime_factors(self.relations.get_max_size(symbol)) == 1)
            outer = self.relations.get_outer_tiles(symbol, none_if_fail=True)
            if isinstance(outer, sympy.Symbol) and outer not in self.done:
                self.add_goal(goals, symbol, self.api.Goal('min_per_prime_factor' if per_prime else 'min'))
            inner = self.relations.get_inner_tiles(symbol, none_if_fail=True)
            if isinstance(inner, sympy.Symbol) and inner not in self.done:
                self.add_goal(goals, symbol, self.api.Goal('max_per_prime_factor' if per_prime else 'max'))
        for symbol in set(self.done) & self.keep:
            self.add_goal(goals, symbol, self.api.Goal('diff'))
        return goals

    def add_goal(self, goals, symbol, goal):
        goals[symbol] = goal | goals.get(symbol, self.api.Goal())

    def pareto(self, state, goals):
        if len(state.choices) < 100:
            return state
        # coalesce_symbols is structural, but may rewrite its working dictionary.
        goals = self.api.coalesce_symbols(
            symbols_enumerated=self.done, symbol2goal=dict(goals),
            update_symbol2goal=lambda s, g, dest: self.add_goal(dest, s, g),
            log_message=lambda *args: None, bounds=self.relations.bounds, text=self.text)
        key = self.api.fzs((f, g.goal) for f, g in goals.items())
        if any(previous.issubset(key) for previous in state.history):
            return state
        state = replace(state, history=state.history + (key,))
        values = [self.evaluate(formula, state) for formula in goals]
        if not values:
            self.log_keep(state, 'Pareto', len(state.choices), 1)
            return replace(state, choices=state.choices[:1])
        if all(goals.get(s) == self.api.Goal('diff') for s in self.done):
            return state
        matrix = np.concatenate([v.reshape(-1, 1) for v in values], axis=1)
        self.stats['pareto_calls'] += 1
        self.stats['target_pareto_calls'] += len(state.targets)
        keep = self.api.makepareto_numpy(matrix, [g.goal for g in goals.values()], dirty=True)
        result = self.mask_rows(state, keep)
        self.log_keep(state, 'Pareto', len(state.choices), len(result.choices))
        return result

    def run(self):
        states = [Cohort(None, tuple(range(len(self.bounds))))]
        for symbol in _symbol_order(self.symbols, self.relations):
            if not states:
                break
            for state in states:
                before = len(state.choices) if state.choices is not None else 1
                state.choices = self.api._expand_symbol_choices(
                    symbol, state.choices, self.done, self.relations, self.api.IMPERFECT)
                self.stats['state_expansions'] += 1
                self.stats['target_expansions'] += len(state.targets)
                self.stats['expanded_rows'] += len(state.choices)
                self.stats['target_expanded_rows'] += len(state.targets) * len(state.choices)
                if self.full_target in state.targets:
                    self.job.n_total_pmappings *= len(state.choices) / max(1, before)
            self.done.append(symbol)
            self.record_peak(states)
            for state in states:
                before = len(state.choices)
                state.choices = self.api.check_loops(self.done, state.choices, self.loop_groups, self.relations)
                self.log_keep(state, 'max_fused_loops_per_rank_variable', before, len(state.choices))
            states = merge_cohorts(states, self.stats)
            goals = self.base_goals()
            for objective in list(self.active):
                partition = self.api.partition_formula(objective.formula, set(self.done), self.relations.bounds)
                if any(g.goal == 'diff' for g in partition.values()):
                    expanded = self.api.partition_formula(sympy.expand(objective.formula), set(self.done), self.relations.bounds)
                    partition = min((partition, expanded), key=lambda d: sum(g.goal == 'diff' for g in d.values()))
                complete = objective.formula.free_symbols.issubset(set(self.done))
                states = [child for state in states for child in self.constrain(state, objective, complete)]
                states = merge_cohorts(states, self.stats)
                self.record_peak(states)
                if complete:
                    objective.max_value = None
                    if objective.only_care_if_valid:
                        self.active.remove(objective)
                        partition = {}
                for formula, goal in partition.items():
                    self.add_goal(goals, formula, goal)
            self.job.n_evaluated_pmappings += sum(len(s.choices) * len(s.targets) for s in states)
            states = merge_cohorts([self.pareto(s, goals) for s in states], self.stats)
            self.record_peak(states)

        self.job.target_enumeration_stats = dict(self.stats)
        self.job.log_message(f'Capacity-event enumeration: {self.stats}')
        if not states:
            return np.empty((0, len(self.symbols))), build_target_membership(
                0, len(self.bounds), (), self.membership_format)
        columns = [self.done.index(s) for s in self.symbols]
        parts = [s.choices[:, columns] for s in states]
        # The oracle returns a float64 empty array when a target is exhausted.
        # Its final concatenate includes those empty parts, promoting the UNION's
        # dtype even though they add no rows. Dropping dead cohorts must not drop
        # this effect: downstream FFM uses the Tile columns' numeric types.
        if sum(len(s.targets) for s in states) < len(self.bounds):
            parts.append(np.empty((0, len(self.symbols)), dtype=np.float64))
        choices = np.unique(np.concatenate(parts), axis=0)
        index = {tuple(row): i for i, row in enumerate(choices.tolist())}
        memberships = (([index[tuple(row)] for row in part.tolist()], state.targets)
                       for state, part in zip(states, parts))
        excluded = build_target_membership(len(choices), len(self.bounds), memberships,
                                           self.membership_format)
        return choices, excluded


def enumerate_targets(api, objectives, capacity_targets, **kwargs):
    """Return None only for explicitly unsupported modes; never hide failures."""
    job = kwargs['job']
    if (not kwargs['symbols'] or api.IMPERFECT or api.pareto_module.TOLERANCE != 0
            or job.spec.mapper.ffm._count_option_for_mapsapce_size_evaluation != ()
            or any(formula != capacity_targets[0][0] for formula, _ in capacity_targets)):
        job.target_enumeration_stats = {'supported': 0}
        return None
    return TargetEnumerator(api, objectives, capacity_targets, **kwargs).run()
