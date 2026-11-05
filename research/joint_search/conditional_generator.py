"""Share native ordered Tile execution across a finite architecture domain."""
from dataclasses import dataclass, replace
import copy
import sympy
import numpy as np
from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.target_enumeration import TargetEnumerator, capacity_events
from accelforge.mapper.FFM.generation_contract import GenerationContract
from .architecture_domain import ArchitectureDomain
from .ffm_backend import tiles


@dataclass(frozen=True)
class JointGenerationContract:
    reference: GenerationContract
    domain: ArchitectureDomain
    version: str = 'finite-architecture-cohort-v1'


class ArchitectureEnumerator(TargetEnumerator):
    """Existing cohort interpreter, with three finite parameter bounds."""
    def __init__(self, objectives, domain, **kwargs):
        super().__init__(tiles, objectives, [(sympy.Integer(0), p.capacity_bytes*8)
            for p in domain.points], membership_format='packed', **kwargs)
        self.full_target = None
        self.domain = domain
        self.active = [copy.copy(o) for o in objectives]
        self.axes = {}
        for o in self.active:
            if o.name == 'usage<SEP>memory<SEP>GlobalBuffer':
                if not o.exact:
                    raise ValueError('exact bit capacities required')
                self.axes[o.name] = tuple(p.capacity_bytes*8 for p in domain.points)
            elif o.name.startswith(('usage<SEP>spatial', 'min_usage_')):
                axis = next((a for a in ('reuse_input', 'reuse_output') if o.name.endswith(a)), None)
                if axis is None or any(v is not None and v != 1 for v in (o.max_value, o.min_value)):
                    raise ValueError('only NVDLA unit spatial policies supported')
                attr = 'px' if axis == 'reuse_input' else 'py'
                o.formula = sympy.simplify(o.formula * getattr(domain.upper, attr))
                o.exact = True
                self.axes[o.name] = tuple(getattr(p, attr) for p in domain.points)
        self.exact_goals = True

    def log_keep(self, *args):
        pass

    def constrain(self, state, objective, complete):
        if objective.name not in self.axes:
            return super().constrain(state, objective, complete)
        if objective.max_value is None and objective.min_value is None:
            return [state]
        minimum = objective.min_value is not None
        try:
            values = self.evaluate(objective.formula, state,
                maximize=objective.formula if minimum else None,
                minimize=None if minimum else objective.formula, exact_evaluation=True)
        except (TypeError, ValueError):
            if complete:
                raise
            return [state]
        values = np.broadcast_to(values, (len(state.choices),))
        bounds = self.axes[objective.name]
        # The inherited event partition handles <=; negation gives >= without
        # reordering choices, objective execution or fallback decisions.
        partitions = capacity_events(-values if minimum else values, state.targets,
            tuple(-b for b in bounds) if minimum else bounds, strict=complete)
        children = []
        for ids, valid in partitions:
            if minimum and objective.try_best_if_none_reaches_min and not valid.any():
                valid = values == np.max(values) if complete else np.ones(len(values), dtype=bool)
            children.append(self.mask_rows(replace(state, targets=ids), valid))
        return children
