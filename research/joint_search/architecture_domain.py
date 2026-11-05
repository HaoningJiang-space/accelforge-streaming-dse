"""A finite global hardware variable; labels carry IDs, never capacity ratios."""
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Architecture:
    px: int
    py: int
    capacity_bytes: int

    def __post_init__(self):
        if any(type(x) is not int or x < 1 for x in (self.px, self.py, self.capacity_bytes)):
            raise ValueError('positive integer architecture coordinates required')
        if any(x & (x-1) for x in (self.px, self.py)):
            raise ValueError('first prototype requires dyadic PE extents')


@dataclass(frozen=True)
class ArchitectureDomain:
    points: tuple[Architecture, ...]

    def __post_init__(self):
        if (not isinstance(self.points,tuple) or not self.points or len(self.points) > 64
                or any(type(p) is not Architecture for p in self.points)
                or len(set(self.points)) != len(self.points)):
            raise ValueError('one to 64 distinct architectures required')
        if len({p.px*p.py for p in self.points}) != 1:
            raise ValueError('this gate requires an equal PE-count budget')

    @property
    def upper(self):
        return Architecture(*(max(getattr(p, f) for p in self.points)
                              for f in ('px', 'py', 'capacity_bytes')))

    @property
    def labels(self):
        # Opaque domain IDs in the existing packed-membership transport. They
        # are NOT capacity ratios; neither the Join nor queries interpret them
        # as physical thresholds. Exact capacity is an independent bit constraint.
        return tuple((i+1)/len(self.points) for i in range(len(self.points)))
