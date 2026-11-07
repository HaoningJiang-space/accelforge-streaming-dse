"""Independently reconstruct AccelForge NVDLA's per-Einsum service envelope."""

from research.runtime.strip_codesign import COMPUTE, DRAM, GB_READ, GB_WRITE


def shape_classes(extent, tile):
    full, tail = divmod(extent, tile)
    return ([(tile, full)] if full else []) + ([(tail, 1)] if tail else [])


def service(rows, k, n, strip, p, q, pin, fetch, drain):
    """Return the native component ticks for one stage of a strip mapping.

    The symbolic reducer repeats a same-shape class and takes the maximum
    across classes for raw latency charges. Initial elisions use the minimum
    nonzero charge. Keeping these separate reproduces the native abstraction.
    """
    bands, reductions, outputs = (shape_classes(extent, tile)
                                  for extent, tile in ((rows, strip), (k, p), (n, q)))
    high_m = max(extent * count for extent, count in bands)
    low_m = min(extent * count for extent, count in bands)
    high_k = max(extent * count for extent, count in reductions)
    high_n = max(extent * count for extent, count in outputs)
    low_n = min(extent * count for extent, count in outputs)
    max_k_repeats = max(count for _, count in reductions)
    max_n_repeats = max(count for _, count in outputs)
    max_band_repeats = max(count for _, count in bands)
    rf_fills = max_band_repeats * high_k * high_n
    weights = k * n if pin else rf_fills

    # Output contributions undergo spatial reduction. The GB owns the
    # running sum. A boundary output also drains GB to the outer holder.
    accumulator = high_m * max_k_repeats * high_n
    skipped_initial = low_m * low_n
    output_writeback = high_m * n if drain else 0
    output_no_initial_fetch = low_m * n if drain else 0
    inputs = high_m * k if fetch else 0
    dram = (weights + inputs + 2 * output_writeback - output_no_initial_fetch) * DRAM[1]
    sram_read = (rf_fills + high_m * high_k * max_n_repeats
                 + accumulator - skipped_initial + output_writeback) * GB_READ[1]
    sram_write = (weights + inputs + accumulator
                  + output_writeback - output_no_initial_fetch) * GB_WRITE[1]
    mac = rows * sum(c for _, c in reductions) * sum(c for _, c in outputs) * COMPUTE[1]
    return dict(MainMemory=dram, GlobalBuffer=max(sram_read, sram_write), Register=0, MAC=mac)


def by_stage(rows, widths, plan):
    result = {}
    for group in plan:
        for i, ((p, q), pin) in enumerate(zip(group.tiles, group.pinned), group.start):
            result[f"Matmul{i}"] = service(rows, widths[i], widths[i+1], group.rows, p, q, pin,
                                          fetch=i == group.start, drain=i == group.stop-1)
    return result
