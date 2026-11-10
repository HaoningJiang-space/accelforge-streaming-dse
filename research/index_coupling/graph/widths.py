"""Structural widths, deliberately separate from runtime/complexity claims."""
from math import prod
from .curve import tile_sizes


def widths(graph):
    use = [graph.tensors((op,)) for op in graph.ops]
    tensors = graph.tensors(graph.ops)
    first = {t: min(i for i, ts in enumerate(use) if t in ts) for t in tensors}
    last = {t: max(i for i, ts in enumerate(use) if t in ts) for t in tensors}
    cuts = [sorted(t for t in tensors if first[t] < p <= last[t]) for p in range(1, len(use))]
    root, unconditional, conditional_upper = {}, 0, 0
    upper_example = None
    for p in range(len(use)):
        for q in range(p + 1, len(use) + 1):
            ops = graph.ops[p:q]
            ts = graph.tensors(ops)
            made = {graph.output(op) for op in ops}
            read = {t for op in ops for t in graph.access[op] if t != graph.output(op)}
            inside = made & read
            common = set.intersection(*(graph.rank_vars((op,)) for op in ops))
            for rank in sorted(common):
                if graph.sizes[rank] <= 1:
                    continue
                missing = {t for t in ts if rank not in graph.dims(t)}
                blockers = missing & inside
                # Every blocker must be external to admit this rank. This is
                # an upper bound over possible interfaces, not reachability.
                bound = len(missing - blockers)
                if bound > conditional_upper:
                    conditional_upper = bound
                    upper_example = dict(span=[p, q], rank=rank,
                                         must_be_external=sorted(blockers), obligations=sorted(missing - blockers))
                if not blockers:
                    unconditional = max(unconditional, len(missing))
                    if p == 0 and q == len(use):
                        root[rank] = sorted(missing)

    def extents(n):
        found, pending = {n}, [n]
        while pending:
            for b in tile_sizes(pending.pop()):
                if b not in found:
                    found.add(b)
                    pending.append(b)
        return sorted(found)

    grids = {r: extents(n) for r, n in graph.sizes.items()}
    return dict(n_ops=len(use), n_ranks=len(graph.sizes), w_cut=max(map(len, cuts), default=0),
                cut_tensors=cuts, root_legal_obligations=root,
                w_obl_unconditional_spans=unconditional,
                w_obl_conditional_upper=conditional_upper, conditional_upper_example=upper_example,
                rank_extent_choices=grids, extent_grid_upper=prod(map(len, grids.values())))
