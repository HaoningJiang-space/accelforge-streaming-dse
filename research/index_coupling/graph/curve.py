"""Capacity-traffic Pareto curve from loop nests, without FFM search.

Extends plateau.py. Instead of forcing zero extra traffic, a tensor may
be left out of the buffer and pay DRAM traffic:
- In a group looping over v with tile b (T = extent/b trips), a tensor lacking v
  is either kept whole (capacity) or refetched every trip: an input pays
  (T-1)·size extra reads; an accumulated output pays 2·(T-1)·size (partial sums
  written and read back). An intermediate produced and consumed inside the same
  group must not lack v (its consumer would read partial sums), so v is illegal.
- A tensor used by several sibling groups is either kept across them or goes
  through DRAM: an intermediate is written once and read by each consuming group;
  a graph input is read once per group.
- Loops may be split by powers of two; inner levels see the tile extent.
- written: intermediates whose single DRAM write the caller charges; passing
  them via DRAM then costs only the reads. A partition that sends an intermediate
  through DRAM owns its one final write and passes it down as written, so nested
  partitions dropping the same tensor charge only reads (legacy_nested_writes=True
  restores the earlier double charge, for reproducing archived results).
- spill_cost: DRAM transfers per element for a partial sum spilled between trips
  (2 = write and read back; 1 models accumulate-in-place at DRAM).
- split_shared=False forbids a multi-consumer intermediate from going via DRAM.
- write_through=False forbids an intermediate from both feeding a consumer in its
  producer's group on chip and going to DRAM for another group.
Compulsory traffic (graph inputs read once, graph outputs written once) is added
at the top. Every einsum in a group must iterate the group's loop (no recompute).
The result is a Pareto set over this restricted model, not a lower bound.
"""
from functools import lru_cache
from itertools import product
from math import floor, log, prod


_CAT = object()  # witness concatenation node; flattened once at the end


def cat(a, b):
    return b if not a else a if not b else (_CAT, a, b)


def flatten(witness):
    out, stack = [], [witness]
    while stack:
        w = stack.pop()
        if w and w[0] is _CAT:
            stack.extend((w[2], w[1]))
        else:
            out.extend(w)
    return tuple(out)


def pareto(points, max_capacity=float('inf'), grid=None):
    # points: (capacity, traffic, witness); keep the first witness per Pareto point.
    # With grid g > 1, only the lowest-traffic point per capacity bucket [g^k, g^(k+1))
    # is kept: every dropped point has a kept one with traffic no higher and capacity
    # less than g times larger. Kept points stay exact and executable.
    out, best = [], float('inf')
    for point in sorted(points, key=lambda p: (p[0], p[1])):
        if point[0] > max_capacity:
            break
        if point[1] < best:
            if grid and out and bucket(out[-1][0], grid) == bucket(point[0], grid):
                out.pop()
            out.append(point)
            best = point[1]
    return tuple(out)


def bucket(capacity, grid):
    return floor(log(capacity, grid)) if capacity > 0 else -1


def combine_max_sum(a, b, max_capacity=float('inf'), grid=None):
    # a, b are Pareto staircases (capacity ascending, traffic descending). The best
    # pair within capacity c is the staircase value of each at c, so one sweep over
    # the union of capacities replaces the |a|·|b| cross product.
    out, i, j = [], -1, -1
    for c in sorted({p[0] for p in a} | {p[0] for p in b}):
        if c > max_capacity:
            break
        while i + 1 < len(a) and a[i + 1][0] <= c:
            i += 1
        while j + 1 < len(b) and b[j + 1][0] <= c:
            j += 1
        if i >= 0 and j >= 0:
            out.append((max(a[i][0], b[j][0]), a[i][1] + b[j][1], cat(a[i][2], b[j][2])))
    return pareto(out, grid=grid)


