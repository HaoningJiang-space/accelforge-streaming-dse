"""Symbolic, correlated effects for one declared three-Matmul grammar.

Construction imports no AccelForge code and evaluates no concrete tile. Counts
are generated from loop multiplicities, not a table of evaluated mappings.
"""
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
import sympy as sp


@dataclass(frozen=True)
class Plan:
    stripe: int
    tiles: tuple  # ((k0,j0), (k1,j1), (k2,j2))


@dataclass(frozen=True)
class Effect:
    # Canonical max(base, x+carried); None means no x-dependent branch.
    base: int
    carried: object = None

    def __post_init__(self):
        if self.base < 0 or (self.carried is not None and not 0 <= self.carried <= self.base):
            raise ValueError('invalid canonical scoped effect')

    def at(self, x):
        if x < 0:
            raise ValueError('negative external reservation')
        return self.base if self.carried is None else max(self.base, self.carried+x)

    def no_larger_than(self, other):
        # At x=0 and asymptotically: necessary and sufficient for all x>=0.
        if self.base > other.base:
            return False
        if self.carried is None:
            return True
        return other.carried is not None and self.carried <= other.carried

    def join(self, other):
        carried=[v for v in (self.carried,other.carried) if v is not None]
        return Effect(max(self.base,other.base),max(carried) if carried else None)


@dataclass(frozen=True)
class State:
    peak: int
    energy: int  # femtojoules, exact
    latency: Fraction  # nanoseconds, exact
    tiles: tuple
    effect: Effect = Effect(0)

    @property
    def vector(self):
        return self.peak, self.energy, self.latency


def dominates(a, b, grounded=False):
    if grounded:
        return all(x <= y for x,y in zip(a.vector,b.vector))
    return a.effect.no_larger_than(b.effect) and a.energy <= b.energy and a.latency <= b.latency


def frontier(states, grounded=False):
    """Pointwise effect frontier, or explicitly grounded numeric frontier."""
    result = []
    for state in states:
        if any(dominates(old, state, grounded) for old in result):
            continue
        result = [old for old in result if not dominates(state, old, grounded)]
        result.append(state)
    return result


def combine(left, right):
    return State(max(left.peak, right.peak), left.energy + right.energy,
                 left.latency + right.latency, left.tiles + right.tiles, left.effect.join(right.effect))


class Family:
    """Uniform 8-bit square chain; exact power-of-two finite tile domains.

    Fixed PE shape 64x96, native 1-GHz / 38.4-GB/s DRAM / 512/128-GB/s
    GB ports. The upper size bound guarantees exact integral binary lambdify
    counts (<2**53); latency and energy arithmetic are subsequently exact.
    """
    names = ('dram_read', 'dram_write', 'gb_read', 'gb_write', 'mac', 'cycles')

    def __init__(self, n=256, stripes=(64, 128, 256), tiles=(32, 64)):
        def power2(x):
            return type(x) is int and x > 0 and x & (x - 1) == 0
        if not power2(n) or n > 1024:
            raise ValueError('supported matrix size: powers of two up to 1024')
        if not stripes or not tiles or len(set(stripes)) != len(stripes) or len(set(tiles)) != len(tiles):
            raise ValueError('nonempty, unique domains required')
        if any(not power2(x) or x > n for x in (*stripes, *tiles)) or max(tiles) > 64:
            raise ValueError('invalid tile/stripe or fixed-array demand')
        self.n, self.stripes, self.tiles = n, tuple(stripes), tuple(tiles)
        N, s, k, j = sp.symbols('N s k j', positive=True, integer=True)
        self.symbols = N, s, k, j
        V = N**3
        self.counts = (
            (N**2 + V/s, 0, N**2 + V/j + N**2*(N/k-1),
             N**2 + V/s + V/k, V, V/(k*j)),
            (N**2, 0, N**2 + V/j + N**2*(N/k-1),
             N**2 + V/k, V, V/(k*j)),
            (N**2, N**2, N**2 + V/j + V/k,
             N**2 + V/k, V, V/(k*j)),
        )
        # The continuation backing T2 enters the producer only with >1 stripe.
        self.peaks = (N*s + N*k + k*j + sp.Piecewise((N**2, s < N), (0, True)),
                      N*s + N**2 + k*j,
                      N**2 + N*j + k*j)
        self.bases = (N*s + N*k + k*j, N*s + k*j, N*j + k*j)
        self.carries = (sp.Piecewise((1,s < N),(0,True)),sp.Integer(1),sp.Integer(1))
        self._uses_s = tuple(any(s in sp.sympify(e).free_symbols for e in (*c, p))
                             for c, p in zip(self.counts, self.peaks))
        self._functions = [sp.lambdify(self.symbols, (*c,p,b,r), 'math', cse=True)
                           for c,p,b,r in zip(self.counts,self.peaks,self.bases,self.carries)]
        x, y, z = sp.symbols('x y z', nonnegative=True, integer=True)
        self.obligations = x, y, z
        self.effect = sp.Max(N*s + N*k + k*j + sp.Piecewise((x, s < N), (0, True)), y, z)
        self.factor_calls = 0

    def legal_tiles(self, stage, stripe):
        for k, j in product(self.tiles, repeat=2):
            if (stage != 0 or stripe % j == 0) and (stage != 1 or stripe % k == 0):
                yield k, j

    def plans(self):
        for stripe in self.stripes:
            for tiles in product(*(tuple(self.legal_tiles(i, stripe)) for i in range(3))):
                yield Plan(stripe, tiles)

    def factor_key(self, stage, stripe, k, j):
        # Proven by free-symbol inspection before any concrete evaluation:
        # stage 2 is independent of the separator stripe. Do not merge stage 0/1.
        return stage, stripe if self._uses_s[stage] else None, k, j

    def factor(self, stage, stripe, k, j):
        if stage not in range(3) or stripe not in self.stripes or (k, j) not in self.legal_tiles(stage, stripe):
            raise ValueError('outside the declared family')
        self.factor_calls += 1
        raw = self._functions[stage](self.n, stripe, k, j)
        if any(v < 0 or int(v) != v or v >= 2**53 for v in raw):
            raise AssertionError('inexact/noninteger symbolic count')
        dr,dw,gr,gw,mac,cycles,peak,base,carries = map(int,raw)
        effect=Effect(base,base if carries else None)
        assert effect.at(self.n**2)==peak
        # Native NVDLA per-bit energies converted to per-byte femtojoules.
        energy = (dr+dw)*56240 + gr*1992 + gw*2344 + mac*84
        latency = max(Fraction(cycles), Fraction((dr+dw)*5, 192),
                      Fraction(gr, 512), Fraction(gw, 128))
        return State(peak,energy,latency,((k,j),),effect)

    def formulas(self):
        return dict(scoped_effect=str(self.effect), phases=[dict(stage=i, counts={k: str(v) for k, v in zip(self.names, counts)},
                     scoped_peak_bytes=str(peak),effect_base=str(self.bases[i]),carries_T2=str(self.carries[i]))
                for i, (counts, peak) in enumerate(zip(self.counts, self.peaks))])
