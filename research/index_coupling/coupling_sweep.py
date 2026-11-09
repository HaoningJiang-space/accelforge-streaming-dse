"""Capacity needed for a traffic target, same vs cross coupling (exploratory).

For every shape (NI, NJ, NK, NL) in {4, 8, 16, 32}^4, compute the curve model's
Pareto curves for same and cross coupling, with and without write-through.
S(q) = least capacity whose best traffic is at most q; the analysis compares
S_cross(q) with S_same(q). Results are exact over the curve model's grammar
(consecutive groups, power-of-2 tiles, kept-or-refetched tensors), not over all
executions.
"""
import json
import sys
from itertools import product
from multiprocessing import Pool

from research.index_coupling.curve_model import curve
from research.index_coupling.nest_model import coupling

SIDES = (4, 8, 16, 32)


def run(shape):
    out = {'shape': shape}
    for cross, wt in product((False, True), repeat=2):
        key = f"{'cross' if cross else 'same'}_{'wt' if wt else 'nowt'}"
        out[key] = [list(p) for p in curve(coupling(*shape, cross), write_through=wt)]
    return out


if __name__ == '__main__':
    jobs = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    shapes = list(product(SIDES, repeat=4))
    with Pool(jobs) as pool:
        for record in pool.imap_unordered(run, shapes):
            print(json.dumps(record), flush=True)
