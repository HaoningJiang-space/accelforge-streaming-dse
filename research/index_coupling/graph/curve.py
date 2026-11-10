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
from math import floor, isqrt, log, prod
from time import perf_counter
from .span_names import SpanNames


_CAT = object()  # witness concatenation node; flattened once at the end
_RENAME = object()  # lazy representative-to-caller witness renaming


def cat(a, b):
    return b if not a else a if not b else (_CAT, a, b)


def flatten(witness):
    out, stack = [], [(witness, None)]
    while stack:
        w, names = stack.pop()
        if w and w[0] is _CAT:
            stack.extend(((w[2], names), (w[1], names)))
        elif w and w[0] is _RENAME:
            maps = w[2] if names is None else tuple(
                {k: outer.get(v, v) for k, v in inner.items()}
                for inner, outer in zip(w[2], names))
            stack.append((w[1], maps))
        elif names is not None:
            op, tensor = names
            for note in w:
                if note[0] == 'groups':
                    out.append(('groups', tuple(tuple(op[x] for x in g) for g in note[1]),
                                'kept', tuple(sorted(tensor[t] for t in note[3])),
                                'via DRAM', tuple(sorted(tensor[t] for t in note[5]))))
                else:
                    assert note[0] == 'loop'
                    out.append(('loop', tuple(op[x] for x in note[1]), note[2], note[3],
                                'kept', tuple(sorted(tensor[t] for t in note[5])),
                                'refetched', tuple(sorted(tensor[t] for t in note[7]))))
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


def merge_staircases(a, b, max_capacity=float('inf')):
    """Linear sweep of two exact frontiers; retain separate witness references."""
    i = j = 0
    left = right = None
    while i < len(a) or j < len(b):
        c = min(a[i][0] if i < len(a) else float('inf'),
                b[j][0] if j < len(b) else float('inf'))
        if c > max_capacity:
            break
        if i < len(a) and a[i][0] == c:
            left = a[i]
            i += 1
        if j < len(b) and b[j][0] == c:
            right = b[j]
            j += 1
        if left is not None and right is not None:
            yield c, left[1] + right[1], left[2], right[2]


def combine_max_sum(a, b, max_capacity=float('inf'), grid=None):
    # a, b are Pareto staircases (capacity ascending, traffic descending). The best
    # pair within capacity c is the staircase value of each at c, so one sweep over
    # the union of capacities replaces the |a|·|b| cross product.
    out = []
    for c, q, wa, wb in merge_staircases(a, b, max_capacity):
        if grid and out and bucket(out[-1][0], grid) == bucket(c, grid):
            out.pop()
        out.append((c, q, cat(wa, wb)))
    return tuple(out)


