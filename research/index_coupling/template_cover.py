"""How many size-free templates does an exact frontier law need?

K is the least number of templates whose evaluated frontiers reach every exact
frontier point of every shape in an evaluation grid. It does not depend on
which tied witness curve() returns. The candidate pool is the union of witness
templates over a training grid and several hash seeds (each in its own
process); greedy set cover gives an upper bound on K for that pool, and points
no pool template reaches are reported.
"""
import argparse
import ast
import itertools
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
from time import perf_counter

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.stacks import attention_stack, ffn_stack
from research.index_coupling.template_census import OPTIONS
from research.index_coupling.template_tree import abstract, evaluate
from research.index_coupling.template_tree_split import FAMILIES as BASE

FAMILIES = dict(BASE, **{
    'ffn3': lambda m, d, f: ffn_stack(3, m=m, d=d, f=f),
    'ffn4': lambda m, d, f: ffn_stack(4, m=m, d=d, f=f),
    'attn2': lambda m, d, p: attention_stack(2, m=m, p=p, d=d),
})


def reaches(points, c, q):
    return any(pc <= c and pq <= q for pc, pq in points)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('family', choices=FAMILIES)
    p.add_argument('out', type=Path)
    p.add_argument('--train', type=int, nargs='+', default=[1, 2, 4, 8])
    p.add_argument('--evaluate', type=int, nargs='+', default=[1, 2, 4, 8, 16, 64])
    p.add_argument('--seeds', type=int, default=8)
    p.add_argument('--gib', type=int, default=8)
    p.add_argument('--closure', action='store_true',
                   help='also pool the witness templates of the evaluation shapes (in-sample K)')
    p.add_argument('--dump', type=Path, help=argparse.SUPPRESS)
    args = p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (args.gib * 2**30, args.gib * 2**30))
    build = FAMILIES[args.family]
    if args.dump:
        pool = {}
        for shape in itertools.product(args.train, repeat=3):
            g = build(*shape)
            for _, _, w in curve(g, witness=True, **OPTIONS):
                pool[abstract(g, w)] = None
        args.dump.write_text(''.join(repr(t) + '\n' for t in pool))
        return
    start = perf_counter()
    pool = {}
    for seed in range(args.seeds):
        dump = args.out.with_suffix(f'.pool{seed}.txt')
        grid = sorted(set(args.train) | set(args.evaluate)) if args.closure else args.train
        subprocess.run([sys.executable, '-m', __spec__.name, args.family, str(args.out), '--dump', str(dump),
                        '--train', *map(str, grid), '--gib', str(args.gib)],
                       check=True, env=dict(os.environ, PYTHONHASHSEED=str(seed)))
        for line in dump.read_text().splitlines():
            pool[ast.literal_eval(line)] = None
        dump.unlink()
    pool = list(pool)
    pool_seconds = perf_counter() - start
    # Coverage: element = (shape, frontier point); set = template.
    elements, covers, uncovered = [], [set() for _ in pool], 0
    exact_seconds = template_seconds = 0.
    for shape in itertools.product(args.evaluate, repeat=3):
        g = build(*shape)
        t = perf_counter()
        exact = [p[:2] for p in curve(g, **OPTIONS)]
        exact_seconds += perf_counter() - t
        t = perf_counter()
        fronts = [evaluate(g, tpl) for tpl in pool]
        template_seconds += perf_counter() - t
        for c, q in exact:
            e = len(elements)
            elements.append((shape, c, q))
            hit = [i for i, f in enumerate(fronts) if reaches(f, c, q)]
            for i in hit:
                covers[i].add(e)
            uncovered += not hit
    coverable = set().union(*covers) if covers else set()
    chosen, gains, left = [], [], set(coverable)
    while left:
        best = max(range(len(pool)), key=lambda i: len(covers[i] & left))
        chosen.append(best)
        gains.append(len(covers[best] & left))
        left -= covers[best]
    record = dict(family=args.family, train=args.train, evaluate=args.evaluate, seeds=args.seeds,
                  closure=args.closure,
                  ops=len(build(2, 2, 2).ops), pool=len(pool), shapes=len(args.evaluate) ** 3,
                  points=len(elements), uncovered_points=uncovered, k_greedy=len(chosen),
                  greedy_gain=gains,
                  pool_seconds=round(pool_seconds, 2), exact_seconds=round(exact_seconds, 2),
                  template_seconds=round(template_seconds, 2),
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  chosen=[repr(pool[i]) for i in chosen])
    args.out.write_text(json.dumps(record) + '\n')
    print(json.dumps({k: v for k, v in record.items() if k not in ('chosen', 'greedy_gain')}), flush=True)


if __name__ == '__main__':
    if sys.platform != 'linux':
        raise SystemExit('run on the Linux server with caps')
    main()
