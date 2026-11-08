"""Exact relaxation that overlaps all group-level resource service."""

from itertools import product

from research.runtime.dag_model import Group, lifetimes, validate_plan
from research.runtime.strip_codesign import COMPUTE, DRAM, GB_READ, GB_WRITE, ceildiv, pareto, representatives, tile_options


def add(left, right):
    return tuple(a+b for a, b in zip(left, right, strict=True))


def boundary(graph, profile):
    fetch = graph.rows * sum(graph.widths[name] for step in profile for name in step.fetch)
    drain = graph.rows * sum(step.op.width for step in profile if step.drain)
    return ((fetch+drain)*DRAM[0]+fetch*GB_WRITE[0]+drain*GB_READ[0],
            (fetch+drain)*DRAM[1], drain*GB_READ[1], fetch*GB_WRITE[1], 0)


def op_service(graph, op, bands, pin, tile):
    p, q = tile
    if op.kind == "gemm":
        k, n = graph.widths[op.inputs[0]], op.width
        kb, nb = ceildiv(k, p), ceildiv(n, q)
        dram = k*n*(1 if pin else bands)
        reads = k*n*bands + graph.rows*(k*nb+n*(kb-1))
        writes = dram + graph.rows*n*kb
        ops = graph.rows*k*n
        cycles = graph.rows*kb*nb
    else:
        dram, ops = 0, graph.rows*op.width
        reads, writes = 2*ops, ops
        cycles = graph.rows*ceildiv(op.width, q)
    return (dram*DRAM[0]+reads*GB_READ[0]+writes*GB_WRITE[0]+ops*COMPUTE[0],
            dram*DRAM[1], reads*GB_READ[1], writes*GB_WRITE[1], cycles*COMPUTE[1])


def group_cost(service):
    return service[0], max(service[1:])


def vector_frontier(entries):
    frontier = []
    for cost, tiles in sorted(entries, key=lambda entry: entry[0]):
        if not any(all(a <= b for a, b in zip(other, cost)) for other, _ in frontier):
            frontier.append((cost, tiles))
    return frontier


def options(graph, hardware, op, room):
    if op.kind != "gemm":
        return ((0, min(op.width, hardware.px*hardware.py)),)
    return tile_options(graph.widths[op.inputs[0]], op.width, hardware.py, hardware.px, room)


def frontier(graph, hardware, order, profile):
    initial = boundary(graph, profile)
    entries = []
    for pins in product(*[(False, True) if step.op.kind == "gemm" else (False,) for step in profile]):
        available = hardware.capacity_bytes - sum(graph.weight_words(step.op)
                                                 for step, pin in zip(profile, pins) if pin)
        largest = min(graph.rows, *((available-int(step.op.kind == "gemm" and not pin))//step.live_width
                                    for step, pin in zip(profile, pins)))
        # All service and energy counts are functions of the number of bands.
        # The smallest band in a class admits all tiles admitted by larger ones.
        for b in representatives(graph.rows, largest):
            bands = ceildiv(graph.rows, b)
            candidates = [(initial, ())]
            for step, pin in zip(profile, pins):
                room = None if pin else available-b*step.live_width
                priced = [(op_service(graph, step.op, bands, pin, tile), tile)
                          for tile in options(graph, hardware, step.op, room)]
                candidates = vector_frontier((add(a, c), tiles+(tile,)) for a, tiles in candidates
                                             for c, tile in priced)
            entries.extend((group_cost(cost), Group(order, b, tiles, pins)) for cost, tiles in candidates)
    return list(pareto(entries))


def score(graph, hardware, plan):
    validate_plan(graph, hardware, plan)
    total = (0, 0)
    for group in plan:
        profile = tuple(lifetimes(graph, group.order))
        cost = boundary(graph, profile)
        bands = ceildiv(graph.rows, group.rows)
        for step, pin, tile in zip(profile, group.pinned, group.tiles, strict=True):
            cost = add(cost, op_service(graph, step.op, bands, pin, tile))
        total = add(total, group_cost(cost))
    return total


def lower_geometry(graph, hardware, profile):
    cost = boundary(graph, profile)
    for step in profile:
        tile, = options(graph, hardware, step.op, None)
        cost = add(cost, op_service(graph, step.op, 1, False, tile))
    energy, ticks = group_cost(cost)
    return energy*ticks
