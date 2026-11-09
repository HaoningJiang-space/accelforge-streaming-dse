"""P17: same and cross curves coincide when a spilled partial sum costs 1."""
import json
import sys
from itertools import product
from multiprocessing import Pool

from research.index_coupling.curve_model import curve
from research.index_coupling.nest_model import coupling


def shapes():
    small = [(i, j, i, l) for i, j, l in product((4, 8, 16, 32), repeat=3)]
    held = [(64, j, 64, l) for j in (4, 8, 16, 32, 64) for l in (4, 8, 16, 32, 64)] + \
           [(i, j, i, 64) for i in (8, 16, 32) for j in (4, 16)]
    return small + held


def run(shape):
    out = {'shape': shape}
    for cost in (1, 2):
        same = [list(p[:2]) for p in curve(coupling(*shape, False), spill_cost=cost)]
        cross = [list(p[:2]) for p in curve(coupling(*shape, True), spill_cost=cost)]
        out[f'identical_spill{cost}'] = same == cross
    return out


if __name__ == '__main__':
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as pool:
        for record in pool.imap_unordered(run, shapes()):
            print(json.dumps(record), flush=True)
