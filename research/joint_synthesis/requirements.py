"""Explicit endpoint restrictions, not inferred consumer layout preferences."""
from dataclasses import dataclass
from .physical_plan import Property


@dataclass(frozen=True)
class PhysicalRequirements:
    producer_delivered: frozenset[Property]|None=None
    consumer_required: frozenset[Property]|None=None

    def validate(self,graph):
        tensor=graph.operators[0].output
        for allowed in (self.producer_delivered,self.consumer_required):
            if allowed is not None and (type(allowed) is not frozenset or
                    any(not isinstance(p,Property) or p.tensor!=tensor for p in allowed)):
                raise ValueError('requirements must name exact boundary properties of this graph')


