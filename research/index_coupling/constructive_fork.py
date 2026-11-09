"""Executable fork schedules built from strip geometry, without nest search.

This is a small constructive upper-bound family, NOT an exact mapper or an
I/O lower bound. No curve_model/FFM calls occur in candidate construction.
Persistent tensors reserve their full storage throughout the strip loop;
this deliberately conservative lifetime is checked by the cell simulator.
"""
from dataclasses import dataclass, asdict
from itertools import combinations, product


def ceildiv(a, b):
    return (a + b - 1) // b


@dataclass(frozen=True)
class Plan:
    shape: tuple
    cross: bool
    kind: str
    tile: int
    kept: tuple = ()
    producer_axis: str = "I"

    def __post_init__(self):
        if len(self.shape) != 4 or any(type(n) is not int or n < 1 for n in self.shape):
            raise ValueError("four positive integer dimensions required")
        i, _, k, _ = self.shape
        limit = {"rows": i, "cols": k, "whole": max(i, k)}.get(self.kind)
        if limit is None or type(self.tile) is not int or not 1 <= self.tile <= limit:
            raise ValueError("invalid strip kind/tile")
        allowed = ({"B", "C", "V" if self.cross else "D"} if self.kind == "rows"
                   else {"A", "U", "D" if self.cross else "V"} if self.kind == "cols"
                   else set())
        if len(set(self.kept)) != len(self.kept) or not set(self.kept) <= allowed:
            raise ValueError("invalid persistent tensors")
        if self.producer_axis not in ("I", "K"):
            raise ValueError("producer axis must be I or K")

    def metrics(self):
        """Exact counts for this schedule; independent execution checks them."""
        i, j, k, l = self.shape
        b, held = self.tile, set(self.kept)
        reads, writes = {}, {}
        if self.kind == "rows":
            p = ceildiv(i, b)
            reads = dict(A=i*j, B=j*k*(1 if "B" in held else p),
                         C=k*l*(1 if "C" in held else p))
            writes = dict(U=i*l)
            last = "V" if self.cross else "D"
            if self.cross:
                reads["D"] = i*l
                writes["V"] = k*l*(1 if "V" in held else p)
                if "V" not in held and p > 1:
                    reads["V"] = k*l*(p-1)
            else:
                reads["D"] = k*l*(1 if "D" in held else p)
                writes["V"] = i*l
            sizes = dict(B=j*k, C=k*l, D=k*l, V=k*l)
            peak = sum(sizes[t] for t in held) + b*k + b + max(t not in held for t in ("B", "C", last))
        elif self.kind == "cols":
            p = ceildiv(k, b)
            reads = dict(A=i*j*(1 if "A" in held else p), B=j*k, C=k*l)
            writes = dict(U=i*l*(1 if "U" in held else p))
            if "U" not in held and p > 1:
                reads["U"] = i*l*(p-1)
            last = "D" if self.cross else "V"
            if self.cross:
                reads["D"] = i*l*(1 if "D" in held else p)
                writes["V"] = k*l
            else:
                reads["D"] = k*l
                writes["V"] = i*l*(1 if "V" in held else p)
                if "V" not in held and p > 1:
                    reads["V"] = i*l*(p-1)
            sizes = dict(A=i*j, U=i*l, D=i*l, V=i*l)
            peak = sum(sizes[t] for t in held) + i*b + b + max(t not in held for t in ("A", "U", last))
        else:
            ri, rk = min(b, i), min(b, k)
            if self.producer_axis == "I":
                reads = dict(A=i*j, B=ceildiv(i, ri)*j*k)
            else:
                reads = dict(A=ceildiv(k, rk)*i*j, B=j*k)
            reads["C"] = ceildiv(i, ri)*k*l
            reads["D"] = ceildiv(k, rk)*i*l if self.cross else ceildiv(i, ri)*k*l
            writes = dict(U=i*l, V=k*l if self.cross else i*l)
            scratch = [ri if self.producer_axis == "I" else rk, ri, rk if self.cross else ri]
            peak = i*k + max(scratch) + 1
        return dict(peak=peak, traffic=sum(reads.values())+sum(writes.values()),
                    reads=dict(sorted(reads.items())), writes=dict(sorted(writes.items())))

    def record(self):
        return dict(asdict(self), **self.metrics())


