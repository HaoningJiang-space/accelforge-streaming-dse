"""Typed, lossless representation of the default exact v2 serial grammar.

No search, pruning, caching or native cost helpers. Entries are solve/group,
plus the internal whole-scalar-part Hold entry. Costs exclude caller residency
and compulsory traffic. Global order is fixed; tiles repeat one child template.
"""
from dataclasses import dataclass
from math import prod
import re


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def tuples(value):
    """Restore native tuples after JSON archival."""
    return tuple(map(tuples, value)) if isinstance(value, (list, tuple)) else value


@dataclass(frozen=True)
class Plan:
    kind: str
    ops: tuple
    entry: str
    kept: tuple = ()
    dropped: tuple = ()
    rank: str = ''
    tile: int = 0
    trips: int = 0
    children: tuple = ()


class Model:
    """Read declarations only; restricted to valid single-writer DAG orders."""
    def __init__(self, graph, tile_domain='halving'):
        require(tile_domain in ('halving', 'divisors'), 'unsupported tile domain')
        self.tile_domain = tile_domain
        self.ops = tuple(graph.ops)
        self.sizes = dict(graph.sizes)
        require(self.ops and len(set(self.ops)) == len(self.ops), 'empty/duplicate operators')
        require(all(type(x) is int and x > 0 for x in self.sizes.values()), 'bad extents')
        self.access, self.inputs, self.output, self.dims, self.writer = {}, {}, {}, {}, {}
        for op in self.ops:
            access = graph.access[op]
            require(bool(access), 'operator has no output')
            self.access[op] = set(access)
            self.inputs[op] = set(tuple(access)[:-1])
            out = self.output[op] = tuple(access)[-1]
            require(out not in self.writer, 'multiple writers')
            self.writer[out] = op
            for t, ds in access.items():
                ds = tuple(ds)
                require(len(set(ds)) == len(ds) and set(ds) <= self.sizes.keys(), 'bad dimensions')
                require(t not in self.dims or self.dims[t] == ds, 'inconsistent tensor projection')
                self.dims[t] = ds
        position = {o: i for i, o in enumerate(self.ops)}
        require(all(t not in self.writer or position[self.writer[t]] < position[o]
                    for o in self.ops for t in self.inputs[o]), 'non-topological order')
        self.consumed = set().union(*self.inputs.values())
        self.domains = {o: set().union(*(set(self.dims[t]) for t in self.access[o])) for o in self.ops}

    def tensors(self, ops):
        return set().union(*(self.access[o] for o in ops))

    def made(self, ops):
        return {self.output[o] for o in ops}

    def size(self, t, ext):
        return prod(ext[v] for v in self.dims[t])

    def scalar(self, ops, ext, resident):
        return all(self.size(t, ext) == 1 for t in self.tensors(ops) - resident)

    def tiles(self, extent):
        if self.tile_domain == 'divisors':
            return {b for b in range(1, extent) if extent % b == 0}
        result, b = set(), extent // 2
        while b:
            if extent % b == 0:
                result.add(b)
            b //= 2
        return result

    def child_entry(self, parent, child, ext, resident):
        if child == parent and len(child) > 1 and self.scalar(child, ext, resident):
            return 'hold'
        return 'group'


def decode(graph, witness, *, entry='solve', external=(), tile_domain='halving'):
    """Read flat notes with native entry types; analyze() checks all guards."""
    model, notes, pos = Model(graph, tile_domain), tuples(witness), 0
    require(entry in ('solve', 'group'), 'invalid root entry')

    def read(ops, ext, resident, mode):
        nonlocal pos
        scalar = model.scalar(ops, ext, resident)
        if scalar and len(ops) == 1 and mode != 'hold':
            return Plan('leaf', ops, mode)
        require(pos < len(notes), 'truncated witness')
        note = notes[pos]
        pos += 1
        require(bool(note), 'empty note')
        if mode == 'hold':
            require(len(note) == 2 and note == ('hold', ops), 'whole scalar part requires Hold')
            return Plan('hold', ops, mode)
        if mode == 'solve' or scalar:
            require(len(note) == 6 and note[0] == 'groups'
                    and note[2] == 'kept' and note[4] == 'via DRAM', 'expected Partition')
            groups, kept, dropped = note[1], note[3], note[5]
            require(groups and all(groups) and sum(groups, ()) == ops, 'partition span/order mismatch')
            children = tuple(read(g, ext, resident | set(kept),
                                  model.child_entry(ops, g, ext, resident | set(kept))) for g in groups)
            return Plan('partition', ops, mode, kept, dropped, children=children)
        require(len(note) == 8 and note[0] == 'loop' and note[1] == ops
                and note[4] == 'kept' and note[6] == 'refetched', 'expected Loop')
        match = re.fullmatch(r'tile (\d+) x(\d+)', note[3])
        require(match is not None and note[2] in ext, 'bad loop notation')
        tile, trips = map(int, match.groups())
        child = read(ops, dict(ext, **{note[2]: tile}), resident | set(note[5]), 'solve')
        return Plan('loop', ops, mode, note[5], note[7], note[2], tile, trips, (child,))

    plan = read(model.ops, model.sizes, set(external), entry)
    require(pos == len(notes), 'unused witness notes')
    # Numeric evaluation is also full structural validation; no cost is trusted
    # from the witness or from the source solver.
    analyze(graph, plan, entry=entry, external=external, tile_domain=tile_domain)
    return plan


