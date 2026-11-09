"""Two-dimensional X tiles with retention scoped to the outer tile loop.

Constructive schedules, not a complete mapspace. EX finishes each X tile;
both consumers then use it before release. Partial U/V may spill. A subset
of tensors invariant across the INNER tile loop can instead remain resident.
Construction uses O(number_of_I_tiles * number_of_K_tiles) constant-size
descriptors, with two orders and at most eight retention masks. No recursive
nest enumeration, curve_model, native model or stored answers are consulted.
"""
from dataclasses import asdict, dataclass
from itertools import combinations, product

from .constructive_fork import ceildiv


@dataclass(frozen=True)
class TiledPlan:
    shape: tuple
    cross: bool
    outer: str
    rows: int
    cols: int
    kept: tuple = ()

    def __post_init__(self):
        if len(self.shape) != 4 or any(type(n) is not int or n < 1 for n in self.shape):
            raise ValueError("four positive integer dimensions required")
        i, _, k, _ = self.shape
        if self.outer not in ("I", "K"):
            raise ValueError("invalid outer tile axis")
        if (type(self.rows) is not int or type(self.cols) is not int
                or not 1 <= self.rows <= i or not 1 <= self.cols <= k):
            raise ValueError("invalid tile shape")
        allowed = ({"A", "U", "D" if self.cross else "V"} if self.outer == "I"
                   else {"B", "C", "V" if self.cross else "D"})
        if len(set(self.kept)) != len(self.kept) or not set(self.kept) <= allowed:
            raise ValueError("retention must be invariant across the inner tile axis")

    def metrics(self):
        i, j, k, l = self.shape
        r, c, held = self.rows, self.cols, set(self.kept)
        p, q = ceildiv(i, r), ceildiv(k, c)
        reads = dict(A=i*j*(1 if "A" in held else q),
                     B=j*k*(1 if "B" in held else p),
                     C=k*l*(1 if "C" in held else p))
        writes = dict(U=i*l*(1 if "U" in held else q))
        if "U" not in held and q > 1:
            reads["U"] = i*l*(q-1)
        if self.cross:
            reads["D"] = i*l*(1 if "D" in held else q)
            writes["V"] = k*l*(1 if "V" in held else p)
            if "V" not in held and p > 1:
                reads["V"] = k*l*(p-1)
        else:
            reads["D"] = k*l*(1 if "D" in held else p)
            writes["V"] = i*l*(1 if "V" in held else q)
            if "V" not in held and q > 1:
                reads["V"] = i*l*(q-1)

        sizes = (dict(A=r*j, U=r*l, D=r*l, V=r*l) if self.outer == "I"
                 else dict(B=j*c, C=c*l, D=c*l, V=c*l))
        # Each vector/scalar order performs the same transfers on a finished X
        # tile. Select the smaller scratch requirement independently per stage.
        scratch = []
        for vrow, scalar in (("A", "B"), ("U", "C"),
                             ("D", "V") if self.cross else ("V", "D")):
            scratch.append(min(r*(vrow not in held)+(scalar not in held),
                               c*(scalar not in held)+(vrow not in held)))
        peak = sum(sizes[t] for t in held) + r*c + max(scratch)
        return dict(peak=peak, traffic=sum(reads.values())+sum(writes.values()),
                    reads=dict(sorted(reads.items())), writes=dict(sorted(writes.items())))

    def record(self):
        return dict(asdict(self), kind="two_dimensional", **self.metrics())


def candidates(shape, cross, all_tiles=False, retention=True):
    i, _, k, _ = shape
    def tiles(n):
        return range(1, n+1) if all_tiles else sorted({n} | {1 << s for s in range(n.bit_length())})
    for outer in ("I", "K"):
        names = (("A", "U", "D" if cross else "V") if outer == "I"
                 else ("B", "C", "V" if cross else "D"))
        for rows, cols in product(tiles(i), tiles(k)):
            for count in range(4 if retention else 1):
                for kept in combinations(names, count):
                    yield TiledPlan(tuple(shape), cross, outer, rows, cols, kept)


def duals(shape, cross, all_tiles=False):
    """Cost-preserving alternatives to nonretaining row/column strips.

    Instead of retaining the X strip, retain the operand/output slices and
    stream the other X axis one cell wide. This is a post-ablation candidate
    subset; it is NOT claimed to replace all scoped-retention alternatives.
    """
    i, _, k, _ = shape
    def tiles(n):
        return range(1, n+1) if all_tiles else sorted({n} | {1 << s for s in range(n.bit_length())})
    for r in tiles(i):
        yield TiledPlan(tuple(shape), cross, "I", r, 1, ("A", "U", "D" if cross else "V"))
    for c in tiles(k):
        yield TiledPlan(tuple(shape), cross, "K", 1, c, ("B", "C", "V" if cross else "D"))


def execute(plan):
    """Cell execution chooses microkernel order from explicit reservations.

    No call to metrics(); reservation/traffic formulas are not used here.
    The same independent Machine used by the original experiments validates
    final reductions, no recomputation, lifetimes, DRAM copies and outputs.
    """
    from .nest_model import coupling
    from .simulate_nest import Machine, Specification
    spec = Specification(coupling(*plan.shape, plan.cross))
    machine = Machine(spec)

    def reserve(cells):
        fresh = cells - machine.buffer
        machine.allocate(fresh)
        return fresh

    def tensor(t, bounds):
        return spec.cells((t,), bounds)

    def chunks(bounds, axis, width):
        for start in range(bounds[axis].start, bounds[axis].stop, width):
            yield dict(bounds, **{axis: range(start, min(start+width, bounds[axis].stop))})

    def kernel(op, bounds, orders):
        def scratch(order):
            outer, vector, middle, scalar, _ = order
            a, b = bounds[outer].start, bounds[middle].start
            one_outer = dict(bounds, **{outer: range(a, a+1)})
            one_middle = dict(one_outer, **{middle: range(b, b+1)})
            return len((tensor(vector, one_outer) | tensor(scalar, one_middle))-machine.buffer)
        outer, vector, middle, scalar, inner = min(orders, key=scratch)
        for a in bounds[outer]:
            one_outer = dict(bounds, **{outer: range(a, a+1)})
            vec = reserve(tensor(vector, one_outer))
            for b in bounds[middle]:
                one_middle = dict(one_outer, **{middle: range(b, b+1)})
                one = reserve(tensor(scalar, one_middle))
                for c in bounds[inner]:
                    pos = {outer: a, middle: b, inner: c}
                    machine.step(op, tuple(pos[v] for v in spec.variables[op]))
                machine.release(one)
            machine.release(vec)

    inner = "K" if plan.outer == "I" else "I"
    widths = dict(I=plan.rows, K=plan.cols)
    for outer_bounds in chunks(spec.bounds, plan.outer, widths[plan.outer]):
        persistent = reserve(spec.cells(plan.kept, outer_bounds))
        for bounds in chunks(outer_bounds, inner, widths[inner]):
            x = reserve(tensor("X", bounds))
            kernel("EX", bounds, [("J", "A", "K", "B", "I"), ("J", "B", "I", "A", "K")])
            kernel("EU", bounds, [("L", "U", "K", "C", "I"), ("L", "C", "I", "U", "K")])
            orders = ([("L", "D", "K", "V", "I"), ("L", "V", "I", "D", "K")]
                      if plan.cross else
                      [("L", "V", "K", "D", "I"), ("L", "D", "I", "V", "K")])
            kernel("EV", bounds, orders)
            machine.release(x)
        machine.release(persistent)
    return machine.finish()
