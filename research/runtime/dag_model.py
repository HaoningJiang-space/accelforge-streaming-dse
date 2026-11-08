"""Dense row-local DAGs and topological fusion segments."""

from collections import Counter
from dataclasses import dataclass
from functools import cached_property


@dataclass(frozen=True)
class Op:
    name: str
    inputs: tuple[str, ...]
    width: int
    kind: str = "gemm"


@dataclass(frozen=True)
class Graph:
    rows: int
    inputs: tuple[tuple[str, int], ...]
    ops: tuple[Op, ...]

    def __post_init__(self):
        widths = dict(self.inputs)
        if self.rows < 1 or len(widths) != len(self.inputs) or not self.ops or min(widths.values(), default=0) < 1:
            raise ValueError("invalid DAG extents")
        for op in self.ops:
            if (op.name in widths or op.width < 1 or len(set(op.inputs)) != len(op.inputs)
                    or any(x not in widths for x in op.inputs)):
                raise ValueError("invalid tensor name or dependency order")
            if op.kind == "gemm" and len(op.inputs) == 1:
                pass
            elif op.kind in ("add", "mul") and len(op.inputs) == 2 and all(widths[x] == op.width for x in op.inputs):
                pass
            else:
                raise ValueError("unsupported affine operator")
            widths[op.name] = op.width

    @cached_property
    def widths(self):
        return dict(self.inputs) | {op.name: op.width for op in self.ops}

    @cached_property
    def operators(self):
        return {op.name: op for op in self.ops}

    @cached_property
    def users(self):
        result = {name: [] for name in self.widths}
        for op in self.ops:
            for name in op.inputs:
                result[name].append(op.name)
        return {name: tuple(users) for name, users in result.items()}

    @property
    def outputs(self):
        return tuple(op.name for op in self.ops if not self.users[op.name])

    def weight_words(self, op):
        return self.widths[op.inputs[0]] * op.width if op.kind == "gemm" else 0


@dataclass(frozen=True)
class Group:
    order: tuple[str, ...]
    rows: int
    tiles: tuple[tuple[int, int], ...]
    pinned: tuple[bool, ...]


@dataclass(frozen=True)
class Lifetime:
    op: Op
    fetch: tuple[str, ...]
    release: tuple[str, ...]
    drain: bool
    live_width: int


def lifetimes(graph, order):
    """Static projection of a group's activation intervals."""
    members = set(order)
    positions = {name: i for i, name in enumerate(order)}
    uses = Counter(x for name in order for x in graph.operators[name].inputs)
    live = set()
    for i, name in enumerate(order):
        op = graph.operators[name]
        if any(x in members and positions[x] >= i for x in op.inputs):
            raise ValueError("group order reads an internal value before production")
        fetch = tuple(x for x in op.inputs if x not in live)
        if any(x in members for x in fetch):
            raise ValueError("missing internal value")
        live.update(fetch)
        live.add(name)
        width = sum(graph.widths[x] for x in live)
        for tensor in op.inputs:
            uses[tensor] -= 1
        release = tuple(x for x in (*op.inputs, name) if uses[x] == 0)
        live.difference_update(release)
        drain = not graph.users[name] or any(x not in members for x in graph.users[name])
        yield Lifetime(op, fetch, release, drain, width)


def validate_plan(graph, hardware, plan):
    ready = set(dict(graph.inputs))
    for group in plan:
        size = len(group.order)
        if not (size and 1 <= group.rows <= graph.rows and len(group.tiles) == len(group.pinned) == size):
            raise ValueError("invalid fusion group")
        for name, (p, q), pin in zip(group.order, group.tiles, group.pinned):
            if name in ready or name not in graph.operators:
                raise ValueError("duplicate or unknown operation")
            op = graph.operators[name]
            if not set(op.inputs) <= ready:
                raise ValueError("operation is not ready in the DAG")
            if op.kind == "gemm":
                if not (1 <= p <= min(hardware.py, graph.widths[op.inputs[0]])
                        and 1 <= q <= min(hardware.px, op.width)):
                    raise ValueError("GEMM tile exceeds the array")
            elif pin or p != 0 or not 1 <= q <= min(hardware.px * hardware.py, op.width):
                raise ValueError("pointwise tile exceeds the array")
            ready.add(name)
    if ready != set(graph.widths):
        raise ValueError("incomplete DAG plan")
