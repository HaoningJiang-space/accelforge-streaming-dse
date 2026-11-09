"""P19 (PROTOCOL.md): forks with six consumers of X."""
import json
import sys
from itertools import product
from multiprocessing import Pool

from research.index_coupling.curve_model import curve
from research.index_coupling.nest_model import fork

ROLES = ('kkkkkk', 'kkkkki', 'kkkkii', 'kkkiii')


def shapes():
    return [(n, j, n, l) for n, j, l in product((8, 16), (4, 8), (2, 4))]


def run(job):
    shape, roles = job
    return {'shape': shape, 'roles': roles, 'points': [list(p[:2]) for p in curve(fork(*shape, roles))]}


if __name__ == '__main__':
    jobs = [(s, r) for s in shapes() for r in ROLES]
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as pool:
        for record in pool.imap_unordered(run, jobs):
            print(json.dumps(record), flush=True)
