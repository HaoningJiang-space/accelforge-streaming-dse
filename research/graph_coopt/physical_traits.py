"""Opaque FFM interface, explicitly not a proof of future equivalence."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PhysicalInterface:
    compatibility: Any
    # FFM's Compatibility does not encode all non-backing copies.
    copies_complete: bool = False

    def proves_substitutability(self, other):
        # No merging or conditional dominance based on incomplete traits.
        return False
