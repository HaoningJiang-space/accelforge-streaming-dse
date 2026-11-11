"""Order-free union responses by downset recursion (DOWNSET_PROTOCOL.md, Gate 3).

`make_downset_kernel()` returns a curve() variant, adapted in memory like
unified_search.make_kernel; graph/curve.py is unchanged:

- state projection canonicalises a span's operator tuple to graph order, so
  every internal order of one operator set shares one cache entry;
- cut_dp is replaced by a dynamic program over the downsets of the span's
  dependency order. Transitions append a group G with D | G a downset; all
  charges are cut_dp's, with positions replaced by sets.

The returned frontier is the Pareto union over all topological orders of the
graph. Witness groups are listed in execution order with canonical member
tuples; `normalize()` rewrites them into the actually executed order and
returns that global order, so the unchanged executor can replay them on the
reordered graph (boundary.resized).
"""
import ast
from pathlib import Path

from research.index_coupling.simulate_nest import Specification, require

CURVE_SOURCE = Path(__file__).resolve().parent.parent / 'index_coupling/graph/curve.py'

DOWNSET_DP = '''
def cut_dp(ops, ext, external, owned):
    # Order-free union over the topological orders of the set `ops`.
    if allowed_mask is not None or empty_groups is not None or not split_shared or not write_through:
        raise ValueError('downset recursion supports default cut-DP options only')
    downsets, after, uses, writer_of = _downset_meta(ops)
    tensors = project(ops)[0]

    def crossing(D):
        return tuple(sorted(t for t in tensors if t not in external and uses[t] & D and uses[t] - D))

    states = {D: {} for D in downsets}
    states[frozenset()][()] = ((0, 0, ((), frozenset(), ()) if witness else ()),)
    for D in downsets:
        if not states[D]:
            continue
        cD = crossing(D)
        for G, D2 in after[D]:
            cD2 = crossing(D2)
            gset = frozenset(G)
            touched = project(G)[0]
            for bits_p, prefix in states[D].items():
                if stats is not None:
                    stats['dp_states'] += 1
                decided = dict(zip(cD, bits_p))
                new = [t for t in cD2 if t not in decided]
                for new_bits in product((True, False), repeat=len(new)):
                    if stats is not None:
                        stats['dp_transitions'] += 1
                    choice = dict(decided, **dict(zip(new, new_bits)))
                    dropped = {t for t, k in choice.items() if not k and t in touched}
                    kept = frozenset(t for t, k in choice.items() if k)
                    across = sum(size(t, ext) for t in kept)
                    extra = 0
                    for t in dropped:
                        w_op = writer_of.get(t)
                        if w_op is not None and t in consumed:
                            extra += size(t, ext) * ((t not in owned) if w_op in gset else 1)
                        elif w_op is None and uses[t] & D:
                            extra += size(t, ext)
                    written_here = frozenset(t for t, k in choice.items()
                                             if not k and writer_of.get(t) is not None and t in consumed)
                    child_owned = owned if legacy_nested_writes else owned | written_here
                    inner = prune(((across + c, q, w) for c, q, w in
                                   part_curve(G, ops, ext, external | kept, child_owned)), max_capacity)
                    bits_q = tuple(choice[t] for t in cD2)
                    decisions = frozenset(choice.items())
                    merged = [(c, q + extra, w if not witness else (w[0] + (G,), w[1] | decisions, join(w[2], wg)))
                              for c, q, w, wg in sweep(prefix, inner, max_capacity)]
                    if merged:
                        states[D2][bits_q] = prune(list(states[D2].get(bits_q, ())) + merged, max_capacity)
    results = []
    for c, q, w in states[frozenset(ops)].get((), ()):
        if witness:
            groups, decisions, inner = w
            note = ('groups', groups, 'kept', tuple(sorted(x for x, k in decisions if k)),
                    'via DRAM', tuple(sorted(x for x, k in decisions if not k)))
            w = join((note,), inner)
        results.append((c, q, w))
    return prune(results, max_capacity, grid)


@lru_cache(maxsize=None)
def _downset_meta(ops):
    members = frozenset(ops)
    writer_of = {output_of(op): op for op in ops}
    preds = {op: frozenset(writer_of[t] for t in graph.access[op] if t != output_of(op) and t in writer_of)
             for op in ops}
    uses = {t: frozenset(op for op in ops if t in graph.access[op]) for t in project(ops)[0]}
    seen, frontier = {frozenset()}, [frozenset()]
    while frontier:
        nxt = []
        for D in frontier:
            for op in ops:
                if op not in D and preds[op] <= D:
                    D2 = D | {op}
                    if D2 not in seen:
                        seen.add(D2)
                        nxt.append(D2)
        frontier = nxt
    downsets = sorted(seen, key=lambda D: (len(D), tuple(sorted(_rank[o] for o in D))))
    after = {D: [(tuple(sorted(D2 - D, key=_rank.__getitem__)), D2) for D2 in downsets if D < D2]
             for D in downsets}
    return downsets, after, uses, writer_of
'''