def encode(plan):
    if plan.kind == 'leaf':
        return ()
    if plan.kind == 'hold':
        return (('hold', plan.ops),)
    if plan.kind == 'partition':
        head = ('groups', tuple(c.ops for c in plan.children), 'kept', plan.kept, 'via DRAM', plan.dropped)
    elif plan.kind == 'loop':
        head = ('loop', plan.ops, plan.rank, f'tile {plan.tile} x{plan.trips}',
                'kept', plan.kept, 'refetched', plan.dropped)
    else:
        raise ContractError('unknown node')
    return (head,) + sum((encode(c) for c in plan.children), ())


def analyze(graph, plan, *, entry='solve', external=(), owned=(), tile_domain='halving'):
    """Check typed native membership and calculate each closed invocation.

    This is a recurrence certificate, not an independent cell execution.
    Caller must use simulate_nest for numeric correctness/DRAM validation.
    """
    model = Model(graph, tile_domain)
    require(entry in ('solve', 'group'), 'invalid root entry')
    require(set(external) | set(owned) <= model.dims.keys(), 'unknown boundary tensor')
    calls = []

    def visit(node, ops, ext, resident, writes, mode):
        require(node.ops == ops and node.entry == mode, 'scope/entry mismatch')
        tensors, made = model.tensors(ops), model.made(ops)
        resident, writes = resident & tensors, writes & made
        live, scalar = tensors - resident, model.scalar(ops, ext, resident)
        kept, dropped = set(node.kept), set(node.dropped)
        require(len(kept) == len(node.kept) and len(dropped) == len(node.dropped)
                and not kept & dropped, 'duplicate/overlapping decisions')
        if node.kind != 'loop':
            require(not node.rank and node.tile == 0 and node.trips == 0, 'unexpected loop frame')
        if node.kind in ('leaf', 'hold'):
            require(scalar and not node.children and not kept and not dropped, 'invalid scalar leaf')
            require((node.kind == 'leaf' and len(ops) == 1 and mode != 'hold')
                    or (node.kind == 'hold' and len(ops) > 1 and mode == 'hold'), 'wrong Hold/leaf entry')
            result = (len(live), 0)
        elif node.kind == 'partition':
            require(mode != 'hold' and (mode == 'solve' or scalar), 'group must loop before partition')
            require(not (scalar and len(ops) == 1), 'scalar singleton must be leaf')
            require(node.children and all(c.ops for c in node.children)
                    and sum((c.ops for c in node.children), ()) == ops, 'partition span/order mismatch')
            users = {t: [i for i, c in enumerate(node.children) if t in model.tensors(c.ops)] for t in live}
            shared = {t for t, uses in users.items() if len(uses) > 1}
            require(kept | dropped == shared, 'missing/extra boundary decision')
            extra = sum(model.size(t, ext) * (len(users[t]) - 1 + (t not in writes)
                        if t in made else len(users[t]) - 1) for t in dropped)
            child_writes = writes | (dropped & made & model.consumed)
            peak = 0
            for i, child in enumerate(node.children):
                reserve = sum(model.size(t, ext) for t in kept if users[t][0] <= i <= users[t][-1])
                cp, cq = visit(child, child.ops, ext, resident | kept, child_writes,
                               model.child_entry(ops, child.ops, ext, resident | kept))
                peak, extra = max(peak, reserve + cp), extra + cq
            result = peak, extra
        elif node.kind == 'loop':
            require(mode == 'group' and not scalar, 'Loop requires nonscalar group entry')
            require(len(node.children) == 1, 'Loop has one uniform body')
            v = node.rank
            require(v in set.intersection(*(model.domains[o] for o in ops)), 'absent common rank')
            inside = made & set().union(*(model.inputs[o] for o in ops))
            require(all(v in model.dims[t] for t in inside - resident), 'unfinished internal reduction')
            require(type(node.tile) is int and type(node.trips) is int
                    and node.tile in model.tiles(ext[v]) and node.trips * node.tile == ext[v], 'illegal tile/trips')
            lacking = {t for t in live if v not in model.dims[t]}
            require(kept | dropped == lacking, 'missing/extra loop obligation')
            cp, cq = visit(node.children[0], ops, dict(ext, **{v: node.tile}), resident | kept, writes, 'solve')
            reserve = sum(model.size(t, ext) for t in kept)
            extra = sum((2 if t in made else 1) * (node.trips - 1) * model.size(t, ext) for t in dropped)
            result = reserve + cp, extra + node.trips * cq
        else:
            raise ContractError('unknown node')
        used = set().union(*(model.domains[o] for o in ops))
        calls.append(dict(entry=mode, operators=list(ops), extents={v: ext[v] for v in sorted(used)},
                          external=sorted(resident), owned=sorted(writes), kind=node.kind,
                          peak=result[0], extra_traffic=result[1],
                          rank=node.rank, tile=node.tile))
        return result

    p, q = visit(plan, model.ops, model.sizes, set(external), set(owned), entry)
    io = (model.consumed - model.writer.keys()) | (model.writer.keys() - model.consumed)
    base = sum(model.size(t, model.sizes) for t in io - set(external))
    return dict(peak=p, extra_traffic=q, compulsory=base, traffic=q + base, calls=calls)
