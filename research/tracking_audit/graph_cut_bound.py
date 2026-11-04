"""Exact branch-and-bound toy for A B = X, X D = Y.

This restricted cost model is deliberately independent of FFM.  It checks a
single producer/consumer cut, not arbitrary FFM Fusion or hardware validity.
All quantities and comparisons are exact integers or Fractions.
"""
from dataclasses import dataclass
from fractions import Fraction
from time import perf_counter


@dataclass(frozen=True)
class Architecture:
    px: int
    py: int
    capacity: int
    bandwidth: int

    def __post_init__(self):
        if any(type(x) is not int or x <= 0 for x in (self.px, self.py, self.capacity, self.bandwidth)):
            raise ValueError('architecture dimensions, capacity and bandwidth must be positive integers')


@dataclass(frozen=True)
class Branch:
    name: str
    # X bytes simultaneously live at the producer/consumer cut.
    live_bytes: int
    # Bytes occupied by other tensors throughout this cut.
    reserved_bytes: int
    # Repeated input traffic from the chosen schedule (in addition to base IO).
    repeated_input_bytes: int
    # The schedule explicitly permits spilling its live X to DRAM.
    can_spill: bool

    def __post_init__(self):
        if not self.name or any(type(x) is not int or x < 0 for x in
                                (self.live_bytes, self.reserved_bytes, self.repeated_input_bytes)):
            raise ValueError('invalid branch')
        if type(self.can_spill) is not bool:
            raise ValueError('can_spill must be boolean')


@dataclass(frozen=True)
class Model:
    macs: int
    base_dram_bytes: int
    mac_energy: int
    byte_energy: int

    def __post_init__(self):
        if any(type(x) is not int or x <= 0 for x in
               (self.macs, self.base_dram_bytes, self.mac_energy, self.byte_energy)):
            raise ValueError('positive integer model constants required')


def spill_bytes(branch, arch):
    """Mandatory traffic at one cut; None means the branch cannot run.

    Each live byte was produced, is dirty, is consumed later, and cannot be
    recomputed, compressed, aliased or kept in another memory. No transfer is
    in flight at the cut. Each missing byte needs one write and one later read.
    This accounts for this single cut only; bounds from cuts must not be added
    without a proof that their transfers are disjoint.
    """
    if branch.reserved_bytes > arch.capacity:
        return None
    missing = max(0, branch.live_bytes - (arch.capacity - branch.reserved_bytes))
    if missing and not branch.can_spill:
        return None
    return 2 * missing


def cost(model, arch, dram_bytes):
    # A deliberately optimistic overlap model. All costs are nonnegative;
    # bytes are distinct mandatory traffic, so addition does not double count.
    energy = model.macs * model.mac_energy + dram_bytes * model.byte_energy
    latency = max(Fraction(model.macs, arch.px * arch.py), Fraction(dram_bytes, arch.bandwidth))
    return energy * latency


def branch_bound(model, arch, branch):
    spill = spill_bytes(branch, arch)
    if spill is None:
        return None
    # Repeated input traffic is intentionally omitted: it represents choices
    # inside the branch and must not be assumed by this certificate.
    return cost(model, arch, model.base_dram_bytes + spill)


def complete_cost(model, arch, branch, extra_input_bytes):
    if type(extra_input_bytes) is not int or extra_input_bytes < 0:
        raise ValueError('extra input bytes must be a nonnegative integer')
    spill = spill_bytes(branch, arch)
    if spill is None:
        return None
    return cost(model, arch, model.base_dram_bytes + spill + branch.repeated_input_bytes + extra_input_bytes)


def search(model, arches, branches, extras, initial, *, prune, epsilon=Fraction(0)):
    """Finite targets, complete branch catalog, EDP-only quality guarantee.

    initial is a validated executable incumbent per architecture, or None. All
    certificates are conditional on the branch and model semantics above. The
    caller must not use this to prune an upstream FFM fallback candidate.
    """
    epsilon = Fraction(epsilon)
    if epsilon < 0:
        raise ValueError('epsilon must be nonnegative')
    if not extras or any(type(x) is not int or x < 0 for x in extras):
        raise ValueError('nonempty nonnegative completion choices required')
    if len(initial) != len(arches):
        raise ValueError('one incumbent per architecture is required')
    incumbents = []
    for arch, seed in zip(arches, initial):
        if seed is None:
            incumbents.append(None)
            continue
        bi, extra = seed
        if type(bi) is not int or not 0 <= bi < len(branches) or extra not in extras:
            raise ValueError('incumbent must identify an actual completion')
        value = complete_cost(model, arch, branches[bi], extra)
        if value is None:
            raise ValueError('infeasible incumbent')
        incumbents.append((value, bi, extra))
    stats = dict(certificates=0, pruned_arch_branches=0, completed_pairs=0,
                 infeasible_arch_branches=0, bound_s=0., completion_s=0., covered_per_branch=[], witnesses=[])
    for bi, branch in enumerate(branches):
        start = perf_counter()
        bounds = [branch_bound(model, arch, branch) for arch in arches] if prune else [None]*len(arches)
        stats['bound_s'] += perf_counter()-start
        covered = 0
        for i, arch in enumerate(arches):
            if prune and bounds[i] is None:
                stats['infeasible_arch_branches'] += 1
                continue
            incumbent = incumbents[i]
            if prune and incumbent is not None and incumbent[0] <= (1+epsilon)*bounds[i]:
                covered += 1
                stats['pruned_arch_branches'] += 1
                stats['witnesses'].append(dict(branch=bi, architecture=i, incumbent=str(incumbent[0]),
                                               incumbent_branch=incumbent[1], incumbent_extra=incumbent[2],
                                               lower_bound=str(bounds[i])))
                continue
            for extra in extras:
                start = perf_counter()
                value = complete_cost(model, arch, branch, extra)
                stats['completion_s'] += perf_counter()-start
                stats['completed_pairs'] += 1
                if value is not None and (incumbent is None or value < incumbent[0]):
                    incumbent = (value, bi, extra)
            incumbents[i] = incumbent
        if covered:
            stats['certificates'] += 1
            stats['covered_per_branch'].append(covered)
    return incumbents, stats
