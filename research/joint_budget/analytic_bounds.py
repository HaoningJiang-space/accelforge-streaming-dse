"""Restricted NVDLA bounds for global hardware/mapping EDP search.

These do not assume that native partial-state Pareto pruning is physically
complete. They bound the terminal native-policy space on the declared hardware.
The finite reference audit is mandatory: it also checks floating-point results.
"""
from dataclasses import dataclass
from fractions import Fraction
import hashlib
from pathlib import Path

from .protocol import Domain, Hardware, ResourceBudget

ROOT = Path(__file__).resolve().parents[2]
FROZEN_INPUTS = {
    'examples/arches/nvdla.yaml': 'e32b9a077a3258bce53486d75bc46413c31b694dd626ca63b25d0e4df4d3daa3',
    'examples/workloads/matmuls.yaml': '96d75c852ee8bd568064a7d3471eadcc011b90fcf182fc61c82f1b7557e8531d',
    'research/workloads/attention_qk_av.yaml': '388f444e084a1b3ce444e94ba4d1d5a7ef785ca9d77082a6e158a2d10c7bdc7d',
}
MAC_ENERGY = Fraction('0.084e-12')
DRAM_ENERGY = Fraction('7.03e-12')
MAC_LATENCY = Fraction('1e-9')
NUMERIC_DISCOUNT = Fraction(99, 100)


def check_frozen_inputs():
    for name, expected in FROZEN_INPUTS.items():
        content = (ROOT / name).read_bytes().replace(b'\r\n', b'\n')
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f'bound derivation requires re-review after changing {name}')


def floor_power_two(value):
    if type(value) is not int or value <= 0:
        raise ValueError('positive integer required')
    return 1 << (value.bit_length() - 1)


@dataclass(frozen=True)
class LowerBound:
    energy: Fraction
    latency: Fraction
    compute_ops: int
    compulsory_dram_bits: int
    phase_parallelism: tuple[int, ...]
    mode: str

    @property
    def edp(self):
        return self.energy * self.latency

    def record(self):
        return dict(energy=float(self.energy), latency=float(self.latency), edp=float(self.edp),
                    exact_energy=str(self.energy), exact_latency=str(self.latency),
                    compute_ops=self.compute_ops, compulsory_dram_bits=self.compulsory_dram_bits,
                    phase_parallelism=list(self.phase_parallelism), mode=self.mode,
                    numeric_discount=str(NUMERIC_DISCOUNT),
                    floating_point_scope='finite native frontier audit required; no universal error theorem')


def lower_bound(case, point, mode='shape'):
    """MAC + compulsory external I/O, with optional grammar-aware compute bound.

    No intermediate spill or independent-Einsum communication bound is added:
    fusion can remove those transfers. No pipeline-overlap mappings are admitted
    by this experiment (native FFM Join sums the operator latencies).
    """
    if case.arch != 'nvdla' or mode not in ('configured', 'shape'):
        raise ValueError('frozen NVDLA and configured/shape bound required')
    if any(n & (n - 1) for n in case.params[1:]):
        raise ValueError('perfect power-of-two rank extents required')
    if case.workload == 'matmuls':
        n, m, k = case.params
        phases = [(m*k*k, k, k)] * n
        bits = 8 * (2*m*k + n*k*k)
    else:
        raise ValueError('bound is not yet proved for this workload')
    parallelism = tuple(point.px * point.py if mode == 'configured' else
                        floor_power_two(min(point.px, x)) * floor_power_two(min(point.py, y))
                        for _, x, y in phases)
    ops = sum(count for count, _, _ in phases)
    energy = ops * MAC_ENERGY + bits * DRAM_ENERGY
    latency = sum((Fraction(count, p) * MAC_LATENCY
                   for (count, _, _), p in zip(phases, parallelism)), Fraction())
    # Intentional weakening, not an asserted roundoff proof. Exhaustive finite
    # native frontier validation must succeed before reporting certified cuts.
    return LowerBound(energy*NUMERIC_DISCOUNT, latency*NUMERIC_DISCOUNT, ops, bits, parallelism, mode)


def factor_domain(pes=6144, capacities=(131072, 135167, 135168, 262144)):
    """All ordered integer factor pairs, selected without timing/quality data."""
    if type(pes) is not int or pes <= 0:
        raise ValueError('positive PE count required')
    return Domain(tuple(Hardware(x, pes//x, c) for x in range(1, pes+1) if pes % x == 0
                        for c in capacities))


def factor_budgets():
    return tuple(ResourceBudget(6144, c) for c in (131072, 135168, 262144))


def audit_vectors(case, domain, records, mode='shape'):
    """Independent of search: every full reference vector must respect E/T bounds."""
    checks = []
    if len(records) != len(domain.points):
        raise ValueError('one full native frontier per hardware required')
    for point, row in zip(domain.points, records):
        if row['architecture'] != dict(px=point.px, py=point.py, capacity_bytes=point.capacity_bytes):
            raise ValueError('reference hardware ordering mismatch')
        bound = lower_bound(case, point, mode)
        for vector in row['vectors']:
            e, t = vector['Total<SEP>energy'], vector['Total<SEP>latency']
            if Fraction.from_float(e) < bound.energy or Fraction.from_float(t) < bound.latency:
                raise AssertionError(f'inadmissible bound at {point}: {bound.record()} vs {vector}')
        checks.append(dict(architecture=row['architecture'], vectors=len(row['vectors']),
                           bound=bound.record(), finite_frontier_admissible=True))
    return checks
