"""Exact componentwise demand frontier; equal-vector sources may be folded."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DominanceWitness:
    removed: object
    dominator: object


class _StateSchema:
    """Do not compare e.g. kernel workspace with complete-plan peak."""
    def __init__(self):
        self.state_type=None;self.dimensions=None

    def validate(self,state):
        try:vector=tuple(state.vector)
        except (AttributeError,TypeError)as error:
            raise TypeError('Pareto states require an objective vector')from error
        if not vector:raise ValueError('Pareto objective vectors must be nonempty')
        if self.state_type is None:
            self.state_type=type(state);self.dimensions=len(vector)
        elif type(state)is not self.state_type:
            raise TypeError('Pareto states must have the same concrete physical type')
        elif len(vector)!=self.dimensions:
            raise ValueError('Pareto objective vectors must have equal dimensions')
        return vector


class Frontier:
    """Incremental numerical frontier; tracing is opt-in, not search overhead."""
    def __init__(self,witnesses=None,stats=None):
        self.kept=[];self.removed=[] if witnesses is not None else None
        self.witnesses=witnesses;self.stats=stats if stats is not None else {}
        self.schema=_StateSchema()

    def _no_worse(self,a,b):
        left,right=self.schema.validate(a),self.schema.validate(b)
        return all(x<=y for x,y in zip(left,right))

    def dominates(self,a,b):
        result=self._no_worse(a,b)
        self.stats['dominance_checks']=self.stats.get('dominance_checks',0)+1
        return result

    def add(self,state):
        self.schema.validate(state)
        self.stats['inputs']=self.stats.get('inputs',0)+1
        if any(self.dominates(old,state) for old in self.kept):
            if self.removed is not None:self.removed.append(state)
            self.stats['pruned']=self.stats.get('pruned',0)+1
            return
        survivors=[]
        for old in self.kept:
            if self.dominates(state,old):
                if self.removed is not None:self.removed.append(old)
                self.stats['pruned']=self.stats.get('pruned',0)+1
            else:survivors.append(old)
        survivors.append(state);self.kept=survivors
        self.stats['peak_kept']=max(self.stats.get('peak_kept',0),len(self.kept))

    def finish(self):
        for state in self.kept:self.schema.validate(state)
        if self.witnesses is not None:
            # Resolve to a final survivor, even if an earlier dominator was
            # itself removed later. Witness resolution is validation-only.
            self.witnesses.extend(DominanceWitness(s,next(p for p in self.kept
                if self._no_worse(p,s))) for s in self.removed)
            self.removed.clear()
        return list(self.kept)


def frontier(states,*,witnesses=None,stats=None):
    active=Frontier(witnesses,stats)
    for state in states:active.add(state)
    return active.finish()


def conditioned(states,property_key,*,witnesses=None,stats=None,prune=True):
    groups={};schema=_StateSchema()
    for state in states:
        schema.validate(state)
        groups.setdefault(property_key(state),[]).append(state)
    return {key:frontier(group,witnesses=witnesses,stats=stats) if prune else group
            for key,group in groups.items()}
