"""Replay rectangular transfer events for a concrete strip mapping."""

from collections import Counter
from itertools import product

from research.runtime.strip_codesign import COMPUTE, DRAM, GB_READ, GB_WRITE


def replay(rows, widths, hardware, plan, scalar=False):
    """Check produced regions, read-before-write and live bytes at each wave."""
    def spans(extent, step):
        return tuple(range(i, min(i + step, extent)) for i in range(0, extent, step))

    def size(*axes):
        if scalar:
            return len(set(product(*axes)))
        count = 1
        for axis in axes:
            count *= len(axis)
        return count

    words = Counter()
    cycles = peak = start = 0
    all_rows = range(rows)

    def action(i, level, tensor, direction, *axes):
        words[i, level, tensor, direction] += size(*axes)

    for segment in plan:
        if (segment.start != start or not start < segment.stop < len(widths)
                or not 1 <= segment.rows <= rows
                or len(segment.tiles) != segment.stop - start
                or len(segment.pinned) != segment.stop - start):
            raise ValueError("segment does not continue the GEMM chain")
        held_weights = 0
        for i, pin in enumerate(segment.pinned, start):
            if pin:
                k, n = range(widths[i]), range(widths[i+1])
                action(i, "DRAM", f"W{i}", "read", k, n)
                action(i, "SRAM", f"W{i}", "write", k, n)
                held_weights += size(k, n)
        bands = spans(rows, segment.rows)
        if tuple(r for band in bands for r in band) != tuple(all_rows):
            raise AssertionError("row bands do not partition the input")
        for band in bands:
            live = (f"T{start}", band, range(widths[start]))
            action(start, "DRAM", live[0], "read", band, live[2])
            action(start, "SRAM", live[0], "write", band, live[2])
            for i, ((p, q), pin) in enumerate(zip(segment.tiles, segment.pinned), start):
                k, n = widths[i], widths[i+1]
                x, w, y = f"T{i}", f"W{i}", f"T{i+1}"
                if live != (x, band, range(k)):
                    raise ValueError("producer has not completed consumer input")
                if not 1 <= p <= min(k, hardware.py) or not 1 <= q <= min(n, hardware.px):
                    raise ValueError("wave exceeds physical fanout")
                ready = 0
                for outputs in spans(n, q):
                    if outputs.start != ready:
                        raise AssertionError("output columns overlap or leave a gap")
                    contributions = 0
                    for reduction in spans(k, p):
                        if reduction.start != contributions:
                            raise AssertionError("partial sum has missing or duplicate contributions")
                        wave = size(reduction, outputs)
                        live_bytes = held_weights + size(band, range(k)) + size(band, range(n))
                        live_bytes += 0 if pin else wave
                        peak = max(peak, live_bytes)
                        if peak > hardware.capacity_bytes:
                            raise ValueError("wave exceeds physical SRAM capacity")
                        if not pin:
                            action(i, "DRAM", w, "read", reduction, outputs)
                            action(i, "SRAM", w, "write", reduction, outputs)
                        action(i, "SRAM", w, "read", reduction, outputs)
                        action(i, "RF", w, "write", reduction, outputs)
                        action(i, "RF", w, "read", band, reduction, outputs)
                        action(i, "SRAM", x, "read", band, reduction)
                        if contributions:
                            action(i, "SRAM", y, "read", band, outputs)
                        action(i, "MAC", y, "compute", band, reduction, outputs)
                        action(i, "SRAM", y, "write", band, outputs)
                        contributions = reduction.stop
                        cycles += len(band)
                    if contributions != k:
                        raise AssertionError("output was consumed before the reduction finished")
                    ready = outputs.stop
                if ready != n:
                    raise AssertionError("output coverage is incomplete")
                live = y, band, range(n)
            action(segment.stop-1, "SRAM", live[0], "read", band, live[2])
            action(segment.stop-1, "DRAM", live[0], "write", band, live[2])
        start = segment.stop
    if start != len(widths) - 1:
        raise ValueError("incomplete chain")
    costs = {"DRAM": DRAM, "SRAM": None, "RF": (0, 0), "MAC": COMPUTE}
    energy, ticks = 0, cycles * COMPUTE[1]
    for (_, level, _, direction), count in words.items():
        cost = (GB_READ if direction == "read" else GB_WRITE) if level == "SRAM" else costs[level]
        energy += count * cost[0]
        if level != "MAC":
            ticks += count * cost[1]
    return (energy, ticks), peak, words
