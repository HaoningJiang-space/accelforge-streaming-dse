"""Immutable candidate-generation provenance, independent of the Join contract."""
from dataclasses import dataclass
import math
import os


def effective_pareto_tolerance():
    from ._pareto_df import pareto
    value = float(pareto.TOLERANCE)
    if not math.isfinite(value) or not 0 <= value < 1:
        raise ValueError('Pareto tolerance must be finite and in [0, 1)')
    return value


@dataclass(frozen=True)
class GenerationContract:
    metrics: str
    pareto_tolerance: float
    switches: tuple[tuple[str, str], ...]
    resource_units: str

    @classmethod
    def capture(cls, metrics):
        return cls(str(metrics), effective_pareto_tolerance(),
                   tuple(sorted((k, v) for k, v in os.environ.items() if k.startswith('AF_'))),
                   os.environ.get('AF_RESOURCE_UNITS', 'bits'))
