"""Independent analytical pricing of DAG calendar events."""

from functools import lru_cache

import numpy as np

from research.runtime.dag_model import lifetimes, validate_plan
from research.runtime.strip_codesign import COMPUTE, DRAM, GB_READ, GB_WRITE, add, ceildiv
from research.runtime.strip_native_timing import shape_classes
from research.runtime.strip_overlap_cost import stage


def boundary(graph, profile):
    fetch = graph.rows * sum(graph.widths[name] for step in profile for name in step.fetch)
    drain = graph.rows * sum(step.op.width for step in profile if step.drain)
    energy = (fetch + drain) * DRAM[0] + fetch * GB_WRITE[0] + drain * GB_READ[0]
    return energy, (fetch + drain) * DRAM[1]


def pointwise(rows, n, b, q, room, live_width, overlap="finite"):
    e = rows * n * (2 * GB_READ[0] + GB_WRITE[0] + COMPUTE[0])
    t = rows * (n * (2 * GB_READ[1] + GB_WRITE[1]) + ceildiv(n, q) * COMPUTE[1])
    if overlap == "serial":
        return e, t
    for band, count in shape_classes(rows, b):
        slack = room - band * live_width
        for width, repeats in shape_classes(n, q):
            if overlap == "free_staging" or 3 * width <= slack:
                read, write = 2 * width * GB_READ[1], width * GB_WRITE[1]
                savings = read + write + COMPUTE[1] - max(read, write, COMPUTE[1])
                t -= (band - 1) * count * repeats * savings
    return e, t


@lru_cache(maxsize=2048)
def pointwise_frontier(rows, n, b, lanes, room, live_width, overlap="finite"):
    q = np.arange(1, min(n, lanes)+1, dtype=np.int64)
    e = rows * n * (2 * GB_READ[0] + GB_WRITE[0] + COMPUTE[0])
    t = rows * (n * (2 * GB_READ[1] + GB_WRITE[1]) + (n + q - 1) // q * COMPUTE[1])
    if overlap != "serial":
        for band, count in shape_classes(rows, b):
            slack = room - band * live_width
            for width, repeats in ((q, n // q), (n % q, 1)):
                read, write = 2 * width * GB_READ[1], width * GB_WRITE[1]
                saving = read + write + COMPUTE[1] - np.maximum(COMPUTE[1], np.maximum(read, write))
                fits = overlap == "free_staging" or 3 * width <= slack
                t -= np.where(fits, (band - 1) * count * repeats * saving, 0)
    best = int(np.argmin(t))
    return (((e, int(t[best])), (0, best+1)),)


def score(graph, hardware, plan, overlap="finite"):
    validate_plan(graph, hardware, plan)
    total = (0, 0)
    for group in plan:
        profile = tuple(lifetimes(graph, group.order))
        total = add(total, boundary(graph, profile))
        room = hardware.capacity_bytes - sum(
            graph.weight_words(step.op) for step, pin in zip(profile, group.pinned) if pin
        )
        for step, (p, q), pin in zip(profile, group.tiles, group.pinned):
            op = step.op
            if group.rows * step.live_width + (0 if pin else p * q) > room:
                raise ValueError("SRAM capacity exceeded")
            if op.kind == "gemm":
                cost = stage(graph.rows, graph.widths[op.inputs[0]], op.width, group.rows, p, q,
                             pin, room, step.live_width, overlap)
            else:
                cost = pointwise(graph.rows, op.width, group.rows, q, room, step.live_width, overlap)
            total = add(total, cost)
    return total