@lru_cache(maxsize=None)
def tile_sizes(extent, domain='halving'):
    """Proper divisible tiles; the default preserves the historical order."""
    if domain == 'divisors':
        values = set()
        for d in range(1, isqrt(extent) + 1):
            if extent % d == 0:
                values.update((d, extent // d))
        return tuple(sorted(values - {extent}, reverse=True))
    if domain != 'halving':
        raise ValueError("tile_domain must be 'halving' or 'divisors'")
    values = []
    b = extent // 2
    while b >= 1:
        if extent % b == 0:
            values.append(b)
        b //= 2
    return tuple(values)


def curve(graph, witness=False, max_capacity=float('inf'), grid=None, write_through=True,
          written=frozenset(), split_shared=True, spill_cost=2, *,
          external=frozenset(), entry='solve', root_groups=None, root_kept=None,
          whole_span_cuts=None, legacy_nested_writes=False, partitions='enumerate',
          ownership_projection=True, stats=None, canonical_spans=False, independent_ops=False,
          tile_domain='halving'):
    """Exact frontiers when grid=None; optional per-call performance ledger.

    stats is populated even if search raises (e.g. a caller's timeout). Timed
    Pareto/merge sections exclude recursive search; counters describe work, not
    unique executable schedules. ownership_projection=False retains the older
    owned-key projection for controlled comparisons.
    tile_domain='divisors' admits every proper divisor at every recursive
    extent. The default 'halving' retains the original integer-halving sequence
    filtered by divisibility, including its omissions on non-power-of-two sizes.
    """
    if tile_domain not in ('halving', 'divisors'):
        raise ValueError("tile_domain must be 'halving' or 'divisors'")
    started = perf_counter()
    span_names = SpanNames(graph) if canonical_spans else None
    prune, merge, join, sweep = pareto, combine_max_sum, cat, merge_staircases
    if stats is not None:
        stats.clear()
        stats.update({k: 0 for k in ('pareto_calls', 'pareto_candidates', 'pareto_points',
                                    'max_frontier', 'merge_calls', 'merge_inputs', 'merge_points',
                                    'partition_masks', 'partition_choices', 'loop_choices',
                                    'dp_states', 'dp_transitions', 'max_crossing',
                                    'dp_multiwriter_fallbacks', 'witness_nodes')})
        stats.update(pareto_seconds=0., merge_seconds=0.)
        stats.update(cache_misses_by_span={}, cache_misses_by_extents={},
                     cache_misses_by_residency={}, renamed_calls=0, rename_nodes=0,
                     independent_splits=0)

        def prune(points, max_capacity=float('inf'), grid=None):
            # Materialize before timing: generators can contain recursive work.
            points = tuple(points)
            begin = perf_counter()
            out = pareto(points, max_capacity, grid)
            stats['pareto_seconds'] += perf_counter() - begin
            stats['pareto_calls'] += 1
            stats['pareto_candidates'] += len(points)
            stats['pareto_points'] += len(out)
            stats['max_frontier'] = max(stats['max_frontier'], len(out))
            return out

        def merge(a, b, max_capacity=float('inf'), grid=None):
            begin = perf_counter()
            out = combine_max_sum(a, b, max_capacity, grid)
            stats['merge_seconds'] += perf_counter() - begin
            stats['merge_calls'] += 1
            stats['merge_inputs'] += len(a) + len(b)
            stats['merge_points'] += len(out)
            stats['witness_nodes'] += sum(bool(wa and wb) for _, _, wa, wb in
                                          merge_staircases(a, b, max_capacity)) if witness else 0
            return out

        def join(a, b):
            stats['witness_nodes'] += bool(a and b)
            return cat(a, b)

        def sweep(a, b, max_capacity=float('inf')):
            begin = perf_counter()
            out = tuple(merge_staircases(a, b, max_capacity))
            stats['merge_seconds'] += perf_counter() - begin
            stats['merge_calls'] += 1
            stats['merge_inputs'] += len(a) + len(b)
            stats['merge_points'] += len(out)
            return out
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
    if partitions == 'dp' and grid is not None:
        raise ValueError('cut DP currently requires exact frontiers (grid=None)')
    if canonical_spans and grid is not None:
        raise ValueError('span canonicalization currently requires exact frontiers (grid=None)')
    if independent_ops and grid is not None:
        raise ValueError('independent operator splitting requires exact frontiers (grid=None)')
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
    axes = {t: tuple(names.index(v) for v in dims) for t, dims in dims_of.items()}
    n_consumers = {t: len(graph.consumers(t)) for t in dims_of}

    def size(t, ext):
        return prod(ext[i] for i in axes[t])

    @lru_cache(maxsize=None)
    def project(ops):
        tensors = frozenset(graph.tensors(ops))
        used = graph.rank_vars(ops)
        made = frozenset(output_of(op) for op in ops)
        return tensors, tuple(i for i, v in enumerate(names) if v not in used), made

    def projected(ops, ext, external, owned):
        # A subproblem's curve depends only on the tensors its ops access and the
        # extents they use; ancestors' kept tensors are charged by the caller, as
        # are final writes an ancestor owns. Projecting the cache key is exact and
        # removes duplicate subproblems.
        tensors, unused, made = project(ops)
        ext = list(ext)
        for i in unused:
            ext[i] = 1
        # owned is consulted only for a write performed inside this span. A
        # consumer-only span cannot observe whether an ancestor owns that write.
        return ops, tuple(ext), external & tensors, owned & (made if ownership_projection else tensors)

    @lru_cache(maxsize=None)
    def loop_metadata(ops):
        common = set.intersection(*(graph.rank_vars((op,)) for op in ops))
        inside_made = project(ops)[2] & {t for op in ops for t in list(graph.access[op])[:-1]}
        return common, inside_made

    @lru_cache(maxsize=None)
    def shared_tensors(ops):
        seen, shared = set(), set()
        for op in ops:
            tensors = project((op,))[0]
            shared.update(seen & tensors)
            seen.update(tensors)
        return frozenset(shared)

    @lru_cache(maxsize=None)
    def cut_metadata(ops):
        # Incidence is independent of extents, external reservations and owned
        # writes. Rebuilding it at every recursive state costs millions of scans.
        use = tuple(project((op,))[0] for op in ops)
        tensors = project(ops)[0]
        first = {t: min(i for i, ts in enumerate(use) if t in ts) for t in tensors}
        last = {t: max(i for i, ts in enumerate(use) if t in ts) for t in tensors}
        writer = {t: next((i for i, op in enumerate(ops) if output_of(op) == t), None) for t in tensors}
        crossing = tuple(tuple(sorted(t for t in tensors if first[t] < p <= last[t]))
                         for p in range(len(ops) + 1))
        touched, readers = {}, {}
        for p in range(len(ops)):
            for q in range(p + 1, len(ops) + 1):
                touched[p, q] = project(ops[p:q])[0]
                readers[p, q] = frozenset(t for op in ops[p:q] for t in graph.access[op]
                                          if t != output_of(op))
        return first, writer, crossing, touched, readers

    def solve(ops, ext, external, owned, constrained=False):
        state = projected(ops, ext, external, owned)
        if span_names is None or constrained:
            return _solve(*state, constrained)
        state, restore = span_names.state(*state)
        return restore_names(_solve(*state, constrained), restore)

    def group_curve(group, ext, external, owned):
        state = projected(group, ext, external, owned)
        if span_names is None:
            return _group_curve(*state)
        state, restore = span_names.state(*state)
        return restore_names(_group_curve(*state), restore)

    def restore_names(points, restore):
        if restore is None:
            return points
        if stats is not None:
            stats['renamed_calls'] += 1
            stats['rename_nodes'] += sum(bool(w) for _, _, w in points) if witness else 0
        return tuple((c, q, (_RENAME, w, restore) if w else ()) for c, q, w in points) if witness else points

    def record_miss(stage, ops, ext, external, owned):
        # Marginals avoid storing another full set of exponential cache keys.
        for field, key in (
                ('cache_misses_by_span', f'{stage}:{",".join(ops)}'),
                ('cache_misses_by_extents', f'{stage}:{ext}'),
                ('cache_misses_by_residency',
                 f'{stage}:n={len(ops)},external={len(external)},local_outputs={len(external & project(ops)[2])},owned={len(owned)}')):
            hist = stats[field]
            hist[key] = hist.get(key, 0) + 1

    @lru_cache(maxsize=None)
    def _solve(ops, ext, external, owned, constrained=False):
        if stats is not None:
            record_miss('solve', ops, ext, external, owned)
        live = project(ops)[0] - external
        if not constrained and all(size(t, ext) == 1 for t in live):
            return ((len(live), 0, ()),)
        if (independent_ops and len(ops) > 1 and not constrained
                and not (allowed_mask is not None and ops == graph.ops)
                and shared_tensors(ops) <= external):
            # Only tensors already reserved by the caller connect these ops.
            # Projecting any fused plan onto each op preserves its traffic and
            # cannot increase peak storage. Singleton groups realize that bound.
            if stats is not None:
                stats['independent_splits'] += 1
            groups = tuple((op,) for op in ops)
            note = (('groups', groups, 'kept', (), 'via DRAM', ()),) if witness else ()
            level = ((0, 0, note),)
            for group in groups:
                level = merge(level, group_curve(group, ext, external, owned), max_capacity)
                if not level:
                    break
            return level
        if partitions == 'dp' and not constrained:
            if len(project(ops)[2]) == len(ops):
                return cut_dp(ops, ext, external, owned)
            # The DP's single-writer transition does not price repeated output
            # accumulations. Preserve the enumeration grammar for such spans.
            if stats is not None:
                stats['dp_multiwriter_fallbacks'] += 1
        results = []
        n = len(ops)
        masks = (0,) if constrained else range(1 << (n - 1))
        for mask in masks:
            if allowed_mask is not None and ops == graph.ops and mask & ~allowed_mask:
                continue
            if stats is not None:
                stats['partition_masks'] += 1
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
                for t in project(group)[0] - external:
                    users.setdefault(t, []).append(g)
            shared = sorted(t for t, gs in users.items() if len(gs) > 1)
            for keep_bits in product((True, False), repeat=len(shared)):
                if stats is not None:
                    stats['partition_choices'] += 1
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
                    level = merge(level, prune(((across + c, t, w) for c, t, w in inner), max_capacity), max_capacity, grid)
                    if not level:
                        break
                results.extend(level)
        return prune(results, max_capacity, grid)

    def cut_dp(ops, ext, external, owned):
        # Same partitions, costs and witnesses as the enumeration in _solve, built
        # left to right over cut positions. A tensor crosses cut p when ops on both
        # sides use it; at a chosen cut that means it is shared by two groups.
        # The state at p is the keep/DRAM choice of each crossing tensor: every
        # later cost depends on the prefix only through it, and capacity (max)
        # and traffic (sum) are monotone, so Pareto-pruning each state is exact.
        n = len(ops)
        first, writer, all_crossing, touched, readers = cut_metadata(ops)
        crossing = [tuple(t for t in ts if t not in external) for ts in all_crossing]
        allowed = [p == 0 or p == n or allowed_mask is None or ops != graph.ops or allowed_mask >> (p - 1) & 1
                   for p in range(n + 1)]
        if stats is not None:
            stats['max_crossing'] = max(stats['max_crossing'], max(map(len, crossing)))
        states = [dict() for _ in range(n + 1)]
        # Witness while building: (groups, decisions, concatenated group witnesses).
        states[0][()] = ((0, 0, ((), frozenset(), ()) if witness else ()),)
        for p in range(n):
            for bits_p, prefix in states[p].items():
                if stats is not None:
                    stats['dp_states'] += 1
                decided = dict(zip(crossing[p], bits_p))
                for q in range(p + 1, n + 1):
                    if not allowed[q]:
                        continue
                    new = [t for t in crossing[q] if t not in decided]
                    group = ops[p:q]
                    for new_bits in product((True, False), repeat=len(new)):
                        if stats is not None:
                            stats['dp_transitions'] += 1
                        choice = dict(decided, **dict(zip(new, new_bits)))
                        if not split_shared and any(not choice[t] and t in produced and n_consumers[t] > 1
                                                    for t in new):
                            continue
                        dropped = {t for t, k in choice.items() if not k and t in touched[p, q]}
                        if not write_through and any(
                                writer[t] is not None and p <= writer[t] < q and
                                t in readers[p, q]
                                for t in dropped):
                            continue
                        kept = frozenset(t for t, k in choice.items() if k)
                        across = sum(size(t, ext) for t in kept)
                        extra = 0
                        for t in dropped:
                            if writer[t] is not None and t in consumed:
                                extra += size(t, ext) * ((t not in owned) if p <= writer[t] < q else 1)
                            elif writer[t] is None and first[t] < p:
                                extra += size(t, ext)
                        written_here = frozenset(t for t, k in choice.items()
                                                 if not k and writer[t] is not None and t in consumed)
                        child_owned = owned if legacy_nested_writes else owned | written_here
                        inner = prune(((across + c, t, w) for c, t, w in
                                        group_curve(group, ext, external | kept, child_owned)), max_capacity)
                        bits_q = tuple(choice[t] for t in crossing[q])
                        decisions = frozenset(choice.items())
                        merged = [(c, t + extra, w if not witness else
                                   (w[0] + (group,), w[1] | decisions, join(w[2], wg)))
                                  for c, t, w, wg in sweep(prefix, inner, max_capacity)]
                        if merged:
                            states[q][bits_q] = prune(list(states[q].get(bits_q, ())) + merged, max_capacity)
        results = []
        for c, t, w in states[n].get((), ()):
            if witness:
                groups, decisions, inner = w
                note = ('groups', groups, 'kept', tuple(sorted(x for x, k in decisions if k)),
                        'via DRAM', tuple(sorted(x for x, k in decisions if not k)))
                w = join((note,), inner)
            results.append((c, t, w))
        return prune(results, max_capacity, grid)

    @lru_cache(maxsize=None)
    def _group_curve(group, ext, external, owned):
        if stats is not None:
            record_miss('group', group, ext, external, owned)
        live = project(group)[0] - external
        if all(size(t, ext) == 1 for t in live):
            return ((len(live), 0, ()),)
        common, inside_made = loop_metadata(group)
        results = []
        for v in common:
            i = names.index(v)
            extent = ext[i]
            if extent == 1 or any(v not in dims_of[t] for t in inside_made - external):
                continue
            lacking = sorted(t for t in live if v not in dims_of[t])
            for b in tile_sizes(extent, tile_domain):
                    trips = extent // b
                    inner_ext = ext[:i] + (b,) + ext[i + 1:]
                    for keep_bits in product((True, False), repeat=len(lacking)):
                        if stats is not None:
                            stats['loop_choices'] += 1
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
                        results.extend((cap + c, extra + trips * t, join(note, w)) for c, t, w in inner)
        return prune(results, max_capacity, grid)

    ext0 = tuple(graph.sizes[v] for v in names)
    inputs = consumed - produced
    outputs = produced - consumed
    compulsory = sum(size(t, ext0) for t in (inputs | outputs) - external)
    written = frozenset(written)
    try:
        points = (group_curve(graph.ops, ext0, external, written) if entry == 'group' else
                  solve(graph.ops, ext0, external, written, root_groups is not None))
        return tuple((c, compulsory + t) + ((flatten(w),) if witness else ()) for c, t, w in points)
    finally:
        if stats is not None:
            stats['solve_cache'] = _solve.cache_info()._asdict()
            stats['group_cache'] = _group_curve.cache_info()._asdict()
            stats['cut_metadata_cache'] = cut_metadata.cache_info()._asdict()
            stats['span_classes'] = len(span_names.representatives) if span_names is not None else None
            stats['seconds'] = perf_counter() - started