def make_downset_kernel():
    tree = ast.parse(CURVE_SOURCE.read_text(), filename=str(CURVE_SOURCE))
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
    projected = next(n for n in ast.walk(outer) if isinstance(n, ast.FunctionDef) and n.name == 'projected')
    projected.body.insert(0, ast.parse('ops = tuple(sorted(ops, key=_rank.__getitem__))').body[0])
    position = next(i for i, n in enumerate(outer.body) if isinstance(n, ast.FunctionDef) and n.name == 'cut_dp')
    outer.body[position:position + 1] = ast.parse(DOWNSET_DP).body
    outer.body[1:1] = ast.parse('''
_rank = {op: i for i, op in enumerate(graph.ops)}
if len({graph.output(op) for op in graph.ops}) != len(graph.ops):
    raise ValueError('downset recursion requires single-writer graphs')
if canonical_spans or canonical_remainders or independent_ops or partitions != 'dp':
    raise ValueError('downset recursion requires the plain cut-DP configuration')
''').body
    namespace = dict(__name__='research.index_coupling.graph._downset_experiment',
                     __package__='research.index_coupling.graph')
    exec(compile(ast.fix_missing_locations(tree), str(CURVE_SOURCE), 'exec'), namespace)
    return namespace['curve']


def normalize(graph, witness, scalar_leaf='v2'):
    """(executed global order, witness rewritten into that order)."""
    spec = Specification(graph)
    position, out = 0, []

    def take():
        nonlocal position
        require(position < len(witness), 'truncated flat witness')
        record = witness[position]
        position += 1
        return record

    def parse(ops, bounds, external, mode):
        local = spec.tensors(ops) - external
        if all(len(bounds[v]) == 1 for t in local for v in spec.dims[t]):
            if scalar_leaf == 'v1' or len(ops) == 1:
                return tuple(ops)
            if witness[position][0] == 'hold':
                record = take()
                require(set(record[1]) == set(ops), 'bad hold record')
                out.append(('hold', tuple(ops)))
                return tuple(ops)
            mode = 'groups'
        slot = len(out)
        out.append(None)
        record = take()
        if mode == 'groups':
            require(record[0] == 'groups', f'expected groups, got {record}')
            groups, kept = record[1], record[3]
            require(sorted(op for g in groups for op in g) == sorted(ops), 'bad partition')
            sequences = tuple(parse(tuple(g), bounds, external | set(kept), 'loop') for g in groups)
            out[slot] = ('groups', sequences) + tuple(record[2:])
            return tuple(op for s in sequences for op in s)
        require(record[0] == 'loop' and set(record[1]) == set(ops), f'expected loop, got {record}')
        variable, tile = record[2], int(record[3].split()[1])
        inner = dict(bounds, **{variable: range(tile)})
        sequence = parse(ops, inner, external | set(record[5]), 'groups')
        out[slot] = (record[0], sequence) + tuple(record[2:])
        return sequence

    order = parse(tuple(spec.ops), spec.bounds, set(), 'groups')
    require(position == len(witness), 'unused flat witness records')
    return order, tuple(out)
