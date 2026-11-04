"""Experimental integer-box interpreter of one FFM Tile enumeration program.

No target points are accepted by build(). Parameters occur as constraint bounds;
only attained candidate values split the family. Ordered choices AND the full
prefix Pareto history must agree before execution states can coalesce. This
does not change the library's default mapper or claim physical-mapspace coverage.
"""
from dataclasses import dataclass, replace
import copy

import numpy as np
import sympy

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.target_enumeration import (
    TargetEnumerator, _symbol_order,
)


@dataclass(frozen=True)
class Box:
    """Inclusive integer ranges; capacity unit is supplied by the adapter."""
    ranges: tuple[tuple[int, int], ...]

    def __post_init__(self):
        if len(self.ranges) != 3 or any(len(r) != 2 for r in self.ranges) or any(type(x) is not int or x < 1
                                      for interval in self.ranges for x in interval):
            raise ValueError('three positive integer parameter ranges required')
        if any(lo > hi for lo, hi in self.ranges):
            raise ValueError('empty parameter range')

    def contains(self, point):
        return len(point) == 3 and all(lo <= v <= hi for v, (lo, hi) in zip(point, self.ranges))

    def cut(self, axis, lo, hi):
        r = list(self.ranges)
        r[axis] = (lo, hi)
        return Box(tuple(r))


@dataclass
class RegionState:
    choices: np.ndarray | None
    targets: tuple[Box, ...]  # compatibility with TargetEnumerator's numerical helpers
    history: tuple = ()


def compact_boxes(boxes):
    boxes = set(boxes)
    changed = True
    while changed:
        before = len(boxes)
        for axis in range(3):
            groups = {}
            for box in boxes:
                key = box.ranges[:axis] + box.ranges[axis+1:]
                groups.setdefault(key, []).append(box)
            merged = set()
            for group in groups.values():
                group.sort(key=lambda b: b.ranges[axis])
                current = group[0]
                for box in group[1:]:
                    if current.ranges[axis][1] + 1 == box.ranges[axis][0]:
                        current = current.cut(axis, current.ranges[axis][0], box.ranges[axis][1])
                    else:
                        merged.add(current)
                        current = box
                merged.add(current)
            boxes = merged
        changed = len(boxes) < before
    return tuple(sorted(boxes, key=lambda b: b.ranges))


def split_events(boxes, axis, values, minimum=False):
    """Partition exactly where a row's integer-bound comparison changes."""
    values = np.asarray(values)
    # For v <= p the row enters at ceil(v); for v >= p it leaves at floor(v)+1.
    events = sorted({int(sympy.floor(v)) + 1 if minimum else int(sympy.ceiling(v))
                     for v in values})
    grouped = {}
    for box in boxes:
        lo, hi = box.ranges[axis]
        starts = [lo] + [v for v in events if lo < v <= hi] + [hi+1]
        for a, b in zip(starts, starts[1:]):
            mask = np.asarray(values >= a if minimum else values <= a, dtype=bool)
            key = mask.tobytes()
            if key not in grouped:
                grouped[key] = ([], mask)
            grouped[key][0].append(box.cut(axis, a, b-1))
    return [(compact_boxes(boxes), mask) for boxes, mask in grouped.values()]