def curve(graph, witness=False, max_capacity=float('inf'), grid=None, write_through=True,
          written=frozenset(), split_shared=True, spill_cost=2, *,
          external=frozenset(), entry='solve', root_groups=None, root_kept=None,
          whole_span_cuts=None, legacy_nested_writes=False, partitions='enumerate'):
    # Conditional interface: external tensors are resident, and their allocation
    # and compulsory transfers belong to the caller. entry='group' queries the
    # exact child interface used by a sibling partition. Root constraints apply
    # only once; recursive children retain the original grammar.
    external = frozenset(external)
    # P21d: constrain the first nontrivial whole-span partition, including
    # after outer loops. Proper child spans retain the original grammar.
    # None leaves all existing calls unchanged; an empty set forbids splitting
    # this span but still allows whole-span loops and scalar leaves.
    allowed_mask = None
    if whole_span_cuts is not None:
        if entry != 'solve' or root_groups is not None:
            raise ValueError('whole_span_cuts requires solve entry and no fixed root_groups')
        whole_span_cuts = frozenset(whole_span_cuts)
        if any(not isinstance(k, int) or not 1 <= k < len(graph.ops) for k in whole_span_cuts):
            raise ValueError('cut positions must be internal integer boundaries')
        allowed_mask = sum(1 << (k-1) for k in whole_span_cuts)
    if entry not in ('solve', 'group'):
        raise ValueError("entry must be 'solve' or 'group'")
    if partitions not in ('enumerate', 'dp'):
        raise ValueError("partitions must be 'enumerate' or 'dp'")
    if root_groups is not None:
        root_groups = tuple(tuple(g) for g in root_groups)
        if (entry != 'solve' or any(not g for g in root_groups)
                or tuple(op for g in root_groups for op in g) != graph.ops):
            raise ValueError('root_groups must partition the ordered graph at solve entry')
        shared = {t for t in graph.tensors(graph.ops) - external
                  if sum(t in graph.tensors(g) for g in root_groups) > 1}
        if root_kept is not None and not set(root_kept) <= shared:
            raise ValueError('root_kept contains a tensor not shared at the root')
    elif root_kept is not None:
        raise ValueError('root_kept requires root_groups')
    root_kept = None if root_kept is None else frozenset(root_kept)
    # Points above max_capacity are dropped in every subproblem: capacities only grow
    # when subresults are combined, so the curve up to max_capacity is unchanged.
    dims_of = {}
    for op in graph.ops:
        for t, d in graph.access[op].items():
            dims_of.setdefault(t, d)
    produced, consumed = graph.produced(), graph.consumed()
    output_of = graph.output
    names = sorted(graph.sizes)
    n_consumers = {t: len(graph.consumers(t)) for t in dims_of}

    def size(t, ext):
        return prod(ext[names.index(v)] for v in dims_of[t])

    @lru_cache(maxsize=None)
    def project(ops):
        tensors = frozenset(graph.tensors(ops))
        used = graph.rank_vars(ops)
        return tensors, tuple(i for i, v in enumerate(names) if v not in used)

    def projected(ops, ext, external, owned):
        # A subproblem's curve depends only on the tensors its ops access and the
        # extents they use; ancestors' kept tensors are charged by the caller, as
        # are final writes an ancestor owns. Projecting the cache key is exact and
        # removes duplicate subproblems.
        tensors, unused = project(ops)
        ext = list(ext)
        for i in unused:
            ext[i] = 1
        return ops, tuple(ext), external & tensors, owned & tensors

    def solve(ops, ext, external, owned, constrained=False):
        return _solve(*projected(ops, ext, external, owned), constrained)

    def group_curve(group, ext, external, owned):
        return _group_curve(*projected(group, ext, external, owned))

    @lru_cache(maxsize=None)
    def _solve(ops, ext, external, owned, constrained=False):
        live = graph.tensors(ops) - external
        if not constrained and all(size(t, ext) == 1 for t in live):
            return ((len(live), 0, ()),)
        if partitions == 'dp' and not constrained:
            return cut_dp(ops, ext, external, owned)
        results = []
        n = len(ops)
        masks = (0,) if constrained else range(1 << (n - 1))
        for mask in masks:
            if allowed_mask is not None and ops == graph.ops and mask & ~allowed_mask:
                continue
            groups, start = [], 0
            for i in range(n - 1):
                if mask >> i & 1:
                    groups.append(ops[start:i + 1])
                    start = i + 1
            groups.append(ops[start:])
            if constrained:
                groups = root_groups
            users = {}
            for g, group in enumerate(groups):
                for t in graph.tensors(group) - external:
                    users.setdefault(t, []).append(g)
            shared = sorted(t for t, gs in users.items() if len(gs) > 1)
            for keep_bits in product((True, False), repeat=len(shared)):
                kept = {t for t, k in zip(shared, keep_bits) if k}
                if constrained and root_kept is not None and kept != root_kept:
                    continue
                if not split_shared and any(not k and t in produced and n_consumers[t] > 1
                                            for t, k in zip(shared, keep_bits)):
                    # A multi-consumer intermediate either stays on chip for all its
                    # consumers or is fully materialized by rewriting (ffm_like.py).
                    continue
                if not write_through and any(
                        not k and any(output_of(op) == t for op in groups[g]) and
                        any(t in graph.access[op] and output_of(op) != t for op in groups[g])
                        for t, k in zip(shared, keep_bits) for g in users[t]):
                    # Write-through: t feeds a consumer in its producer's group on chip
                    # and also goes to DRAM for another group. FFM shares a tensor
                    # between einsums through one backing reservation only.
                    continue
                extra = 0
                for t, k in zip(shared, keep_bits):
                    if k:
                        continue
                    gs = users[t]
                    writers = [g for g in gs if any(output_of(op) == t for op in groups[g])]
                    if writers and t in consumed:
                        # The write is skipped for tensors whose one DRAM write the
                        # caller charges separately (chain_view.py).
                        extra += size(t, ext) * ((t not in owned) + len(gs) - len(writers))
                    elif writers:
                        extra += 2 * size(t, ext) * (len(writers) - 1)
                    else:
                        extra += size(t, ext) * (len(gs) - 1)
                dropped = tuple(t for t, k in zip(shared, keep_bits) if not k)
                child_owned = owned if legacy_nested_writes else owned | {
                    t for t in dropped if t in consumed and any(output_of(op) == t for g in users[t] for op in groups[g])}
                level = ((0, extra, (('groups', tuple(groups), 'kept', tuple(sorted(kept)), 'via DRAM', dropped),)
                          if witness else ()),)
                for g, group in enumerate(groups):
                    across = sum(size(t, ext) for t in kept if min(users[t]) <= g <= max(users[t]))
                    inner = group_curve(group, ext, external | frozenset(kept), child_owned)
                    level = combine_max_sum(level, pareto(((across + c, t, w) for c, t, w in inner), max_capacity), max_capacity, grid)
                    if not level:
                        break
                results.extend(level)
        return pareto(results, max_capacity, grid)

    def cut_dp(ops, ext, external, owned):
        # Same partitions, costs and witnesses as the enumeration in _solve, built
        # left to right over cut positions. A tensor crosses cut p when ops on both
        # sides use it; at a chosen cut that means it is shared by two groups.
        # The state at p is the keep/DRAM choice of each crossing tensor: every
        # later cost depends on the prefix only through it, and capacity (max)
        # and traffic (sum) are monotone, so Pareto-pruning each state is exact.
        live = graph.tensors(ops) - external
        n = len(ops)
        use = [graph.tensors((op,)) & live for op in ops]
        first = {t: min(i for i in range(n) if t in use[i]) for t in live}
        last = {t: max(i for i in range(n) if t in use[i]) for t in live}
        writer = {t: next((i for i, op in enumerate(ops) if output_of(op) == t), None) for t in live}
        crossing = [tuple(sorted(t for t in live if first[t] < p <= last[t])) for p in range(n + 1)]
        allowed = [p == n or allowed_mask is None or ops != graph.ops or allowed_mask >> (p - 1) & 1
                   for p in range(n + 1)]
        states = [dict() for _ in range(n + 1)]
        # Witness while building: (groups, decisions, concatenated group witnesses).
        states[0][()] = ((0, 0, ((), frozenset(), ()) if witness else ()),)
        for p in range(n):
            for bits_p, prefix in states[p].items():
                decided = dict(zip(crossing[p], bits_p))
                for q in range(p + 1, n + 1):
                    if not allowed[q]:
                        continue
                    new = [t for t in crossing[q] if t not in decided]
                    group = ops[p:q]
                    touched = set().union(*use[p:q])
                    for new_bits in product((True, False), repeat=len(new)):
                        choice = dict(decided, **dict(zip(new, new_bits)))
                        if not split_shared and any(not choice[t] and t in produced and n_consumers[t] > 1
                                                    for t in new):
                            continue
                        dropped = {t for t in touched if t in choice and not choice[t]}
                        if not write_through and any(
                                writer[t] is not None and p <= writer[t] < q and
                                any(t in graph.access[op] and output_of(op) != t for op in group)
                                for t in dropped):
                            continue
                        kept = frozenset(t for t, k in choice.items() if k)
                        across = sum(size(t, ext) for t in set(crossing[p]) | set(crossing[q]) if choice[t])
                        extra = 0
                        for t in dropped:
                            if writer[t] is not None and t in consumed:
                                extra += size(t, ext) * ((t not in owned) if p <= writer[t] < q else 1)
                            elif writer[t] is None and first[t] < p:
                                extra += size(t, ext)
                        written_here = frozenset(t for t, k in choice.items()
                                                 if not k and writer[t] is not None and t in consumed)
                        child_owned = owned if legacy_nested_writes else owned | written_here
                        inner = pareto(((across + c, t, w) for c, t, w in
                                        group_curve(group, ext, external | kept, child_owned)), max_capacity)
                        bits_q = tuple(choice[t] for t in crossing[q])
                        decisions = frozenset(choice.items())
                        merged = [(c, t + extra, w if not witness else
                                   (w[0] + (group,), w[1] | decisions, cat(w[2], wg)))
                                  for c, t, w, wg in merge_staircases(prefix, inner)]
                        if merged:
                            states[q][bits_q] = pareto(list(states[q].get(bits_q, ())) + merged, max_capacity)
        results = []
        for c, t, w in states[n].get((), ()):
            if witness:
                groups, decisions, inner = w
                note = ('groups', groups, 'kept', tuple(sorted(x for x, k in decisions if k)),
                        'via DRAM', tuple(sorted(x for x, k in decisions if not k)))
                w = cat((note,), inner)
            results.append((c, t, w))
        return pareto(results, max_capacity, grid)

    def merge_staircases(a, b):
        # combine_max_sum keeping both witnesses separate for the caller.
        out, i, j = [], -1, -1
        for c in sorted({p[0] for p in a} | {p[0] for p in b}):
            if c > max_capacity:
                break
            while i + 1 < len(a) and a[i + 1][0] <= c:
                i += 1
            while j + 1 < len(b) and b[j + 1][0] <= c:
                j += 1
            if i >= 0 and j >= 0:
                out.append((max(a[i][0], b[j][0]), a[i][1] + b[j][1], a[i][2], b[j][2]))
        best, kept = float('inf'), []
        for point in sorted(out, key=lambda p: (p[0], p[1])):
            if point[1] < best:
                kept.append(point)
                best = point[1]
        return kept

    @lru_cache(maxsize=None)
    def _group_curve(group, ext, external, owned):
        live = graph.tensors(group) - external
        if all(size(t, ext) == 1 for t in live):
            return ((len(live), 0, ()),)
        common = set.intersection(*(graph.rank_vars((op,)) for op in group))
        inside_made = {output_of(op) for op in group} & {t for op in group for t in list(graph.access[op])[:-1]}
        results = []
        for v in common:
            i = names.index(v)
            extent = ext[i]
            if extent == 1 or any(v not in dims_of[t] for t in inside_made - external):
                continue
            lacking = sorted(t for t in live if v not in dims_of[t])
            b = extent // 2
            while b >= 1:
                if extent % b == 0:
                    trips = extent // b
                    inner_ext = ext[:i] + (b,) + ext[i + 1:]
                    for keep_bits in product((True, False), repeat=len(lacking)):
                        kept = frozenset(t for t, k in zip(lacking, keep_bits) if k)
                        cap = sum(size(t, ext) for t in kept)
                        extra = 0
                        for t, k in zip(lacking, keep_bits):
                            if not k:
                                accumulated = any(output_of(op) == t for op in group)
                                extra += (spill_cost if accumulated else 1) * (trips - 1) * size(t, ext)
                        inner = solve(group, inner_ext, external | kept, owned)
                        note = () if not witness else (('loop', group, v, f'tile {b} x{trips}', 'kept', tuple(sorted(kept)),
                                 'refetched', tuple(t for t, k in zip(lacking, keep_bits) if not k)),)
                        results.extend((cap + c, extra + trips * t, cat(note, w)) for c, t, w in inner)
                b //= 2
        return pareto(results, max_capacity, grid)

    ext0 = tuple(graph.sizes[v] for v in names)
    inputs = consumed - produced
    outputs = produced - consumed
    compulsory = sum(size(t, ext0) for t in (inputs | outputs) - external)
    written = frozenset(written)
    points = (group_curve(graph.ops, ext0, external, written) if entry == 'group' else
              solve(graph.ops, ext0, external, written, root_groups is not None))
    return tuple((c, compulsory + t) + ((flatten(w),) if witness else ()) for c, t, w in points)
