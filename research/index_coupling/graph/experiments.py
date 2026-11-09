"""Experiment runners for the graph models; each prints JSON lines or a table.

Usage: python -m research.index_coupling.graph.experiments <command> [args]
  plateau                       P8: nest-model plateaus vs measured FFM plateaus
  compare                       curve model vs every saved small FFM frontier
  classify [small] [ffn]        P11-P13: write-through switch and chain view
  ffm-like [small]              P14: FFM-like curve vs FFM (default: FFN)
  ffn-part PART [max_capacity]  one FFN M8 D4 F8 curve: graph, nowt, chain,
                                ffm_like:<materialized intermediates joined by +>,
                                or ffm_like_si:<...> (inputs shareable, P14-FFN')
  sweep [jobs] [heldout]        two-consumer coupling sweep (P15/P16 data)
  p17 [jobs]                    same vs cross with spill cost 1 and 2
  p18 [jobs] | p19 [jobs]       multi-consumer forks
  fork I J K L roles            one fork curve, same record format as p18/p19
  witness I J K L pure mixed    witnesses at the maximum capacity gap
PROTOCOL.md defines every prediction. Heavy commands belong on the experiment
server with memory and time caps.
"""
import json
import resource
import sys
import time
from itertools import product
from multiprocessing import Pool

from research.index_coupling.graph.analysis import capacity_for, compare_to_reference, delta, traffic_at
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import coupling, ffn, fork
from research.index_coupling.graph.plateau import plateau
from research.index_coupling.graph.references import cases, ffn_case
from research.index_coupling.graph.views import chain_curve, ffm_like_curve, ffm_like_part

SIDES = (4, 8, 16, 32)
P18_ROLES = ('kkk', 'kki', 'ikk', 'iik', 'kkkk', 'kkki', 'kkii')
P19_ROLES = ('kkkkkk', 'kkkkki', 'kkkkii', 'kkkiii')


def pts(points):
    return [list(p[:2]) for p in points]


def sweep_shapes():
    return list(product(SIDES, repeat=4))


def heldout_shapes():
    # P15/P16 held-out shapes (PROTOCOL.md): I = K, at least one side 64.
    return [(64, j, 64, l) for j in (4, 8, 16, 32, 64) for l in (4, 8, 16, 32, 64)] + \
           [(i, j, i, 64) for i in (8, 16, 32) for j in (4, 16)]


def p17_shapes():
    return [(i, j, i, l) for i, j, l in product(SIDES, repeat=3)] + heldout_shapes()


def p18_shapes():
    return [(n, j, n, l) for n, j, l in product((4, 8, 16), (4, 8), (4, 8))]


def p19_shapes():
    return [(n, j, n, l) for n, j, l in product((8, 16), (4, 8), (2, 4))]


def run_sweep(shape):
    out = {'shape': shape}
    for cross, wt in product((False, True), repeat=2):
        key = f"{'cross' if cross else 'same'}_{'wt' if wt else 'nowt'}"
        out[key] = [list(p) for p in curve(coupling(*shape, cross), write_through=wt)]
    return out


def run_p17(shape):
    out = {'shape': shape}
    for cost in (1, 2):
        same = pts(curve(coupling(*shape, False), spill_cost=cost))
        cross = pts(curve(coupling(*shape, True), spill_cost=cost))
        out[f'identical_spill{cost}'] = same == cross
    return out


def run_fork(job):
    shape, roles = job
    return {'shape': shape, 'roles': roles, 'points': pts(curve(fork(*shape, roles)))}


def pool_map(function, jobs, workers):
    with Pool(workers) as pool:
        for record in pool.imap_unordered(function, jobs):
            print(json.dumps(record), flush=True)


def plateau_table():
    # (label, graph, measured FFM plateau, role). Calibration points were seen
    # before the model was written; held-out points were frozen in PROTOCOL.md.
    rows = [
        ('square n=4 same', coupling(4, 4, 4, 4, False), 21, 'calibration'),
        ('square n=8 cross', coupling(8, 8, 8, 8, True), 73, 'calibration'),
        ('square n=16 same', coupling(16, 16, 16, 16, False), 273, 'calibration'),
        ('T2 64,8,8,8 same', coupling(64, 8, 8, 8, False), 201, 'calibration'),
        ('T2 64,8,8,8 cross', coupling(64, 8, 8, 8, True), 201, 'calibration'),
        ('T3 8,32,32,32 cross', coupling(8, 32, 32, 32, True), 265, 'calibration'),
        ('FFN M8 D4 F8', ffn(8, 4, 8), 147, 'calibration'),
        ('FFN M16 D4 F8', ffn(16, 4, 8), 147, 'calibration'),
        ('FFN M4 D4 F16', ffn(4, 4, 16), 81, 'calibration'),
        ('C1 16,4,32,8 same', coupling(16, 4, 32, 8, False), 337, 'held-out'),
        ('C1 16,4,32,8 cross', coupling(16, 4, 32, 8, True), 337, 'held-out'),
        ('C2 8,16,4,32 same', coupling(8, 16, 4, 32, False), 37, 'held-out'),
        ('C2 8,16,4,32 cross', coupling(8, 16, 4, 32, True), 37, 'held-out'),
        ('F3 FFN M8 D2 F16', ffn(8, 2, 16), 75, 'held-out'),
        ('F4 FFN M16 D8 F4', ffn(16, 8, 4), 153, 'held-out'),
    ]
    for label, graph, measured, role in rows:
        value = plateau(graph)
        print(f'{label:22s} {role:11s} model {value:5} FFM {measured:5} FFM-model {measured - value:+d}', flush=True)


