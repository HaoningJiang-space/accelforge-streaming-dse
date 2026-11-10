"""Exploratory P21 cut attribution, chosen after inspecting saved witnesses.

No new frozen prediction. Four bottom-cut menus are lifted through I contexts.
The numeric context helper is cross-checked against explicit witnesses and cell
execution. The solver and the original frozen protocol are unchanged.
Run on the designated server: --case 0..15.
"""
import argparse
from functools import lru_cache
import gc
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import time

from research.index_coupling.graph.context import compulsory, lifted_curve, span_ranks, with_extent
from research.index_coupling.graph.curve import cat, curve, flatten, pareto
from research.index_coupling.graph.model import residual
from research.index_coupling.run_p21 import CASES, comparison, frontier, pts, replay


MENUS = {'join_only': (1,), 'after_first': (2,),
         'after_first_split_ex': (1, 2), 'after_pair_split_ex': (1, 3)}


def groups_at(graph, cuts):
    boundaries = (0,) + cuts + (len(graph.ops),)
    return tuple(graph.ops[a:b] for a, b in zip(boundaries, boundaries[1:]))


def lifted_with_witness(graph, bottom):
    """Independent witness construction for this single-rank/input-only context."""
    lacking = sorted(t for t in graph.tensors(graph.ops) if 'I' not in graph.dims(t))
    if any(t in graph.produced() for t in lacking):
        raise ValueError('this P21 wrapper only supports input obligations')

    @lru_cache(None)
    def solve(extent, external):
        g = with_extent(graph, 'I', extent)
        base = compulsory(g, external)
        points = [(c, q-base, w) for c, q, w in bottom(g, external)]
        b = extent // 2
        while b:
            if extent % b:
                b //= 2
                continue
            trips = extent // b
            free = [t for t in lacking if t not in external]
            for bits in product((True, False), repeat=len(free)):
                kept = frozenset(t for t, keep in zip(free, bits) if keep)
                dropped = tuple(t for t in free if t not in kept)
                reserve = sum(g.size(t, ()) for t in kept)
                extra = sum((trips-1)*g.size(t, ()) for t in dropped)
                prefix = (('groups', (graph.ops,), 'kept', (), 'via DRAM', ()),
                          ('loop', graph.ops, 'I', f'tile {b} x{trips}',
                           'kept', tuple(sorted(kept)), 'refetched', dropped))
                points += [(reserve+c, extra+trips*q, cat(prefix, w))
                           for c, q, w in solve(b, external | kept)]
            b //= 2
        return pareto(points)

    base = compulsory(graph)
    return tuple((c, q+base, flatten(w)) for c, q, w in solve(graph.sizes['I'], frozenset()))


def run(index, streamed_tail_only=False):
    shape, depth, reads_x = CASES[index]
    graph = residual(*shape, depth, reads_x)
    archive = Path(__file__).parent / 'results'
    original = json.loads((archive / 'p21' / f'case_{index:02d}.json').read_text())['result']['interfaces'][0]
    attribution = json.loads((archive / 'p21_attribution' / f'case_{index}.json').read_text())
    reference = original['curves']['unrestricted']
    assert reference == attribution['unrestricted']
    menus = {}
    chosen = ({'streamed_tail': (1, 3) + tuple(range(4, len(graph.ops)-1))}
              if streamed_tail_only else MENUS)
    for name, cuts in chosen.items():
        start = time.monotonic()
        groups = groups_at(graph, cuts)

        @lru_cache(None)
        def bottom_at(extent, external):
            return curve(with_extent(graph, 'I', extent), external=external,
                         root_groups=groups, witness=True)

        def bottom(g, external):
            return bottom_at(g.sizes['I'], external)

        top = bottom(graph, frozenset())
        lifted = lifted_with_witness(graph, bottom)
        numeric = pts(lifted_curve(graph, 'I', lambda g, ext: pts(bottom(g, ext))))
        checked = replay(graph, lifted)
        menus[name] = dict(cuts=cuts, groups=groups,
                           span_ranks=[sorted(span_ranks(graph, group)) for group in groups],
                           full=pts(top), lifted=pts(lifted),
                           context_equal=pts(lifted) == numeric,
                           comparison=comparison(pts(lifted), reference),
                           replay=checked, witnesses=lifted,
                           seconds=time.monotonic()-start)
        bottom_at.cache_clear()
        gc.collect()
    union = frontier([p for m in menus.values() for p in m['lifted']])
    return dict(case=index, shape=shape, depth=depth, reads_x=reads_x,
                frozen=original['curves']['actual'], output_resident=attribution['fixed'],
                output_resident_lifted=attribution['lifted'], unrestricted=reference,
                menus=menus, menu_union=union,
                union_comparison=comparison(union, reference))


def timeout(_signal, _frame):
    raise TimeoutError('600-second exploratory case limit')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=int, choices=range(16), required=True)
    parser.add_argument('--streamed-tail-only', action='store_true',
                        help='second exploratory round, selected from residual errors')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (8*2**30, 8*2**30))
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(600)
    start = time.monotonic()
    revision = os.environ.get('P21_SOURCE_REVISION') or subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True).strip()
    result = dict(case=args.case, source_revision=revision, python=platform.python_version(),
                  analysis='exploratory, menus selected after seeing P21 witnesses',
                  protocol_sha256=hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest())
    try:
        result.update(status='complete', result=run(args.case, args.streamed_tail_only))
    except Exception as exc:
        result.update(status='incomplete', error=f'{type(exc).__name__}: {exc}')
    signal.alarm(0)
    result.update(seconds=time.monotonic()-start,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    print(json.dumps(result, allow_nan=False), flush=True)
    raise SystemExit(0 if result['status']=='complete' else 1)
