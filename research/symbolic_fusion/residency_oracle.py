"""Two-context event interpreter; no symbolic/search imports.

GB path preserves the previous interpreter. DRAM has explicit physical tiles,
copy actions and per-output-block logical versions; it never substitutes x=0.

Full-size execution checks allocation lifetimes and every tile's memory actions.
Optional scalar execution also checks values, partial sums and 8-bit overflow.
The service estimate is the native ideal aggregate port model, not a timed DMA
simulator; it is applied independently to the counted events in each phase.
"""
from fractions import Fraction


def execute(n, stripe, tiles, numeric=False,context="gb"):
    if context not in ("gb","dram"):raise ValueError("unknown backing context")
    if type(n) is not int or n <= 0 or type(stripe) is not int or not 0 < stripe <= n or n % stripe:
        raise ValueError('invalid size/stripe')
    if len(tiles) != 3 or any(len(t) != 2 or any(type(x) is not int or x <= 0 or n % x for x in t) for t in tiles):
        raise ValueError('invalid tiles')
    if stripe % tiles[0][1] or stripe % tiles[1][0]:
        raise ValueError('stripe must align with both incident tiles')
    if numeric and n > 8:
        raise ValueError('scalar verification limited to n<=8')
    phases = [dict(dram_read=0, dram_write=0, gb_read=0, gb_write=0, mac=0, cycles=0, reg_read=0, reg_write=0) for _ in range(3)]
    live = {}; current = peak = events = 0
    fixed_peak = 0; carried_peak = None
    memory = {}; registers = {}
    dram_T2 = [[None]*n for _ in range(n)] if numeric else None
    versions = {};version_writes=0
    def alloc(name, rows, cols):
        nonlocal current, peak, events, fixed_peak, carried_peak
        if name in live:
            raise AssertionError('duplicate physical allocation')
        live[name] = rows*cols; current += rows*cols; peak = max(peak, current); events += 1
        if 'T2' in live:
            without_T2 = current-live['T2']
            carried_peak = max(carried_peak or 0,without_T2)
        else:
            fixed_peak = max(fixed_peak,current)
        if numeric:
            memory[name] = [[0]*cols for _ in range(rows)]
    def free(name):
        nonlocal current, events
        current -= live.pop(name); memory.pop(name, None); registers.pop(name,None); events += 1
    def weight(i, r, c):
        return int(c == (r+i+1) % n)  # distinct permutations; dense MAC execution
    def input_value(r, c):
        return (3*r + 2*c + r*c + 1) % 3 - 1
    def wave(phase, inp, inp_row, inp_col, output, out_row, out_col, w, k, j, first):
        nonlocal events
        c = phases[phase]
        c['gb_read'] += k + (0 if first else j)
        c['gb_write'] += j
        c['reg_read'] += k*j
        c['mac'] += k*j; c['cycles'] += 1; events += 1
        if numeric:
            for jj in range(j):
                value = memory[output][out_row][out_col+jj]
                for kk in range(k):
                    value += memory[inp][inp_row][inp_col+kk]*registers[w][kk][jj]
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
                phases[0]['dram_read'] += k*j; phases[0]['gb_write'] += k*j; phases[0]['gb_read'] += k*j; phases[0]['reg_write'] += k*j
                if numeric:
                    memory['W0'] = [[weight(0, red+r, col+c) for c in range(j)] for r in range(k)]
                    registers['W0'] = [row[:] for row in memory['W0']]
                for row in range(n):
                    wave(0, 'T0tile', row, 0, 'T1', row, col-start, 'W0', k, j, red == 0)
                free('W0')
            free('T0tile')
        if context=='gb' and 'T2' not in live:
            alloc('T2', n, n)
        k, j = tiles[1]
        for red in range(start, start+stripe, k):
            for col in range(0, n, j):
                if context=='dram':
                    alloc('T2tile',n,j)
                    if red:
                        if versions.get(col)!=red-k:
                            raise AssertionError('wrong or missing T2 version')
                        phases[1]['dram_read']+=n*j;phases[1]['gb_write']+=n*j
                        if numeric:
                            memory['T2tile']=[row[col:col+j]for row in dram_T2]
                    elif col in versions:
                        raise AssertionError('overwrite of initial T2 version')
                alloc('W1', k, j)
                phases[1]['dram_read'] += k*j; phases[1]['gb_write'] += k*j; phases[1]['gb_read'] += k*j; phases[1]['reg_write'] += k*j
                if numeric:
                    memory['W1'] = [[weight(1, red+r, col+c) for c in range(j)] for r in range(k)]
                    registers['W1'] = [row[:] for row in memory['W1']]
                for row in range(n):
                    wave(1,'T1',row,red-start,'T2' if context=='gb' else 'T2tile',row,col if context=='gb' else 0,'W1',k,j,red==0)
                free('W1')
                if context=='dram':
                    phases[1]['gb_read']+=n*j;phases[1]['dram_write']+=n*j
                    if numeric:
                        for r in range(n):dram_T2[r][col:col+j]=memory['T2tile'][r][:]
                    versions[col]=red;version_writes+=1
                    free('T2tile')
        free('T1')
    prefix_peak=peak
    k, j = tiles[2]
    output = [[None]*n for _ in range(n)] if numeric else None
    for col in range(0, n, j):
        alloc('T3tile', n, j)
        for red in range(0, n, k):
            if context=='dram':
                if len(versions)!=n//tiles[1][1] or any(v!=n-tiles[1][0]for v in versions.values()):
                    raise AssertionError('T2 consumed before its final version')
                alloc('T2input',n,k)
                phases[2]['dram_read']+=n*k;phases[2]['gb_write']+=n*k
                if numeric:memory['T2input']=[row[red:red+k]for row in dram_T2]
            alloc('W2', k, j)
            phases[2]['dram_read'] += k*j; phases[2]['gb_write'] += k*j; phases[2]['gb_read'] += k*j; phases[2]['reg_write'] += k*j
            if numeric:
                memory['W2'] = [[weight(2, red+r, col+c) for c in range(j)] for r in range(k)]
                registers['W2'] = [row[:] for row in memory['W2']]
            for row in range(n):
                wave(2,'T2' if context=='gb' else 'T2input',row,red if context=='gb' else 0,'T3tile',row,0,'W2',k,j,red==0)
            free('W2')
            if context=='dram':free('T2input')
        # A final GB read sends the final output to DRAM. Backed intermediates
        # have no such read; this explains the native stage-2 read asymmetry.
        phases[2]['gb_read'] += n*j; phases[2]['dram_write'] += n*j
        if numeric:
            for row in range(n):
                output[row][col:col+j] = memory['T3tile'][row][:]
        free('T3tile')
    if context=='gb':free('T2')
    if live or current:
        raise AssertionError('leaked allocation')
    if numeric:
        # Untiled reference with distinct, nonsymmetric permutations, rather
        # than identity weights that could hide a transpose or index error.
        expected = [[input_value(r,c) for c in range(n)] for r in range(n)]
        for stage in range(3):
            expected = [[sum(expected[r][red]*weight(stage,red,c) for red in range(n))
                         for c in range(n)] for r in range(n)]
        if output != expected:
            raise AssertionError('incorrect scalar 3mm result')
    # Primitive action prices shared with the declared hardware model, not with
    # the symbolic implementation. There is no call to its formulas/factors.
    energy = 0; latency = Fraction(0)
    prefix_energy=0;prefix_latency=Fraction(0)
    for phase_index,c in enumerate(phases):
        energy += c['dram_read']*56240 + c['dram_write']*56240
        energy += c['gb_read']*1992 + c['gb_write']*2344 + c['mac']*84
        dram_service = Fraction(c['dram_read']+c['dram_write'], 1)/Fraction(192, 5)
        read_service = Fraction(c['gb_read'], 512); write_service = Fraction(c['gb_write'], 128)
        latency += max(Fraction(c['cycles']), dram_service, read_service, write_service)
        if phase_index==1:prefix_energy=energy;prefix_latency=latency
    return dict(peak=peak, energy=energy, latency=latency, phases=phases, events=events,
                numeric_checked=numeric,prefix=(prefix_peak,prefix_energy,prefix_latency),
                dram_version_writes=version_writes,
                effect=dict(base=max(fixed_peak,carried_peak or 0),carried=carried_peak))
