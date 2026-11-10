"""Cut DP versus partition enumeration: equality, witness replay and cost.

For one graph, runs curve() with partitions='enumerate' and partitions='dp'
in separate capped child processes, then checks that the curves are equal and
that every DP frontier witness executes exactly. Also records the largest
number of crossing tensors at any cut of the whole graph.

Usage (designated server): python -m research.index_coupling.bench_cut_dp
    GRAPH ARGS... [--seconds S] [--mem-gib G] [--dp-only]
GRAPH is residual (I K L DEPTH READS_X) or fork (I J K L ROLES).
"""
import argparse
import json
import multiprocessing as mp
import resource
import time

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import fork, residual
from research.index_coupling.simulate_nest import simulate


def build(kind, args):
    if kind == 'residual':
        i, k, l, depth, reads_x = args
        return residual(int(i), int(k), int(l), int(depth), reads_x in ('1', 'true', 'True'))
    i, j, k, l, roles = args
    return fork(int(i), int(j), int(k), int(l), roles)


def width(graph):
    ops = graph.ops
    use = [graph.tensors((op,)) for op in ops]
    return max((sum(1 for t in graph.tensors(ops)
                    if any(t in u for u in use[:p]) and any(t in u for u in use[p:]))
                for p in range(1, len(ops))), default=0)


def arm(kind, args, mode, mem_gib, queue):
    limit = int(mem_gib * 2**30)
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    graph = build(kind, args)
    start = time.time()
    try:
        points = curve(graph, witness=mode == 'dp', partitions=mode)
    except MemoryError:
        queue.put(dict(status='memory', seconds=time.time() - start))
        return
    seconds = time.time() - start
    replays = None
    if mode == 'dp':
        replays = sum(1 for c, q, w in points
                      if (lambda a: a['valid'] and (a['peak'], a['traffic']) == (c, q))(simulate(graph, w)))
    queue.put(dict(status='complete', seconds=seconds, points=[list(p[:2]) for p in points],
                   replay_exact=replays,
                   peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def run(kind, args, mode, seconds, mem_gib):
    queue = mp.Queue()
    proc = mp.Process(target=arm, args=(kind, args, mode, mem_gib, queue))
    proc.start()
    proc.join(seconds)
    if proc.is_alive():
        proc.kill()
        proc.join()
        return dict(status='timeout', seconds=seconds)
    return queue.get() if not queue.empty() else dict(status='crashed', exitcode=proc.exitcode)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('residual', 'fork'))
    parser.add_argument('args', nargs=5)
    parser.add_argument('--seconds', type=int, default=1800)
    parser.add_argument('--mem-gib', type=float, default=8)
    parser.add_argument('--dp-only', action='store_true')
    a = parser.parse_args()
    graph = build(a.kind, a.args)
    out = dict(kind=a.kind, args=a.args, n_ops=len(graph.ops), max_crossing=width(graph),
               dp=run(a.kind, a.args, 'dp', a.seconds, a.mem_gib))
    if not a.dp_only:
        out['enumerate'] = run(a.kind, a.args, 'enumerate', a.seconds, a.mem_gib)
        if out['dp']['status'] == out['enumerate']['status'] == 'complete':
            out['equal'] = out['dp']['points'] == out['enumerate']['points']
    print(json.dumps(out), flush=True)
