"""Exact batched pricing for the explicit strip port calendar."""

from functools import lru_cache

import numpy as np

from research.runtime.strip_codesign import COMPUTE, DRAM, GB_READ, GB_WRITE, ceildiv, stage_cost
from research.runtime.strip_native_timing import shape_classes
from research.runtime.strip_prefetch_cost import credit


def boundary(rows, k, n):
    energy = rows * ((k + n) * DRAM[0] + k * GB_WRITE[0] + n * GB_READ[0])
    return energy, rows * (k + n) * DRAM[1]


def wave_classes(k, n, p, q):
    """First reduction, repeated full reductions, and a possible tail."""
    for no, nc in ((q, n // q), (n % q, 1)):
        for ki, kc, prior in ((p, 1, 0), (p, k // p - 1, 1), (k % p, 1, 1)):
            reads = (ki + prior * no) * GB_READ[1]
            writes = no * GB_WRITE[1]
            if isinstance(reads, np.ndarray) or isinstance(writes, np.ndarray):
                period = np.maximum(COMPUTE[1], np.maximum(reads, writes))
            else:
                period = max(COMPUTE[1], reads, writes)
            savings = (reads + writes + COMPUTE[1] - period) * nc * kc
            staging = ki + (1 + prior) * no
            yield ki * no, staging, savings


def stage(rows, k, n, b, p, q, pin, room, live_width=None, overlap="finite"):
    """Price valid tiles given remaining segment SRAM after pinned weights."""
    bands = ceildiv(rows, b)
    e, t = stage_cost(rows, k, n, ceildiv(k, p), ceildiv(n, q), bands, pin)
    t -= k * n * (1 if pin else bands) * GB_WRITE[1]
    if overlap == "serial":
        return e, t
    for band, count in shape_classes(rows, b):
        slack = room - band * (k + n if live_width is None else live_width)
        for wave, staging, savings in wave_classes(k, n, p, q):
            if wave and (overlap == "free_staging" or staging + (0 if pin else wave) <= slack):
                t -= (band - 1) * count * savings
        if overlap == "prefetch" and not pin:
            t -= count * int(credit(band, k, n, p, q, slack))
    return e, t


def evaluate_overlap(rows, widths, hardware, plan):
    from research.runtime.strip_codesign import add, evaluate

    serial, peak = evaluate(rows, widths, hardware, plan)
    total = (0, 0)
    for segment in plan:
        total = add(total, boundary(rows, widths[segment.start], widths[segment.stop]))
        resident = sum(widths[i] * widths[i+1]
                       for i, pin in enumerate(segment.pinned, segment.start) if pin)
        for i, ((p, q), pin) in enumerate(zip(segment.tiles, segment.pinned), segment.start):
            total = add(total, stage(rows, widths[i], widths[i+1], segment.rows, p, q,
                                     pin, hardware.capacity_bytes - resident))
    if total[0] != serial[0]:
        raise AssertionError("the overlap schedule changed the energy ledger")
    return total, peak


@lru_cache(maxsize=12)
def tile_grid(k, n, x, y):
    p = np.arange(1, min(k, y) + 1, dtype=np.int64).reshape((-1, 1))
    q = np.arange(1, min(n, x) + 1, dtype=np.int64).reshape((1, -1))
    kb, nb = (k + p - 1) // p, (n + q - 1) // q
    waves = tuple((wave, staging, np.where(wave, savings, 0))
                  for wave, staging, savings in wave_classes(k, n, p, q))
    return p, q, kb, nb, waves


@lru_cache(maxsize=4096)
def stage_frontier(rows, k, n, b, x, y, pin, room, live_width=None, overlap="finite"):
    live_width = k + n if live_width is None else live_width
    p, q, kb, nb, waves = tile_grid(k, n, x, y)
    bands = ceildiv(rows, b)
    energy, time = stage_cost(rows, k, n, kb, nb, bands, pin)
    time = time - k * n * (1 if pin else bands) * GB_WRITE[1]
    if overlap != "serial":
        for band, count in shape_classes(rows, b):
            slack = room - band * live_width
            if band > 1:
                for wave, staging, savings in waves:
                    fits = overlap == "free_staging" or staging + (0 if pin else wave) <= slack
                    time -= np.where(fits, savings, 0) * (band - 1) * count
            if overlap == "prefetch" and not pin:
                time -= count * credit(band, k, n, p, q, slack)

    valid = np.flatnonzero((p * q <= room - b * live_width).ravel()) if not pin else np.arange(time.size)
    energy, time = energy.ravel()[valid], time.ravel()[valid]
    if not valid.size:
        return ()
    order = np.lexsort((time, energy))
    times = time[order]
    best = np.minimum.accumulate(times)
    front = np.concatenate(([True], times[1:] < best[:-1]))
    return tuple(
        ((int(energy[i]), int(time[i])), (int(valid[i] // q.size + 1), int(valid[i] % q.size + 1)))
        for i in order[front]
    )