class RegionEnumerator(TargetEnumerator):
    def __init__(self, api, objectives, family, *, axes, max_boxes=50000,
                 max_rows=2000000, **kwargs):
        """axes maps objective name -> parameter axis (upper or lower bound).

        Formulas must be independent of architecture parameters. A parameter
        objective's only bound is interpreted as its axis, not its numeric value.
        The adapter is responsible for proving the normalization transformation.
        """
        if api.IMPERFECT or api.pareto_module.TOLERANCE != 0 or not kwargs['symbols']:
            raise ValueError('requires nonempty perfect tiling and exact Pareto')
        if kwargs['job'].spec.mapper.ffm._count_option_for_mapsapce_size_evaluation != ():
            raise ValueError('mapspace counting mode is unsupported')
        super().__init__(api, objectives, [(sympy.Integer(0), 1)], **kwargs)
        self.active = [copy.copy(o) for o in objectives]  # no finite-target constraint
        self.exact_goals = any(o.exact for o in objectives)
        self.family, self.axes = family, dict(axes)
        if not set(axes).issubset({o.name for o in objectives}) or any(
                type(axis) is not int or not 0 <= axis < 3 for axis in axes.values()):
            raise ValueError('parameter axes must refer to existing objectives and axes 0..2')
        if max_boxes < 1 or max_rows < 1:
            raise ValueError('positive state budgets required')
        self.max_boxes, self.max_rows = max_boxes, max_rows
        self.leaves = None
        self.stats.update(region_splits=0, peak_boxes=1, final_boxes=0, final_states=0)
        for o in objectives:
            if o.name in axes and (not o.exact or not o.inclusive or (o.min_value is None) == (o.max_value is None)):
                raise ValueError('parameter objectives require exact arithmetic and one inclusive bound')

    def log_keep(self, *args):
        pass  # No representative architecture is privileged in this interpreter.

    def record_peak(self, states):
        super().record_peak(states)
        boxes = sum(len(s.targets) for s in states)
        self.stats['peak_boxes'] = max(self.stats['peak_boxes'], boxes)
        if boxes > self.max_boxes or sum(len(s.choices) for s in states) > self.max_rows:
            raise MemoryError(f'parametric state budget exceeded: {boxes} boxes; {self.stats}')

    def merge(self, states):
        groups = {}
        for s in states:
            if not len(s.choices):
                continue
            key = (s.choices.dtype.str, s.choices.shape, s.choices.tobytes(), s.history)
            if key in groups:
                groups[key].targets += s.targets
                self.stats['state_merges'] += 1
            else:
                groups[key] = s
        for s in groups.values():
            s.targets = compact_boxes(s.targets)
        return list(groups.values())

    def constrain(self, state, objective, complete):
        if objective.name not in self.axes:
            return super().constrain(state, objective, complete)
        if objective.max_value is None and objective.min_value is None:
            return [state]
        minimum = objective.min_value is not None
        try:
            values = self.evaluate(objective.formula, state,
                maximize=objective.formula if minimum else None,
                minimize=None if minimum else objective.formula,
                exact_evaluation=objective.exact)
        except (TypeError, ValueError) as error:
            if complete:
                raise RuntimeError('unsupported complete parametric constraint') from error
            return [state]
        if np.ndim(values) == 0:
            values = np.full(len(state.choices), values)
        if not all(sympy.sympify(v).is_finite for v in values):
            raise ValueError('finite parameter events required')
        partitions = split_events(state.targets, self.axes[objective.name], values, minimum)
        self.stats['region_splits'] += len(partitions) - 1
        children = []
        for boxes, mask in partitions:
            if minimum and objective.try_best_if_none_reaches_min and not mask.any():
                mask = values == np.max(values) if complete else np.ones(len(values), dtype=bool)
            children.append(self.mask_rows(replace(state, targets=boxes), mask))
        return children

    def build(self):
        if self.leaves is not None:
            raise ValueError('build is single-use; query the resulting representation')
        states = [RegionState(None, (self.family,))]
        for symbol in _symbol_order(self.symbols, self.relations):
            if not states:
                break
            for state in states:
                state.choices = self.api._expand_symbol_choices(
                    symbol, state.choices, self.done, self.relations, False)
                self.stats['state_expansions'] += 1
                self.stats['expanded_rows'] += len(state.choices)
            self.done.append(symbol)
            self.record_peak(states)
            for state in states:
                state.choices = self.api.check_loops(self.done, state.choices, self.loop_groups, self.relations)
            states = self.merge(states)
            goals = self.base_goals()
            for objective in list(self.active):
                partition = self.api.partition_formula(objective.formula, set(self.done), self.relations.bounds)
                if any(g.goal == 'diff' for g in partition.values()):
                    expanded = self.api.partition_formula(sympy.expand(objective.formula), set(self.done), self.relations.bounds)
                    partition = min((partition, expanded), key=lambda d: sum(g.goal == 'diff' for g in d.values()))
                complete = objective.formula.free_symbols.issubset(set(self.done))
                states = self.merge([child for state in states for child in self.constrain(state, objective, complete)])
                self.record_peak(states)
                if complete:
                    objective.max_value = None
                    if objective.only_care_if_valid:
                        self.active.remove(objective)
                        partition = {}
                for formula, goal in partition.items():
                    self.add_goal(goals, formula, goal)
            states = self.merge([self.pareto(s, goals) for s in states])
            self.record_peak(states)
        columns = [self.done.index(s) for s in self.symbols] if states else []
        self.leaves = [replace(s, choices=s.choices[:, columns].copy()) for s in states]
        self.stats['final_states'] = len(states)
        self.stats['final_boxes'] = sum(len(s.targets) for s in states)
        # The inherited "target" counters count boxes, not architectures; do not
        # expose them as a work-reduction claim about a continuum of targets.
        self.stats = {k:v for k,v in self.stats.items() if not k.startswith('target_')}
        return self

    def locate(self, point):
        if len(point) != 3 or any(type(v) is not int for v in point):
            raise ValueError('query requires three integer parameters in the compiled units')
        if not self.family.contains(point):
            raise ValueError('query lies outside the compiled architecture family')
        if self.leaves is None:
            raise ValueError('build the representation before querying')
        found = [i for i,s in enumerate(self.leaves) if any(b.contains(point) for b in s.targets)]
        if len(found) > 1:
            raise AssertionError('overlapping final execution regions')
        return found[0] if found else None

    def query(self, point):
        i = self.locate(point)
        return (self.leaves[i].choices.copy() if i is not None
                else np.empty((0, len(self.symbols))))
