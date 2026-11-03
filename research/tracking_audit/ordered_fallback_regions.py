"""Exact policy regions for a FIXED complete candidate universe, not FFM prefixes."""
from dataclasses import dataclass
import math
from numbers import Integral


def exact_bits(value):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise ValueError('capacity/resource bits must be nonnegative integers, not reconstructed floats')
    return int(value)


@dataclass(frozen=True)
class PolicyInterval:
    lower_bits: int
    upper_bits: int | None

    def contains(self, capacity_bits):
        capacity_bits = exact_bits(capacity_bits)
        return self.lower_bits <= capacity_bits and (self.upper_bits is None or capacity_bits < self.upper_bits)


def ordered_fallback_regions(requirements_bits, usages, thresholds):
    """One exact interval or None per candidate; O(nd log n) priority sweep.

    Assumptions: fixed candidates, fixed attributes, sole changing hard constraint
    r<=C, then the complete ordered fallback sequence. No partial-state pruning.
    Scores use supplied exact Python comparisons; Fraction attributes are allowed.
    """
    requirements = [exact_bits(r) for r in requirements_bits]
    if len(usages) != len(requirements) or any(len(u) != len(thresholds) for u in usages):
        raise ValueError('usage shape must match candidates and thresholds')
    if any(not math.isfinite(x) for row in usages for x in row) or any(not math.isfinite(t) for t in thresholds):
        raise ValueError('usage attributes and thresholds must be finite')
    tiers = {}
    for i, values in enumerate(usages):
        priority = tuple((1, 0) if value >= threshold else (0, value)
                         for value, threshold in zip(values, thresholds))
        tiers.setdefault(priority, []).append(i)
    result, higher_minimum = [None] * len(requirements), None
    for priority in sorted(tiers, reverse=True):
        indices = tiers[priority]
        for i in indices:
            if higher_minimum is None or requirements[i] < higher_minimum:
                result[i] = PolicyInterval(requirements[i], higher_minimum)
        tier_minimum = min(requirements[i] for i in indices)
        higher_minimum = tier_minimum if higher_minimum is None else min(tier_minimum, higher_minimum)
    return result


def fallback_oracle(requirements_bits, usages, thresholds, capacity_bits):
    """Independent direct application of the ordered policy, including all ties."""
    capacity_bits = exact_bits(capacity_bits)
    rows = [i for i, r in enumerate(requirements_bits) if exact_bits(r) <= capacity_bits]
    for j, threshold in enumerate(thresholds):
        if not rows:
            break
        passing = [i for i in rows if usages[i][j] >= threshold]
        if passing:
            rows = passing
        else:
            best = max(usages[i][j] for i in rows)
            rows = [i for i in rows if usages[i][j] == best]
    return rows
