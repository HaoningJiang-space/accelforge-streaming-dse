"""Frozen native experiment domain, with one shared physical resource budget.

This protocol is independent of observed EDPs. It does not infer calibrated chip
area from PE count or bytes. It also does not relax the separate dyadic 2mm gate.
"""
from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True, order=True)
class Hardware:
    px: int
    py: int
    capacity_bytes: int

    def __post_init__(self):
        if any(type(x) is not int or x <= 0 for x in (self.px, self.py, self.capacity_bytes)):
            raise ValueError('positive integer physical hardware coordinates required')


@dataclass(frozen=True)
class ResourceBudget:
    max_pes: int
    max_sram_bytes: int

    def __post_init__(self):
        if any(type(x) is not int or x <= 0 for x in (self.max_pes, self.max_sram_bytes)):
            raise ValueError('positive integer resource ceilings required')

    def admits(self, hardware):
        return (hardware.px * hardware.py <= self.max_pes
                and hardware.capacity_bytes <= self.max_sram_bytes)


@dataclass(frozen=True)
class Domain:
    points: tuple[Hardware, ...]

    def __post_init__(self):
        if (not isinstance(self.points, tuple) or not self.points
                or any(type(p) is not Hardware for p in self.points)
                or len(set(self.points)) != len(self.points)):
            raise ValueError('nonempty distinct physical hardware domain required')

    def under(self, budget):
        selected = tuple(p for p in self.points if budget.admits(p))
        if not selected:
            raise ValueError('resource budget admits no declared hardware')
        return Domain(selected)


def registered_domain():
    """Twelve real 3mm points selected before any new measurements."""
    return Domain(tuple(Hardware(x, y, c) for (x, y), c in product(
        ((16, 384), (32, 192), (64, 96)),
        (128 * 1024, 132 * 1024 - 1, 132 * 1024, 256 * 1024))))


def registered_budgets():
    return tuple(ResourceBudget(6144, c) for c in (128 * 1024, 132 * 1024, 256 * 1024))