def compare():
    total = exact = 0
    for name, graph, ffm in cases():
        model = curve(graph)
        diffs = [(c, traffic_at(c, model) - t) for c, t in ffm]
        better = [d for d in diffs if d[1] < -1e-9]
        worse = [d for d in diffs if d[1] > 1e-9]
        total += len(diffs)
        exact += len(diffs) - len(better) - len(worse)
        print(f'{name:22s} FFM points {len(diffs):2}  model better {better}  model worse {worse}', flush=True)
    print(f'total {total} points, {exact} exact')


def classify(which):
    # Version 2: scores against Q_FFM(C) and uses the corrected chain view.
    which = which or ['small', 'ffn']
    todo = (list(cases()) if 'small' in which else []) + ([ffn_case()] if 'ffn' in which else [])
    for name, graph, ffm in todo:
        t0 = time.time()
        on, off, chain = curve(graph), curve(graph, write_through=False), chain_curve(graph)
        print(json.dumps({
            'case': name, 'seconds': round(time.time() - t0, 1), 'ffm': ffm,
            'graph': pts(on), 'no_write_through': pts(off), 'chain': pts(chain),
            # Q_FFM(C) = best saved FFM traffic within capacity C (the archive keeps
            # dominated records at equal capacity). Columns: C, Q_FFM, then
            # graph, no-write-through and chain minus Q_FFM.
            'vs_ffm_best': [[c, traffic_at(c, ffm), traffic_at(c, on) - traffic_at(c, ffm),
                             traffic_at(c, off) - traffic_at(c, ffm), traffic_at(c, chain) - traffic_at(c, ffm)]
                            for c in sorted({c for c, _ in ffm})],
        }), flush=True)


def ffm_like(args):
    todo = list(cases()) if 'small' in args else [ffn_case()]
    for name, graph, ffm in todo:
        model = ffm_like_curve(graph)
        diffs = [list(row) for row in compare_to_reference(model, ffm) if row[2] != 0]
        full = pts(curve(graph)) if 'attention' in name else None
        print(json.dumps({'case': name, 'ffm_like': [list(p) for p in model], 'diffs': diffs,
                          'equals_graph_curve': full == [list(p) for p in model] if full else None}),
              flush=True)


def ffn_part(part, max_capacity=None):
    # Optional capacity cap: exact up to the cap (see curve()), and above FFM's largest
    # saved capacity (147) it cannot change any P12/P14-FFN comparison.
    kw = {'max_capacity': int(max_capacity)} if max_capacity else {}
    graph = ffn(8, 4, 8)
    t = time.time()
    if part == 'graph':
        points = curve(graph, **kw)
    elif part == 'nowt':
        points = curve(graph, write_through=False, **kw)
    elif part == 'chain':
        points = chain_curve(graph, **kw)
    else:
        # ffm_like:<...> separates multi-consumer inputs (P14-FFN); ffm_like_si:<...>
        # keeps them shareable (P14-FFN').
        kind, chosen = part.split(':', 1)
        points = ffm_like_part(graph, {x for x in chosen.split('+') if x},
                               separate_inputs=kind == 'ffm_like', **kw)
    # ru_maxrss is in KiB on Linux, where these runs belong.
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20
    print(json.dumps({'part': part, 'seconds': round(time.time() - t), 'peak_gib': round(peak, 2),
                      'points': pts(points)}))


def witness(i, j, k, l, pure, mixed):
    # At the smallest extra-traffic target q attaining max dS, the witness of the
    # least-capacity point reaching q for each graph.
    shape = tuple(map(int, (i, j, k, l)))
    curves = {r: curve(fork(*shape, r), witness=True) for r in (pure, mixed)}
    ds = delta(curves[pure], curves[mixed])
    q, gap, _ = max(ds, key=lambda r: (r[1], -r[0]))
    print('shape', shape, 'max dS', gap, 'at q', q)
    for r in (pure, mixed):
        base = curves[r][-1][1]
        c, t, w = min((p for p in curves[r] if p[1] - base <= q), key=lambda p: p[0])
        assert c == capacity_for(curves[r], q)
        print(f'--- {r}: capacity {c} traffic {t}')
        for note in w:
            print('   ', note)


def main(argv):
    command, args = argv[0], argv[1:]
    workers = int(args[0]) if args and args[0].isdigit() else None
    if command == 'plateau':
        plateau_table()
    elif command == 'compare':
        compare()
    elif command == 'classify':
        classify(args)
    elif command == 'ffm-like':
        ffm_like(args)
    elif command == 'ffn-part':
        ffn_part(*args)
    elif command == 'sweep':
        pool_map(run_sweep, heldout_shapes() if 'heldout' in args[1:] else sweep_shapes(), workers or 8)
    elif command == 'p17':
        pool_map(run_p17, p17_shapes(), workers or 4)
    elif command in ('p18', 'p19'):
        shapes, roles = (p18_shapes(), P18_ROLES) if command == 'p18' else (p19_shapes(), P19_ROLES)
        pool_map(run_fork, [(s, r) for s in shapes for r in roles], workers or 4)
    elif command == 'fork':
        print(json.dumps(run_fork((tuple(map(int, args[:4])), args[4]))), flush=True)
    elif command == 'witness':
        witness(*args)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:] or ['help'])
