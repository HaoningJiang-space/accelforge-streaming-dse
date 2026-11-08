"""Price the fixed next-wave DMA policy without enumerating individual tiles."""

import numpy as np

from research.runtime.strip_codesign import COMPUTE, DRAM, GB_READ, GB_WRITE


def transitions(k, n, p, q):
    """Current tile, prior-sum flag, following tile and multiplicity."""
    full_k, tail_k = k//p, k%p
    full_n, tail_n = n//q, n%q
    for width, copies in ((q, full_n), (tail_n, tail_n > 0)):
        yield p, width, False, p, width, copies*(full_k > 1)
        yield p, width, False, tail_k, width, copies*((full_k == 1) & (tail_k > 0))
        yield p, width, True, p, width, copies*np.maximum(full_k-2, 0)
        yield p, width, True, tail_k, width, copies*((full_k > 1) & (tail_k > 0))
    last_k = np.where(tail_k > 0, tail_k, p)
    prior = (full_k > 1) | (tail_k > 0)
    yield last_k, q, prior, p, q, full_n-1
    yield last_k, q, prior, p, tail_n, tail_n > 0


def credit(rows, k, n, p, q, slack):
    """The synchronous DMA ticks removed by adjacent streamed waves."""
    total = 0
    word_ticks = max(DRAM[1], GB_WRITE[1])
    for inner, width, prior, next_inner, next_width, copies in transitions(k, n, p, q):
        ingress = inner + prior*width
        read, mac, write = ingress*GB_READ[1], COMPUTE[1], width*GB_WRITE[1]
        stage = ingress + width
        current, following = inner*width, next_inner*next_width
        overlap = (rows > 1) & (current+stage <= slack)
        charged = current + np.where(overlap, stage, 0) + following
        serial = read+mac+write
        period = np.where(overlap, np.maximum(np.maximum(read, mac), write), serial)
        head = (read+mac)//word_ticks
        gaps = head + (rows-1)*((period-write)//word_ticks)
        serial_gaps = head + (rows-1)*((serial-write)//word_ticks)
        eager = np.where(charged <= slack, np.minimum(gaps, following), 0) * word_ticks
        switched = np.where(current+following <= slack, np.minimum(serial_gaps, following), 0) * word_ticks
        switched -= (rows-1)*(serial-period)
        total += np.maximum(eager, switched) * copies
    return total
