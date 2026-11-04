"""Experimental shared-prefix region interpreter for perfect FFM tiling.

One numeric prefix pool is built per symbol depth; each region retains an
ordered uint32 ID vector, its boxes and its own Pareto history. This is a
research backend, not a replacement for the default mapper. Unsupported
assumptions fail closed; no FFM policy or Fusion semantics are changed.
"""
from dataclasses import dataclass, replace

import numpy as np
import sympy

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.target_enumeration import _symbol_order
from research.tracking_audit.parametric_template import RegionEnumerator, RegionState, compact_boxes, split_events


@dataclass
class IdState:
    ids: np.ndarray | None
    targets: tuple
    history: tuple = ()


class FactorizedPrefixRegions(RegionEnumerator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool = None
        self.values = {}
        self.stats.update(shared_expansion_calls=0,shared_expanded_rows=0,
                          requested_expanded_rows=0,peak_id_bytes=0,peak_pool_bytes=0,
                          peak_id_rows=0,peak_value_array_bytes=0,pool_evaluations=0,subset_fallbacks=0)

    def _peak(self,states):
        rows = sum(len(s.ids) for s in states)
        boxes = sum(len(s.targets) for s in states)
        self.stats['peak_id_rows'] = max(self.stats['peak_id_rows'],rows)
        self.stats['peak_state_rows'] = max(self.stats['peak_state_rows'],rows)
        id_bytes = sum(s.ids.nbytes for s in states)
        self.stats['peak_id_bytes'] = max(self.stats['peak_id_bytes'],id_bytes)
        # The region state payload is now IDs, not complete numeric rows. Pool,
        # Python objects and temporary arrays are accounted for separately.
        self.stats['peak_state_bytes'] = max(self.stats['peak_state_bytes'],id_bytes)
        self.stats['peak_cohorts'] = max(self.stats['peak_cohorts'],len(states))
        self.stats['peak_pool_bytes'] = max(self.stats['peak_pool_bytes'],self.pool.nbytes)
        self.stats['peak_boxes'] = max(self.stats['peak_boxes'],boxes)
        if rows > self.max_rows or boxes > self.max_boxes:
            raise MemoryError('factorized region state budget exceeded')

    def _merge(self,states):
        groups = {}
        for state in states:
            if not len(state.ids):
                continue
            key = (state.ids.tobytes(),state.history)
            if key in groups:
                groups[key].targets += state.targets
                self.stats['state_merges'] += 1
            else:
                groups[key] = state
        for state in groups.values():
            state.targets = compact_boxes(state.targets)
        return list(groups.values())

    def _dependency(self,symbol):
        if self.relations.is_stride(symbol):
            inner = self.relations.get_inner_tiles(symbol,none_if_fail=True)
            outer = self.relations.get_outer_tiles(symbol,none_if_fail=True)
            return inner if inner in self.done else outer if outer in self.done else None
        if self.relations.is_initial_tile_shape(symbol):
            stride = self.relations.get_tile_shape(symbol)
            return stride if stride in self.done else None
        raise ValueError('unsupported symbol kind')

    def _expand(self,states,symbol):
        if self.pool is None:
            expanded = self.api._expand_symbol_choices(symbol,None,self.done,self.relations,False)
            if expanded.dtype.hasobject:
                raise ValueError('object-valued prefix pools are unsupported')
            if len(expanded) >= 2**32 or len(expanded) > self.max_rows:
                raise MemoryError('factorized prefix state budget exceeded')
            if len(np.unique(expanded,axis=0)) != len(expanded):
                raise ValueError('initial prefix choices must be unique')
            self.pool = expanded
            states[0].ids = np.arange(len(expanded),dtype=np.uint32)
            self.stats['requested_expanded_rows'] += len(expanded)
        else:
            seen = np.zeros(len(self.pool),dtype=bool)
            for state in states:
                seen[state.ids] = True
            active = np.flatnonzero(seen)
            parents = self.pool[active]
            dep = self._dependency(symbol)
            dep_index = self.done.index(dep) if dep is not None else None
            expanded = self.api._expand_symbol_choices(symbol,parents,self.done,self.relations,False)
            if expanded.dtype.hasobject or len(expanded) >= 2**32:
                raise ValueError('unsupported prefix dtype or ID range')
            parent_by_value = {tuple(row.tolist()):int(ident) for row,ident in zip(parents,active)}
            if len(parent_by_value) != len(parents):
                raise AssertionError('prefix pool must contain unique rows')
            children = {int(i):[] for i in active}
            child_by_value,unique = {},[]
            for row in expanded:
                key = tuple(row.tolist())
                parent = parent_by_value.get(key[:-1])
                if parent is None:
                    raise AssertionError('expanded row lost its parent')
                child = child_by_value.get(key)
                if child is None:
                    child = len(unique);child_by_value[key] = child;unique.append(row.copy())
                children[parent].append(child)
            children = {key:np.asarray(value,dtype=np.uint32) for key,value in children.items()}
            oldpool = self.pool
            for state in states:
                parents_in_order = state.ids
                if dep_index is not None:
                    order = np.argsort(oldpool[parents_in_order,dep_index],kind='stable')
                    parents_in_order = parents_in_order[order]
                parts = [children[int(i)] for i in parents_in_order if len(children[int(i)])]
                state.ids = np.concatenate(parts) if parts else np.empty(0,dtype=np.uint32)
                self.stats['requested_expanded_rows'] += len(state.ids)
            self.pool = np.asarray(unique,dtype=expanded.dtype).reshape(-1,expanded.shape[1])
        self.values = {}
        self.stats['shared_expansion_calls'] += 1
        self.stats['shared_expanded_rows'] += len(expanded)
        self.stats['state_expansions'] += 1
        self.stats['expanded_rows'] += len(expanded)

    def _evaluate(self,formula,state,minimize=None,maximize=None,exact_evaluation=False):
        key = (formula,minimize,maximize,exact_evaluation)
        if key not in self.values:
            try:
                proxy = RegionState(self.pool,())
                self.values[key] = super().evaluate(formula,proxy,minimize,maximize,exact_evaluation)
                self.stats['pool_evaluations'] += 1
                self.stats['peak_value_array_bytes'] = max(self.stats['peak_value_array_bytes'],
                    sum(getattr(v,'nbytes',0) for v in self.values.values()))
            except (TypeError,ValueError):
                # Some expressions may not be evaluable on the entire pool;
                # preserve the original region-local error/defer semantics.
                self.stats['subset_fallbacks'] += 1
                return super().evaluate(formula,RegionState(self.pool[state.ids],state.targets),
                                        minimize,maximize,exact_evaluation)
        result = self.values[key]
        return result if np.ndim(result)==0 else np.asarray(result)[state.ids]

    @staticmethod
    def _masked(state,mask):
        if np.ndim(mask)==0:
            mask = np.full(len(state.ids),bool(mask),dtype=bool)
        return replace(state,ids=state.ids[mask])

    def _constrain(self,state,objective,complete):
        if objective.name in self.axes:
            if objective.max_value is None and objective.min_value is None:
                return [state]
            minimum = objective.min_value is not None
            try:
                values = self._evaluate(objective.formula,state,
                    maximize=objective.formula if minimum else None,
                    minimize=None if minimum else objective.formula,exact_evaluation=objective.exact)
            except (TypeError,ValueError) as error:
                if complete:
                    raise RuntimeError('unsupported complete parametric constraint') from error
                return [state]
            if np.ndim(values)==0:
                values=np.full(len(state.ids),values)
            if not all(sympy.sympify(v).is_finite for v in values):
                raise ValueError('finite parameter events required')
            parts=split_events(state.targets,self.axes[objective.name],values,minimum)
            self.stats['region_splits'] += len(parts)-1
            children=[]
            for boxes,mask in parts:
                if minimum and objective.try_best_if_none_reaches_min and not mask.any():
                    mask=values==np.max(values) if complete else np.ones(len(values),dtype=bool)
                children.append(self._masked(replace(state,targets=boxes),mask))
            return children
        if objective.max_value is not None:
            try:
                values=self._evaluate(objective.formula,state,minimize=objective.formula,
                                      exact_evaluation=objective.exact)
                state=self._masked(state,values<=objective.max_value if objective.inclusive else values<objective.max_value)
            except (TypeError,ValueError) as error:
                if objective.exact and complete:
                    raise RuntimeError('could not evaluate a complete exact capacity constraint') from error
        if objective.min_value is not None:
            try:
                values=self._evaluate(objective.formula,state,maximize=objective.formula)
                valid=values>=objective.min_value if objective.inclusive else values>objective.min_value
                if np.ndim(valid)==0:
                    valid=np.full(len(state.ids),bool(valid),dtype=bool)
                if not objective.try_best_if_none_reaches_min or valid.any():
                    state=self._masked(state,valid)
                elif complete:
                    valid |= values==np.max(values)
                    state=self._masked(state,valid)
            except (TypeError,ValueError):
                pass
        return [state]

    def _pareto(self,state,goals):
        if len(state.ids)<100:
            return state
        goals=self.api.coalesce_symbols(symbols_enumerated=self.done,symbol2goal=dict(goals),
            update_symbol2goal=lambda s,g,dest:self.add_goal(dest,s,g),
            log_message=lambda *args:None,bounds=self.relations.bounds,text=self.text)
        key=self.api.fzs((f,g.goal) for f,g in goals.items())
        if any(previous.issubset(key) for previous in state.history):
            return state
        state=replace(state,history=state.history+(key,))
        values=[]
        for formula in goals:
            exact=self.exact_goals and not formula.atoms(sympy.Float)
            value=self._evaluate(formula,state,exact_evaluation=exact)
            if exact:
                from accelforge.mapper.FFM._pareto_df.exact_resources import comparison_values
                value=comparison_values(value)
            values.append(value)
        if not values:
            return replace(state,ids=state.ids[:1])
        if all(goals.get(s)==self.api.Goal('diff') for s in self.done):
            return state
        matrix=np.concatenate([v.reshape(-1,1) for v in values],axis=1)
        self.stats['pareto_calls'] += 1
        keep=self.api.makepareto_numpy(matrix,[g.goal for g in goals.values()],dirty=True)
        return self._masked(state,keep)

    def _check_loops(self,states):
        if not self.loop_groups:
            return states
        # An ID column is ignored by FFM's check_loops but follows its row mask.
        tagged=np.column_stack((self.pool,np.arange(len(self.pool),dtype=np.int64)))
        filtered=self.api.check_loops(self.done,tagged,self.loop_groups,self.relations)
        valid=np.zeros(len(self.pool),dtype=bool)
        valid[filtered[:,-1].astype(np.int64)] = True
        return [replace(s,ids=s.ids[valid[s.ids]]) for s in states]

    def build(self):
        if self.leaves is not None:
            raise ValueError('build is single-use')
        states=[IdState(None,(self.family,))]
        for symbol in _symbol_order(self.symbols,self.relations):
            if not states:
                break
            self._expand(states,symbol)
            self.done.append(symbol)
            self._peak(states)
            states=self._merge(self._check_loops(states))
            goals=self.base_goals()
            for objective in list(self.active):
                partition=self.api.partition_formula(objective.formula,set(self.done),self.relations.bounds)
                if any(g.goal=='diff' for g in partition.values()):
                    expanded=self.api.partition_formula(sympy.expand(objective.formula),set(self.done),self.relations.bounds)
                    partition=min((partition,expanded),key=lambda d:sum(g.goal=='diff' for g in d.values()))
                complete=objective.formula.free_symbols.issubset(set(self.done))
                states=self._merge([child for state in states for child in self._constrain(state,objective,complete)])
                self._peak(states)
                if complete:
                    objective.max_value=None
                    if objective.only_care_if_valid:
                        self.active.remove(objective);partition={}
                for formula,goal in partition.items():
                    self.add_goal(goals,formula,goal)
            states=self._merge([self._pareto(state,goals) for state in states])
            self._peak(states)
        columns=[self.done.index(s) for s in self.symbols] if states else []
        self.leaves=[RegionState(self.pool[s.ids][:,columns].copy(),s.targets,s.history) for s in states]
        self.stats['final_states']=len(states)
        self.stats['final_boxes']=sum(len(s.targets) for s in states)
        self.stats={k:v for k,v in self.stats.items() if not k.startswith('target_')}
        return self
