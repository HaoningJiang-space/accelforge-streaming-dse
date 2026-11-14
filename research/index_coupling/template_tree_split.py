"""Train/test check of the size-free template law on multi-operator graph families.

Train: every shape on TRAIN^3; templates are the abstracted witnesses of every
exact frontier point. Test: every shape on TEST^3 with an extent above the
training range; the template frontier must equal the exact v2 frontier point for
point. curve() returns one witness per frontier point, and which of several
equal-cost templates it returns depends on PYTHONHASHSEED, so training takes the
union over --train-seeds hash seeds (each in its own process).
"""
import argparse
import ast
import itertools
import os
import subprocess
import json
from pathlib import Path
import resource
import signal
import sys
from time import perf_counter

from research.index_coupling.decode_census import decoder_block
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph
from research.index_coupling.graph.stacks import attention_stack, ffn_stack
from research.index_coupling.template_census import OPTIONS
from research.index_coupling.template_tree import abstract, frontier

FAMILIES = {
    'matmul': lambda i, j, k: Graph(dict(I=i, J=j, K=k),
                                    [('E', {'A': ('I', 'J'), 'B': ('J', 'K'), 'C': ('I', 'K')})]),
    'ffn1': lambda m, d, f: ffn_stack(1, m=m, d=d, f=f),
    'attn1': lambda m, d, p: attention_stack(1, m=m, p=p, d=d),
    'ffn2': lambda m, d, f: ffn_stack(2, m=m, d=d, f=f),
    # Decoder chain with residuals: model and head dims share x, sequence and hidden share y.
    'block_chain': lambda m, x, y: decoder_block(m, d=x, a=x, t=y, f=y, kv_write=False, swiglu=False),
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('family', choices=FAMILIES)
    p.add_argument('out', type=Path)
    p.add_argument('--train', type=int, nargs='+', default=[1, 2, 4, 8])
    p.add_argument('--test', type=int, nargs='+', default=[1, 16, 64, 256])
    p.add_argument('--seconds', type=int, default=3600)
    p.add_argument('--gib', type=int, default=8)
    p.add_argument('--train-seeds', type=int, default=1)
    p.add_argument('--dump-train', type=Path, help=argparse.SUPPRESS)
    args = p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (args.gib * 2**30, args.gib * 2**30))
    def timeout(*_):
        raise TimeoutError(f'{args.seconds}s budget')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(args.seconds)
    build = FAMILIES[args.family]
    templates, start = {}, perf_counter()
    if args.dump_train:
        for shape in itertools.product(args.train, repeat=3):
            g = build(*shape)
            for _, _, w in curve(g, witness=True, **OPTIONS):
                templates[abstract(g, w)] = None
        args.dump_train.write_text('\n'.join(map(repr, templates)) + '\n')
        return
    for seed in range(args.train_seeds):
        dump = args.out.with_suffix(f'.train{seed}.txt')
        subprocess.run([sys.executable, '-m', __spec__.name, args.family, str(args.out), '--dump-train', str(dump),
                        '--train', *map(str, args.train)], check=True, env=dict(os.environ, PYTHONHASHSEED=str(seed)))
        for line in dump.read_text().splitlines():
            templates[ast.literal_eval(line)] = None
    train_seconds = perf_counter() - start
    summary = dict(family=args.family, train=args.train, test=args.test, train_seeds=args.train_seeds,
                   templates=len(templates),
                   train_seconds=round(train_seconds, 2), equal=0, mismatch=0, exact_seconds=0.,
                   template_seconds=0., status='running')
    with args.out.open('w') as stream:
        try:
            for shape in itertools.product(args.test, repeat=3):
                if max(shape) <= max(args.train):
                    continue
                g = build(*shape)
                t = perf_counter()
                exact = [p[:2] for p in curve(g, **OPTIONS)]
                te = perf_counter() - t
                t = perf_counter()
                pred = [list(p) for p in frontier(g, templates)]
                tp = perf_counter() - t
                ok = [list(p) for p in exact] == pred
                summary['equal' if ok else 'mismatch'] += 1
                summary['exact_seconds'] += te
                summary['template_seconds'] += tp
                row = dict(shape=shape, equal=ok, exact_points=len(exact), exact_seconds=round(te, 3),
                           template_seconds=round(tp, 3))
                if not ok:
                    row.update(exact=exact, predicted=pred)
                stream.write(json.dumps(row) + '\n')
                stream.flush()
            summary['status'] = 'complete'
        except (TimeoutError, MemoryError) as exc:
            summary['status'] = type(exc).__name__
        finally:
            signal.alarm(0)
            summary['exact_seconds'] = round(summary['exact_seconds'], 2)
            summary['template_seconds'] = round(summary['template_seconds'], 2)
            summary['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            stream.write(json.dumps(dict(summary=summary)) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    if sys.platform != 'linux':
        raise SystemExit('run on the Linux server with caps')
    main()
