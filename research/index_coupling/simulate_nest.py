"""Execute curve_model witnesses with explicit cells and DRAM transactions.

Run from the repository root, without creating bytecode:
    PYTHONHASHSEED=0 python3 -B -m research.index_coupling.simulate_nest

Only the CLI imports curve_model (to obtain witnesses and claimed numbers).
The parser/executor use no model size, traffic, or capacity routines. All
allocations enumerate (tensor, coordinate) cells; all traffic is a load/store.
The flat witness's omitted leaves execute the remaining Cartesian iteration
space of each operation in graph order. Unary operations are identity maps;
multi-input operations accumulate products, with unit-byte cells. This matches
the graph's elementwise-softmax abstraction, not actual normalized softmax.

"kept" reserves a whole current tile for the indicated scope. Other cells
live in descendant scopes. On eviction a dirty cell is stored if still needed
or a graph output; a later access reloads it. Thus a producer may pass a cell
locally to one consumer, then save it for another. Static future-use counts
are validation/liveness metadata, never a cache or numeric-value store.
"""

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import product
import json
import os
import re


class InvalidExecution(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidExecution(message)


class Specification:
    """Read only graph declarations, independently of Graph helper methods."""

    def __init__(self, graph):
        self.sizes = dict(graph.sizes)
        self.ops = tuple(graph.ops)
        self.access = {op: dict(graph.access[op]) for op in self.ops}
        self.dims = {}
        self.inputs_of = {}
        self.output_of = {}
        self.variables = {}
        self.producer = {}
        consumed = set()
        for op in self.ops:
            access = self.access[op]
            self.inputs_of[op] = tuple(access)[:-1]
            out = self.output_of[op] = tuple(access)[-1]
            require(out not in self.producer, f"multiple producers for {out}")
            self.producer[out] = op
            consumed.update(self.inputs_of[op])
            for tensor, dims in access.items():
                require(len(dims) == len(set(dims)), "repeated projection dimension")
                require(tensor not in self.dims or self.dims[tensor] == dims,
                        f"inconsistent projection: {tensor}")
                self.dims[tensor] = dims
            self.variables[op] = tuple(sorted({v for ds in access.values() for v in ds}))
        self.inputs = consumed - self.producer.keys()
        self.outputs = self.producer.keys() - consumed
        self.bounds = {v: range(n) for v, n in self.sizes.items()}

    def tensors(self, ops):
        return {t for op in ops for t in self.access[op]}

    def cells(self, tensors, bounds):
        return {(t, ix) for t in tensors
                for ix in product(*(bounds[v] for v in self.dims[t]))}

    def iterations(self, op, bounds):
        return product(*(bounds[v] for v in self.variables[op]))

    def accesses(self, op, iteration):
        position = dict(zip(self.variables[op], iteration))
        return tuple((t, tuple(position[v] for v in ds))
                     for t, ds in self.access[op].items())


@dataclass
class Node:
    kind: str
    ops: tuple
    kept: tuple = ()
    dropped: tuple = ()
    variable: str = ""
    tile: int = 0
    children: tuple = ()


def parse_witness(spec, witness):
    """Recover implicit leaves and subtree boundaries, without cost recurrences."""
    position = 0

    def parse(ops, bounds, external, mode):
        nonlocal position
        local = spec.tensors(ops) - external
        if all(len(bounds[v]) == 1 for t in local for v in spec.dims[t]):
            return Node("leaf", ops)
        require(position < len(witness), "truncated flat witness")
        record = witness[position]
        position += 1
        if mode == "groups":
            require(len(record) == 6 and record[0] == "groups"
                    and record[2] == "kept" and record[4] == "via DRAM",
                    f"expected groups, got {record}")
            groups, kept, dropped = record[1], record[3], record[5]
            require(tuple(op for g in groups for op in g) == ops, "bad partition")
            users = {t: [i for i, g in enumerate(groups) if t in spec.tensors(g)]
                     for t in local}
            shared = {t for t, indices in users.items() if len(indices) > 1}
            require(set(kept).isdisjoint(dropped) and set(kept) | set(dropped) == shared,
                    "inconsistent shared-tensor annotation")
            children = tuple(parse(g, bounds, external | set(kept), "loop") for g in groups)
            return Node("groups", ops, kept, dropped, children=children)
        require(len(record) == 8 and record[0] == "loop" and record[1] == ops
                and record[4] == "kept" and record[6] == "refetched",
                f"expected loop, got {record}")
        variable, kept, dropped = record[2], record[5], record[7]
        match = re.fullmatch(r"tile (\d+) x(\d+)", record[3])
        require(match is not None, "bad tile annotation")
        tile, trips = map(int, match.groups())
        require(0 < tile < len(bounds[variable]) and tile * trips == len(bounds[variable]),
                "bad loop bounds")
        require(all(variable in spec.variables[op] for op in ops), "recomputing loop")
        lacking = {t for t in local if variable not in spec.dims[t]}
        require(set(kept).isdisjoint(dropped) and set(kept) | set(dropped) == lacking,
                "inconsistent loop retention annotation")
        inner = dict(bounds, **{variable: range(tile)})
        child = parse(ops, inner, external | set(kept), "groups")
        return Node("loop", ops, kept, dropped, variable, tile, (child,))

    root = parse(spec.ops, spec.bounds, set(), "groups")
    require(position == len(witness), "unused flat witness records")
    return root


def events(spec, node, bounds=None, external=frozenset()):
    """Yield actual cell reservations/releases and scalar arithmetic steps."""
    if bounds is None:
        bounds = spec.bounds
    if node.kind == "leaf":
        cells = spec.cells(spec.tensors(node.ops) - external, bounds)
        yield "allocate", cells
        for op in node.ops:
            for iteration in spec.iterations(op, bounds):
                yield "step", (op, iteration)
        yield "release", cells
    elif node.kind == "loop":
        cells = spec.cells(node.kept, bounds)
        yield "allocate", cells
        current = bounds[node.variable]
        for start in range(current.start, current.stop, node.tile):
            inner = dict(bounds, **{node.variable: range(start, start + node.tile)})
            yield from events(spec, node.children[0], inner, external | set(node.kept))
        yield "release", cells
    elif node.kind == "groups":
        users = {t: [i for i, child in enumerate(node.children)
                     if t in spec.tensors(child.ops)] for t in node.kept}
        for i, child in enumerate(node.children):
            first = [t for t, uses in users.items() if uses[0] == i]
            last = [t for t, uses in users.items() if uses[-1] == i]
            yield "allocate", spec.cells(first, bounds)
            yield from events(spec, child, bounds, external | set(node.kept))
            yield "release", spec.cells(last, bounds)
    else:
        raise InvalidExecution(f"unknown node: {node.kind}")


def input_value(cell):
    tensor, index = cell
    return 1 + (sum(map(ord, tensor)) + sum((i + 1) * n for i, n in enumerate(index))) % 7


class Machine:
    def __init__(self, spec, trace=False):
        self.spec = spec
        self.trace = trace
        self.buffer = set()              # Explicit (tensor, index) reservations.
        self.values = {}                 # Numeric payload exists only if resident.
        self.dirty = set()
        self.dram = {cell: (input_value(cell), 0)
                     for cell in spec.cells(spec.inputs, spec.bounds)}
        self.reads = Counter()
        self.writes = Counter()
        self.partial_reads = Counter()
        self.partial_writes = Counter()
        self.expected = {}               # Exact operation index tuples, not a formula.
        self.seen = defaultdict(set)
        self.required = Counter()        # Number of contributions to each output cell.
        self.done = Counter()
        self.future_reads = Counter()
        for op in spec.ops:
            iterations = self.expected[op] = set(spec.iterations(op, spec.bounds))
            for iteration in iterations:
                accesses = spec.accesses(op, iteration)
                self.required[accesses[-1]] += 1
                self.future_reads.update(accesses[:-1])
        self.peak = 0
        self.peak_cells = ()
        self.steps = 0
        self.consumer_checks = 0

    def transfer(self, direction, cell, value):
        if self.trace:
            print(json.dumps({"event": direction, "cell": cell, "value": value,
                              "contributions": self.done[cell], "step": self.steps}))

    def allocate(self, cells):
        require(self.buffer.isdisjoint(cells), "overlapping reservations")
        self.buffer.update(cells)
        if len(self.buffer) > self.peak:
            self.peak = len(self.buffer)
            self.peak_cells = tuple(sorted(self.buffer))

    def load(self, cell, accumulator=False):
        require(cell in self.buffer, f"unreserved access: {cell}")
        if not accumulator:
            self.consumer_checks += 1
            if cell[0] in self.spec.producer:
                require(self.done[cell] == self.required[cell],
                        f"consumer read of nonfinal {cell}: "
                        f"{self.done[cell]}/{self.required[cell]} contributions")
        if cell not in self.values:
            if accumulator and self.done[cell] == 0:
                self.values[cell] = 0
            else:
                require(cell in self.dram, f"lost value, no DRAM backing: {cell}")
                value, version = self.dram[cell]
                require(version == self.done[cell], f"stale DRAM value: {cell}")
                self.values[cell] = value
                self.reads[cell[0]] += 1
                if cell[0] in self.spec.producer and self.done[cell] < self.required[cell]:
                    self.partial_reads[cell[0]] += 1
                self.transfer("read", cell, value)
        return self.values[cell]

    def step(self, op, iteration):
        require(iteration in self.expected[op], f"out-of-domain iteration: {op} {iteration}")
        require(iteration not in self.seen[op], f"recomputation: {op} {iteration}")
        accesses = self.spec.accesses(op, iteration)
        term = 1
        for cell in accesses[:-1]:
            term *= self.load(cell)
            self.future_reads[cell] -= 1
        output = accesses[-1]
        self.values[output] = self.load(output, accumulator=True) + term
        self.done[output] += 1
        self.dirty.add(output)
        self.seen[op].add(iteration)
        self.steps += 1

    def release(self, cells):
        require(cells <= self.buffer, "release of unreserved cells")
        for cell in sorted(cells):
            needed = (self.future_reads[cell] > 0 or cell[0] in self.spec.outputs
                      or self.done[cell] < self.required[cell])
            if cell in self.dirty and needed:
                self.dram[cell] = (self.values[cell], self.done[cell])
                self.writes[cell[0]] += 1
                if self.done[cell] < self.required[cell]:
                    self.partial_writes[cell[0]] += 1
                self.transfer("write", cell, self.values[cell])
            self.dirty.discard(cell)
            self.values.pop(cell, None)
        self.buffer.difference_update(cells)

    def finish(self):
        require(not self.buffer and not self.values, "leaked buffer reservations")
        require(all(self.seen[op] == self.expected[op] for op in self.spec.ops),
                "missing arithmetic iterations")
        require(self.done == self.required, "unfinished reductions")
        require(all(n == 0 for n in self.future_reads.values()), "missing input accesses")
        # Independent, untiled topological execution to validate numeric outputs.
        reference = {c: input_value(c) for c in self.spec.cells(self.spec.inputs, self.spec.bounds)}
        for op in self.spec.ops:
            for iteration in self.spec.iterations(op, self.spec.bounds):
                accesses = self.spec.accesses(op, iteration)
                term = 1
                for cell in accesses[:-1]:
                    term *= reference[cell]
                out = accesses[-1]
                reference[out] = reference.get(out, 0) + term
        outputs = self.spec.cells(self.spec.outputs, self.spec.bounds)
        require(all(c in self.dram and self.dram[c][0] == reference[c] for c in outputs),
                "incorrect or unwritten graph outputs")
        return {"peak": self.peak, "reads": dict(sorted(self.reads.items())),
                "writes": dict(sorted(self.writes.items())),
                "traffic": sum(self.reads.values()) + sum(self.writes.values()),
                "partial_reads": dict(sorted(self.partial_reads.items())),
                "partial_writes": dict(sorted(self.partial_writes.items())),
                "peak_by_tensor": dict(sorted(Counter(t for t, _ in self.peak_cells).items())),
                "steps": self.steps, "consumer_checks": self.consumer_checks,
                "outputs_checked": len(outputs), "valid": True}


def simulate(graph, witness, trace=False):
    spec = Specification(graph)
    root = parse_witness(spec, witness)
    machine = Machine(spec, trace=trace)
    for kind, payload in events(spec, root):
        if kind == "step":
            machine.step(*payload)
        else:
            getattr(machine, kind)(payload)
    return machine.finish()


def self_check():
    """Hand-enumerated traffic, spill/reload, and deliberate dependency violations."""
    from types import SimpleNamespace
    graph = SimpleNamespace(sizes={"I": 2, "J": 2}, ops=("R", "C"), access={
        "R": {"A": ("I", "J"), "X": ("I",)},
        "C": {"X": ("I",), "Y": ("I",)}})
    s = Specification(graph)
    m = Machine(s)
    # Two output cells, two reductions each: spill each partial once.
    for i in range(2):
        for j in range(2):
            cells = {("A", (i, j)), ("X", (i,))}
            m.allocate(cells)
            m.step("R", (i, j))
            m.release(cells)
        cells = {("X", (i,)), ("Y", (i,))}
        m.allocate(cells)
        m.step("C", (i,))
        m.release(cells)
    r = m.finish()
    require((r["peak"], r["reads"], r["writes"]) ==
            (2, {"A": 4, "X": 4}, {"X": 4, "Y": 2}), "hand traffic check failed")
    require(r["partial_reads"] == {"X": 2} and r["partial_writes"] == {"X": 2},
            "partial-sum transfer check failed")
    m = Machine(s)
    m.allocate(s.cells(s.dims, s.bounds))
    m.step("R", (0, 0))
    for action, fragment in [(lambda: m.step("C", (0,)), "nonfinal"),
                             (lambda: m.step("R", (0, 0)), "recomputation")]:
        try:
            action()
        except InvalidExecution as exc:
            require(fragment in str(exc), f"unexpected rejection: {exc}")
        else:
            raise InvalidExecution(f"failed to reject {fragment}")
    # Explicit eviction of a still-needed result must cause a write and a reload.
    return {"hand_spill_traffic": r["traffic"], "reject_partial_consumer": True,
            "reject_recomputation": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="simulate all 216 saved FFM points")
    parser.add_argument("--case", help="exact case label, e.g. 'n4 cross'")
    parser.add_argument("--capacity", type=int, help="select one saved FFM capacity")
    parser.add_argument("--witness", action="store_true", help="include the raw witness in JSON")
    parser.add_argument("--trace", action="store_true", help="print every DRAM transaction")
    parser.add_argument("--self-check", action="store_true", help="run only internal checks")
    args = parser.parse_args()
    print(json.dumps({"self_check": self_check(), "hash_seed": os.environ.get("PYTHONHASHSEED")}))
    if args.self_check:
        return
    # Model imports are deliberately confined to the comparison driver.
    from research.index_coupling.compare_curves import cases
    from research.index_coupling.curve_model import curve
    total = lower = bugs = 0
    for name, graph, ffm in cases():
        if args.case and args.case != name:
            continue
        points = curve(graph, witness=True)
        comparisons = []
        for capacity, ffm_traffic in ffm:
            claimed = min((p for p in points if p[0] <= capacity), key=lambda p: p[1])
            comparisons.append((capacity, ffm_traffic, claimed))
        equals = [r for r in comparisons if r[1] == r[2][1]]
        # One interior equality per graph, plus its plateau; all lower points.
        sample_caps = {equals[len(equals) // 2][0], equals[-1][0]}
        for capacity, ffm_traffic, (model_peak, model_traffic, witness) in comparisons:
            is_lower = model_traffic < ffm_traffic
            if args.capacity is not None:
                if capacity != args.capacity:
                    continue
            elif not args.all and not is_lower and capacity not in sample_caps:
                continue
            result = {"case": name, "capacity": capacity, "ffm_traffic": ffm_traffic,
                      "kind": "lower" if is_lower else "equal",
                      "model_peak": model_peak, "model_traffic": model_traffic}
            try:
                result.update(simulate(graph, witness, trace=args.trace))
                result["model_bug"] = (result["peak"] > model_peak or result["traffic"] > model_traffic)
            except InvalidExecution as exc:
                result.update(valid=False, model_bug=True, error=str(exc))
            if args.witness:
                result["witness"] = witness
            total += 1
            lower += is_lower
            bugs += result["model_bug"]
            print(json.dumps(result, sort_keys=True), flush=True)
    print(json.dumps({"summary": {"points": total, "lower": lower, "equal": total - lower,
                                  "model_bugs": bugs}}))


if __name__ == "__main__":
    main()