def candidates(shape, cross, all_tiles=False):
    """O(log I + log K) strip sizes, eight retention masks, two whole-X orders.

    all_tiles=True also admits nondivisor strips with a smaller final strip.
    This wider grammar is deliberately distinguished in the comparison.
    """
    i, _, k, _ = shape
    def tiles(n):
        return range(1, n+1) if all_tiles else sorted({n} | {1 << s for s in range(n.bit_length())})
    for kind, n, names in (("rows", i, ("B", "C", "V" if cross else "D")),
                           ("cols", k, ("A", "U", "D" if cross else "V"))):
        for b in tiles(n):
            for count in range(4):
                for held in combinations(names, count):
                    yield Plan(tuple(shape), cross, kind, b, held)
    for b, axis in product(tiles(max(i, k)), ("I", "K")):
        yield Plan(tuple(shape), cross, "whole", b, producer_axis=axis)


def frontier(plans):
    scored = sorted(((p.metrics()["peak"], p.metrics()["traffic"], p) for p in plans),
                    key=lambda row: row[:2])
    out, best = [], float("inf")
    for peak, traffic, plan in scored:
        if traffic < best:
            out.append(plan)
            best = traffic
    return out


def execute(plan):
    """Emit allocations and MACs directly; never use metrics() or nest search."""
    from .nest_model import coupling
    from .simulate_nest import Specification, Machine
    graph = coupling(*plan.shape, plan.cross)
    spec = Specification(graph)
    machine = Machine(spec)
    all_bounds = spec.bounds

    def cells(tensor, bounds):
        return spec.cells((tensor,), bounds)

    def reserve(cs):
        fresh = cs - machine.buffer
        machine.allocate(fresh)
        return fresh

    def kernel(op, bounds, outer, vector, middle, scalar, inner):
        # The remaining index ranges and tensor coordinates come from the graph,
        # not from the analytic traffic formulas above.
        for a in bounds[outer]:
            outer_bounds = dict(bounds, **{outer: range(a, a+1)})
            vec = reserve(cells(vector, outer_bounds))
            for b in bounds[middle]:
                middle_bounds = dict(outer_bounds, **{middle: range(b, b+1)})
                one = reserve(cells(scalar, middle_bounds))
                for c in bounds[inner]:
                    position = {outer: a, middle: b, inner: c}
                    machine.step(op, tuple(position[v] for v in spec.variables[op]))
                machine.release(one)
            machine.release(vec)

    def chunks(axis, tile, bounds):
        ran = bounds[axis]
        for start in range(ran.start, ran.stop, tile):
            yield dict(bounds, **{axis: range(start, min(start+tile, ran.stop))})

    persistent = reserve(spec.cells(plan.kept, all_bounds))
    if plan.kind in ("rows", "cols"):
        rows = plan.kind == "rows"
        for bounds in chunks("I" if rows else "K", plan.tile, all_bounds):
            x = reserve(cells("X", bounds))
            if rows:
                kernel("EX", bounds, "J", "A", "K", "B", "I")
                kernel("EU", bounds, "L", "U", "K", "C", "I")
                kernel("EV", bounds, "L", "D" if plan.cross else "V", "K",
                       "V" if plan.cross else "D", "I")
            else:
                kernel("EX", bounds, "J", "B", "I", "A", "K")
                kernel("EU", bounds, "L", "C", "I", "U", "K")
                kernel("EV", bounds, "L", "V" if plan.cross else "D", "I",
                       "D" if plan.cross else "V", "K")
            machine.release(x)
    else:
        x = reserve(cells("X", all_bounds))
        axis = plan.producer_axis
        for bounds in chunks(axis, plan.tile, all_bounds):
            if axis == "I":
                kernel("EX", bounds, "J", "A", "K", "B", "I")
            else:
                kernel("EX", bounds, "J", "B", "I", "A", "K")
        for bounds in chunks("I", plan.tile, all_bounds):
            kernel("EU", bounds, "L", "U", "K", "C", "I")
        for bounds in chunks("K" if plan.cross else "I", plan.tile, all_bounds):
            if plan.cross:
                kernel("EV", bounds, "L", "V", "I", "D", "K")
            else:
                kernel("EV", bounds, "L", "V", "K", "D", "I")
        machine.release(x)
    machine.release(persistent)
    return machine.finish()
