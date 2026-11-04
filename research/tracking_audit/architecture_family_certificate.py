"""Two-corner family certificate for the restricted synthetic graph-cut model.

The supported rectangle is integer-valued and uses the monotonic cost model in
graph_cut_bound. This is not a certificate for FFM, arbitrary architectures or
for preserving an entire Pareto frontier.
"""
from dataclasses import dataclass
from fractions import Fraction
from math import prod

from research.tracking_audit.graph_cut_bound import Architecture, branch_bound, complete_cost


@dataclass(frozen=True)
class ArchitectureBox:
    """Inclusive ranges in order Px, Py, capacity, bandwidth."""
    ranges: tuple[tuple[int,int], ...]

    def __post_init__(self):
        if len(self.ranges) != 4 or any(len(r)!=2 or any(type(v) is not int or v<=0 for v in r)
                                        or r[0]>r[1] for r in self.ranges):
            raise ValueError('four nonempty positive integer ranges required')

    @property
    def count(self):
        return prod(hi-lo+1 for lo,hi in self.ranges)

    def corner(self, upper):
        return Architecture(*(hi if upper else lo for lo,hi in self.ranges))

    def contains(self, arch):
        return all(lo<=v<=hi for (lo,hi),v in zip(self.ranges,
                   (arch.px,arch.py,arch.capacity,arch.bandwidth)))


def certify_family(model, box, branch, seed, seed_extra, epsilon=Fraction(0)):
    """Prove one feasible seed beats a branch uniformly, using two corners.

    In the synthetic model, larger PE dimensions, capacity and bandwidth cannot
    worsen a *fixed* seed's cost: its spill and latency are non-increasing.
    A branch lower bound is likewise non-increasing in all four parameters.
    Therefore U(box low) is an upper bound for the seed's cost throughout the
    box, and L(box high) is a lower bound for every branch completion throughout
    the box. The seed must be feasible at the lowest capacity. No target-point
    enumeration, sampling or user-supplied incumbent cost is used.
    """
    epsilon = Fraction(epsilon)
    if epsilon < 0:
        raise ValueError('epsilon must be nonnegative')
    low,high = box.corner(False),box.corner(True)
    upper = complete_cost(model,low,seed,seed_extra)
    lower = branch_bound(model,high,branch)
    if upper is None:
        return dict(status='unproven',reason='seed not feasible throughout the box',
                    architectures=box.count,upper=None,lower=None,corner_evaluations=2)
    if lower is None:
        return dict(status='infeasible_branch',reason='branch infeasible even at largest capacity',
                    architectures=box.count,upper=str(upper),lower=None,corner_evaluations=2)
    status = 'certified' if upper <= (1+epsilon)*lower else 'unproven'
    return dict(status=status,reason='two monotone corner bounds',architectures=box.count,
                upper=str(upper),lower=str(lower),epsilon=str(epsilon),corner_evaluations=2)
