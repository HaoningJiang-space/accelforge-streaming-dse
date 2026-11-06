"""Independent event interpreter; no symbolic formulas or composition imports.

Full-size execution checks allocation lifetimes and every tile's memory actions.
Optional scalar execution also checks values, partial sums and 8-bit overflow.
The service estimate is the native ideal aggregate port model, not a timed DMA
simulator; it is applied independently to the counted events in each phase.
"""
from fractions import Fraction


def execute(n, stripe, tiles, numeric=False):
    if type(n) is not int or n <= 0 or type(stripe) is not int or not 0 < stripe <= n or n % stripe:
        raise ValueError('invalid size/stripe')
    if len(tiles) != 3 or any(len(t) != 2 or any(type(x) is not int or x <= 0 or n % x for x in t) for t in tiles):
        raise ValueError('invalid tiles')
    if stripe % tiles[0][1] or stripe % tiles[1][0]:
        raise ValueError('stripe must align with both incident tiles')
    if numeric and n > 8:
        raise ValueError('scalar verification limited to n<=8')
    phases = [dict(dram_read=0, dram_write=0, gb_read=0, gb_write=0, mac=0, cycles=0) for _ in range(3)]
    live = {}; current = peak = events = 0
    memory = {}
    def alloc(name, rows, cols):
        nonlocal current, peak, events
        if name in live:
            raise AssertionError('duplicate physical allocation')
        live[name] = rows*cols; current += rows*cols; peak = max(peak, current); events += 1
        if numeric:
            memory[name] = [[0]*cols for _ in range(rows)]
    def free(name):
        nonlocal current, events
        current -= live.pop(name); memory.pop(name, None); events += 1
    def weight(i, r, c):
        return int(r == c)  # dense execution, no sparsity shortcut
    def input_value(r, c):
        return (r+c) % 2
    def wave(phase, inp, inp_row, inp_col, output, out_row, out_col, w, k, j, first):
        nonlocal events
        c = phases[phase]
        c['gb_read'] += k + (0 if first else j)
        c['gb_write'] += j
        c['mac'] += k*j; c['cycles'] += 1; events += 1
        if numeric:
            for jj in range(j):
                value = memory[output][out_row][out_col+jj]
                for kk in range(k):
                    value += memory[inp][inp_row][inp_col+kk]*memory[w][kk][jj]
                    if not -128 <= value <= 127:
                        raise AssertionError('8-bit accumulator overflow')
                memory[output][out_row][out_col+jj] = value
    for start in range(0, n, stripe):
        alloc('T1', n, stripe)
        k, j = tiles[0]
        for red in range(0, n, k):
            alloc('T0tile', n, k)
            phases[0]['dram_read'] += n*k; phases[0]['gb_write'] += n*k
            if numeric:
                memory['T0tile'] = [[input_value(r, red+c) for c in range(k)] for r in range(n)]
            for col in range(start, start+stripe, j):
                alloc('W0', k, j)
                phases[0]['dram_read'] += k*j; phases[0]['gb_write'] += k*j; phases[0]['gb_read'] += k*j
                if numeric:
                    memory['W0'] = [[weight(0, red+r, col+c) for c in range(j)] for r in range(k)]
                for row in range(n):
                    wave(0, 'T0tile', row, 0, 'T1', row, col-start, 'W0', k, j, red == 0)
                free('W0')
            free('T0tile')
        if 'T2' not in live:
            alloc('T2', n, n)
        k, j = tiles[1]
        for red in range(start, start+stripe, k):
            for col in range(0, n, j):
                alloc('W1', k, j)
                phases[1]['dram_read'] += k*j; phases[1]['gb_write'] += k*j; phases[1]['gb_read'] += k*j
                if numeric:
                    memory['W1'] = [[weight(1, red+r, col+c) for c in range(j)] for r in range(k)]
                for row in range(n):
                    wave(1, 'T1', row, red-start, 'T2', row, col, 'W1', k, j, red == 0)
                free('W1')
        free('T1')
    k, j = tiles[2]
    output = [[None]*n for _ in range(n)] if numeric else None
    for col in range(0, n, j):
        alloc('T3tile', n, j)
        for red in range(0, n, k):
            alloc('W2', k, j)
            phases[2]['dram_read'] += k*j; phases[2]['gb_write'] += k*j; phases[2]['gb_read'] += k*j
            if numeric:
                memory['W2'] = [[weight(2, red+r, col+c) for c in range(j)] for r in range(k)]
            for row in range(n):
                wave(2, 'T2', row, red, 'T3tile', row, 0, 'W2', k, j, red == 0)
            free('W2')
        # A final GB read sends the final output to DRAM. Backed intermediates
        # have no such read; this explains the native stage-2 read asymmetry.
        phases[2]['gb_read'] += n*j; phases[2]['dram_write'] += n*j
        if numeric:
            for row in range(n):
                output[row][col:col+j] = memory['T3tile'][row][:]
        free('T3tile')
    free('T2')
    if live or current:
        raise AssertionError('leaked allocation')
    if numeric and output != [[input_value(r, c) for c in range(n)] for r in range(n)]:
        raise AssertionError('incorrect scalar 3mm result')
    # Primitive action prices shared with the declared hardware model, not with
    # the symbolic implementation. There is no call to its formulas/factors.
    energy = 0; latency = Fraction(0)
    for c in phases:
        energy += c['dram_read']*56240 + c['dram_write']*56240
        energy += c['gb_read']*1992 + c['gb_write']*2344 + c['mac']*84
        dram_service = Fraction(c['dram_read']+c['dram_write'], 1)/Fraction(192, 5)
        read_service = Fraction(c['gb_read'], 512); write_service = Fraction(c['gb_write'], 128)
        latency += max(Fraction(c['cycles']), dram_service, read_service, write_service)
    return dict(peak=peak, energy=energy, latency=latency, phases=phases, events=events,
                numeric_checked=numeric)
