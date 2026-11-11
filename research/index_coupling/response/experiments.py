"""Experiments of the response study (CONTRACTION_ORACLE.md, SANDWICH_RESULTS.md).

Frozen prediction sets live in results/contraction_oracle/<set>_predictions.json
(nest_predictions.json for `nest`); `verify` recomputes all of them from the
current code without running the grammar, as a fast regression check.

Usage: python -m research.index_coupling.response.experiments COMMAND ...
  verify                              recompute every frozen prediction set
  grammar SET PRED.json OUT.jsonl     grammar check of one frozen set
                                      (SET: nest chain2 chain elementwise weights matmul)
  archive CASE...                     unit-M closed forms vs archived child curves (§10-11)
  op-check CASE...                    operator-projection bound vs archived curves (§14)
  op-c2 CASE...                       ideal C2 exclusions with the operator bound (§14)
  op-work CASE...                     ordered edge pruning on the shared DAG, with ceilings (§17-18)
  closed-form-work CASE...            work removed by unit-M closed-form terminals (§15)
  sandwich CASE...                    LB/UB certificate, coverage and work (SANDWICH_RESULTS.md)
  residency CASE...                   sharing across residency contexts (RESIDENCY_SHARING.md)
  exact-check CASE...                 online substitution: curves and witness replay (§16)
  exact-bench OUT.jsonl REPEATS CASE...   fresh-process timing, baseline vs substitution
  exact-once MODE CASE                one measurement (used by exact-bench)
  exact-mapping-bench OUT.jsonl REPEATS CASE...  native witness generation, including recovery
  exact-mapping-once MODE CASE        one mapping measurement, followed by untimed replay
Archive-based commands default to all eight archived cases when none is given.
"""
from collections import Counter, defaultdict
import json
from math import prod
from pathlib import Path
import sys
import time

from research.index_coupling.c2_bound_audit import dominates, frontier, transformed
from research.index_coupling.census_tools import graph_of
from research.index_coupling.contraction_oracle import grammar as contraction_grammar
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph
from research.index_coupling.graph.stacks import attention_stack, ffn_stack
from research.index_coupling.response import bounds, dag, forms, keep_level
from research.index_coupling.response.chains import archived
from research.index_coupling.response.substitution import OPTIONS, expand, make_exact_kernel

RESULTS = Path(__file__).resolve().parent.parent / 'results/contraction_oracle'
INF = float('inf')


# ---------------------------------------------------------------- frozen sets

def stack(family, layers, d, f):
    """Unit-M FFN or attention stack with every weight external."""
    g = ffn_stack(layers, m=1, d=d, f=f) if family == 'ffn' else attention_stack(layers, m=1, p=f, d=d)
    external = frozenset(t for op in g.ops for t in g.access[op] if 'M' not in g.access[op][t])
    return g, external, ['c', 'e', 'c'] * layers, [d, f, f] * layers + [d]


def chain_graph(sizes):
    ranks = [f'R{j}' for j in range(len(sizes))]
    ops = [(f'E{j}', {f'V{j}': (ranks[j],), f'W{j}': (ranks[j], ranks[j + 1]), f'V{j + 1}': (ranks[j + 1],)})
           for j in range(len(sizes) - 1)]
    return Graph(dict(zip(ranks, sizes)), ops), frozenset(f'W{j}' for j in range(len(sizes) - 1))


def streamed_flags(graph, streamed):
    return [int(any(t in streamed for t in graph.access[op])) for op in graph.ops]


def prediction(name, r):
    """Recompute one frozen row's prediction from the current code."""
    if name == 'nest':
        return forms.loop_nest(r['a'], r['b'], r['C'], r['tile_domain'])
    if name == 'chain2':
        return forms.two_chain(r['a'], r['b'], r['c'], r['C'], r['tile_domain'])
    if name == 'chain':
        return forms.contraction_chain(r['sizes'], r['C'], r['tile_domain'])
    if name in ('elementwise', 'weights'):
        g, _, kinds, sizes = stack(r['family'], r['layers'], r['d'], r['f'])
        flags = streamed_flags(g, set(r.get('streamed', ())))
        return forms.predict(kinds, sizes, r['C'], r['tile_domain'], streamed=flags)
    if name == 'matmul':
        return keep_level.predict(tuple(r['ext']), tuple(r['live']), r['C'], r['tile_domain'])
    raise ValueError(name)


def frozen_rows(name):
    rows = json.load(open(RESULTS / f'{name}_predictions.json'))
    stored = 'loop_nest' if name == 'nest' else 'predict'
    return rows, stored


def verify():
    ok = True
    for name in ('nest', 'chain2', 'chain', 'elementwise', 'weights', 'matmul'):
        rows, stored = frozen_rows(name)
        bad = sum(prediction(name, r) != r[stored] for r in rows)
        ok &= bad == 0
        print(json.dumps(dict(set=name, rows=len(rows), changed=bad)), flush=True)
    if not ok:
        raise SystemExit('frozen predictions changed')


def grammar_value(name, r, cache):
    """Grammar extra traffic of one frozen row (curve() under grammar v2)."""
    if name == 'nest':
        return contraction_grammar(r['a'], r['b'], r['C'], r['tile_domain'])
    if name == 'chain2':
        key = ('chain', (r['a'], r['b'], r['c']), r['tile_domain'])
    elif name == 'chain':
        key = ('chain', tuple(r['sizes']), r['tile_domain'])
    elif name in ('elementwise', 'weights'):
        key = ('stack', (r['family'], r['layers'], r['d'], r['f']), tuple(r.get('streamed', ())), r['tile_domain'])
    else:
        key = ('matmul', tuple(r['ext']), tuple(r['live']), r['tile_domain'])
    if key not in cache:
        if key[0] == 'chain':
            g, external = chain_graph(key[1])
            compulsory = key[1][0] + key[1][-1]
        elif key[0] == 'stack':
            family, layers, d, f = key[1]
            g, external, _, _ = stack(family, layers, d, f)
            external = external - set(key[2])
            compulsory = 2 * d + d * f * len(key[2])
        else:
            m, a, b = key[1]
            g = Graph(dict(M=m, D=a, F=b), [('E', {'X': ('M', 'D'), 'W': ('D', 'F'), 'Y': ('M', 'F')})])
            external = frozenset({'X', 'W', 'Y'} - set(key[2]))
            compulsory = sum(dict(X=m * a, W=a * b, Y=m * b)[t] for t in key[2])
        cache[key] = (curve(g, external=external, tile_domain=key[-1], **OPTIONS), compulsory)
    points, compulsory = cache[key]
    return traffic_at(r['C'], points) - compulsory


def grammar_check(name, pred, out):
    rows = json.load(open(pred))
    stored = 'loop_nest' if name == 'nest' else 'predict'
    cache, bad = {}, 0
    with open(out, 'w') as stream:
        for r in rows:
            r['grammar'] = grammar_value(name, r, cache)
            bad += r['grammar'] != r[stored]
            stream.write(json.dumps(r) + '\n')
    print(json.dumps(dict(set=name, cases=len(rows), mismatches=bad)))


# ---------------------------------------------------------- archive analyses

def capacities(points):
    return range(0, max(c for c, _ in points) + 3)


def archive(cases):
    for case in cases:
        g = graph_of(case)
        _, nodes, _ = dag.load(case)
        c = dict(nodes=len(nodes), qualifying=0, exact=0, positive=0, streamed=0, streamed_exact=0)
        for n in nodes.values():
            ch = archived(g, n['state'], unit_rows=True)
            if ch is None:
                continue
            pts = n['points']
            ok = all(forms.predict(ch.kinds, ch.sizes, C, dag.DOMAIN, ch.first, ch.last, ch.streamed)
                     == traffic_at(C, pts) for C in capacities(pts))
            c['qualifying'] += 1
            c['exact'] += ok
            c['positive'] += any(q > 0 for _, q in pts)
            c['streamed'] += any(ch.streamed)
            c['streamed_exact'] += ok and any(ch.streamed)
        print(json.dumps(dict(case=case, **c)), flush=True)


def op_check(cases):
    for case in cases:
        g = graph_of(case)
        _, nodes, _ = dag.load(case)
        c = dict(qualifying=0, multi_row=0, violations=0, exact=0, positive=0)
        for n in nodes.values():
            ch = archived(g, n['state'])
            if ch is None:
                continue
            pts = n['points']
            lb = [bounds.lower(ch, C) for C in capacities(pts)]
            act = [traffic_at(C, pts) for C in capacities(pts)]
            c['qualifying'] += 1
            c['multi_row'] += ch.rows > 1
            c['violations'] += any(l > a for l, a in zip(lb, act))
            c['exact'] += lb == act
            c['positive'] += any(0 < a < INF for a in act)
        print(json.dumps(dict(case=case, **c)), flush=True)


def lifted(slots, child, allocation, extra, trips):
    """Child bound lifted to the parent level, combined pointwise (max) with the slot bound."""
    lift = frontier((allocation + c, extra + trips * q) for c, q in child if q != INF)
    caps = sorted({c for c, _ in slots} | {c for c, _ in lift})
    return frontier((c, max(traffic_at(c, slots), traffic_at(c, lift))) for c in caps)


def loop_actions(g, nodes, children, pid):
    """Loop retention choices of a group node, in captured order (as c2_bound_audit.analyze)."""
    names = sorted(g.sizes)
    s = nodes[pid]['state']
    ops, ext, resident = tuple(s['ops']), tuple(s['ext']), set(s['external'])
    sizes = dict(zip(names, ext))
    size = lambda t: prod(sizes[v] for v in g.dims(t))
    live = g.tensors(ops) - resident
    if all(size(t) == 1 for t in live):
        return None
    made = {g.output(o) for o in ops}
    actions = []
    for child in children.get(pid, ()):
        cs = nodes[child]['state']
        at = next(i for i, (x, y) in enumerate(zip(ext, cs['ext'])) if x != y)
        v, b = names[at], cs['ext'][at]
        lacking = sorted(t for t in live if v not in g.dims(t))
        keep = set(cs['external']) - resident
        trips = sizes[v] // b
        allocation = sum(size(t) for t in keep)
        extra = (trips - 1) * sum((2 if t in made else 1) * size(t) for t in set(lacking) - keep)
        slots = max(len(set(g.access[o]) - set(cs['external'])) for o in ops)
        actions.append(dict(child=child, axis=v, tile=b, allocation=allocation, extra=extra, trips=trips,
                            slots=slots, full=len(keep) == len(lacking),
                            actual=transformed(nodes[child]['points'], allocation, extra, trips)))
    return actions


def op_bound_curve(ch, a):
    top = max(c for c, _ in a['actual']) - a['allocation'] + 3
    return [(C, bounds.lower(ch, C)) for C in range(top)]


def op_c2(cases):
    """Ideal exclusions (final parent frontier as incumbent): slot bound vs slot max operator bound."""
    for case in cases:
        g = graph_of(case)
        _, nodes, children = dag.load(case)
        c = dict(proper=0, applicable=0, slots=0, op_bound=0)
        for pid, n in nodes.items():
            if n['state']['stage'] != 'group':
                continue
            actions = loop_actions(g, nodes, children, pid)
            if actions is None:
                continue
            anchors = {(a['axis'], a['tile']): nodes[a['child']]['points'] for a in actions if a['full']}
            par = frontier(n['points'])
            for a in actions:
                if a['full']:
                    continue
                c['proper'] += 1
                slots = transformed(anchors[a['axis'], a['tile']], a['allocation'], a['extra'], a['trips'], a['slots'])
                s = dominates(par, slots)
                c['slots'] += s
                ch = archived(g, nodes[a['child']]['state'])
                if ch is None:
                    c['op_bound'] += s
                    continue
                b = lifted(slots, op_bound_curve(ch, a), a['allocation'], a['extra'], a['trips'])
                assert dominates(b, a['actual'])
                c['applicable'] += 1
                c['op_bound'] += dominates(par, b)
        print(json.dumps(dict(case=case, **c)), flush=True)


def op_work(cases):
    """Ordered shadow pruning (c2_bound_audit.analyze policy) with five bounds/ceilings.

    slots: C2 slot bound; op: slot max operator bound; perfect: exact child
    curve for proper choices; perfect_any: exact curve for every choice;
    oracle: keep only the first action attaining each final frontier point.
    """
    modes = ('slots', 'op', 'perfect', 'perfect_any', 'oracle')
    for case in cases:
        g = graph_of(case)
        names = sorted(g.sizes)
        data, nodes, children = dag.load(case)
        cuts = {m: set() for m in modes}
        for pid, n in nodes.items():
            if n['state']['stage'] != 'group':
                continue
            actions = loop_actions(g, nodes, children, pid)
            if actions is None:
                continue
            anchors = {(a['axis'], a['tile']): nodes[a['child']]['points'] for a in actions if a['full']}
            needed = {next(a['child'] for a in actions if p in a['actual']) for p in frontier(n['points'])}
            cuts['oracle'] |= {(pid, a['child']) for a in actions if a['child'] not in needed}
            incumbent = ()
            for a in actions:
                for mode in ('perfect', 'perfect_any') if not a['full'] else ('perfect_any',):
                    if dominates(incumbent, a['actual']):
                        cuts[mode].add((pid, a['child']))
                if not a['full']:
                    slots = transformed(anchors[a['axis'], a['tile']], a['allocation'], a['extra'], a['trips'],
                                        a['slots'])
                    bound = {'slots': slots, 'op': slots}
                    ch = archived(g, nodes[a['child']]['state'])
                    if ch is not None:
                        bound['op'] = lifted(slots, op_bound_curve(ch, a), a['allocation'], a['extra'], a['trips'])
                        assert dominates(bound['op'], a['actual'])
                    for mode, b in bound.items():
                        if dominates(incumbent, b):
                            cuts[mode].add((pid, a['child']))
                incumbent = frontier(incumbent + a['actual'])
            assert incumbent == frontier(n['points'])
        out = dict(case=case, states=len(nodes))
        for mode in modes:
            kept = dag.reach(data['root'], children, cut=cuts[mode])
            out[mode] = dict(cut_edges=len(cuts[mode]), unreachable_states=len(nodes) - len(kept),
                             unreachable_multi_row=sum(nodes[i]['state']['ext'][names.index('M')] > 1
                                                       for i in set(nodes) - kept),
                             saved_fraction=dag.removed(nodes, kept))
        print(json.dumps(out), flush=True)


def closed_form_work(cases):
    for case in cases:
        g = graph_of(case)
        data, nodes, children = dag.load(case)
        terminal = {i for i, n in nodes.items() if archived(g, n['state'], unit_rows=True) is not None}
        kept = dag.reach(data['root'], children, terminal)
        print(json.dumps(dict(case=case, nodes=len(nodes), terminal=len(terminal),
                              terminal_reached=len(terminal & kept), nodes_left=len(kept - terminal),
                              removed=dag.removed(nodes, kept - terminal))), flush=True)


def sandwich(cases):
    for case in cases:
        g = graph_of(case)
        data, nodes, children = dag.load(case)
        c = dict(qualifying=0, multi_row=0, lb_violations=0, ub_violations=0, certified=0,
                 certified_multi_row=0, certified_inexact=0,
                 uncertified_multi_row=dict(ub_gap_only=0, lb_gap_only=0, both=0))
        certified, unit = set(), set()
        for i, n in nodes.items():
            if archived(g, n['state'], unit_rows=True) is not None:
                unit.add(i)
            ch = archived(g, n['state'])
            if ch is None:
                continue
            multi = ch.rows > 1
            pts = n['points']
            act = [traffic_at(C, pts) for C in capacities(pts)]
            lb = [bounds.lower(ch, C) for C in capacities(pts)]
            ub = [bounds.upper(ch, C) for C in capacities(pts)]
            c['qualifying'] += 1
            c['multi_row'] += multi
            c['lb_violations'] += any(l > a for l, a in zip(lb, act))
            c['ub_violations'] += any(u < a for u, a in zip(ub, act))
            if lb == ub:
                certified.add(i)
                c['certified'] += 1
                c['certified_multi_row'] += multi
                c['certified_inexact'] += lb != act
            elif multi:
                ug, lg = ub != act, lb != act
                c['uncertified_multi_row']['both' if ug and lg else 'ub_gap_only' if ug else 'lb_gap_only'] += 1
        out = dict(case=case, **c)
        for label, terminal in (('unit_only', unit), ('certified_only', certified), ('union', unit | certified)):
            out[label] = dag.terminal_work(data, nodes, children, terminal)
        print(json.dumps(out), flush=True)


def residency(cases):
    """How a sub-problem's response varies across weight-residency contexts.

    A context-free key is (ops, ext, owned, non-weight external); its contexts
    are the resident weight sets seen in the archive. Reports the work ceiling
    of solving each key once (keeping its costliest member), whether the gap
    F - LB is the same in every context, pairwise weight interactions of F
    (by distance of the owning ops), and whether each context's curve is the
    most-resident context's curve, a pure (capacity, traffic) shift of it, or
    another shape.
    """
    from itertools import combinations
    from research.index_coupling.c2_bound_audit import COUNTERS
    for case in cases:
        g = graph_of(case)
        _, nodes, _ = dag.load(case)
        weights = {t for op in g.ops for t in g.access[op] if 'M' not in g.access[op][t]}
        owner = {t: op for op in g.ops for t in g.access[op] if t in weights}
        pos = {op: i for i, op in enumerate(g.ops)}
        keys, solves = defaultdict(list), defaultdict(dict)
        for i, n in nodes.items():
            s = n['state']
            keys[(s['stage'], tuple(s['ops']), tuple(s['ext']), tuple(s['owned']), s['constrained'])].append(i)
            if s['stage'] == 'solve' and not s['constrained']:
                ext = set(s['external'])
                solves[(tuple(s['ops']), tuple(s['ext']), tuple(s['owned']), frozenset(ext - weights))][
                    frozenset(ext & weights)] = (tuple(map(tuple, n['points'])), archived(g, s))
        total = {k: sum(n['work'][k] for n in nodes.values()) for k in COUNTERS}
        once = {k: sum(max(nodes[i]['work'][k] for i in ids) for ids in keys.values()) for k in COUNTERS}
        out = dict(case=case, states=len(nodes), context_free_keys=len(keys),
                   ceiling={k: round(1 - once[k] / total[k], 4) for k in COUNTERS})
        c = Counter()
        for key, ctx in solves.items():
            if len(ctx) < 2:
                continue
            multi = key[1][sorted(g.sizes).index('M')] > 1
            top = max(max(cc for cc, _ in p) for p, _ in ctx.values()) + 3
            if all(ch is not None for _, ch in ctx.values()):
                gaps = {tuple(traffic_at(C, p) - bounds.lower(ch, C) if traffic_at(C, p) < INF else None
                              for C in range(top)) for p, ch in ctx.values()}
                c['gap_invariant' if len(gaps) == 1 else 'gap_varies'] += 1
            ref_set = max(ctx, key=len)
            ref = ctx[ref_set][0]
            for R, (pts, _) in ctx.items():
                if R == ref_set:
                    continue
                s_, t_ = pts[0][0] - ref[0][0], pts[0][1] - ref[0][1]
                shape = ('identical' if pts == ref else
                         f'shift{(s_, t_)}' if len(pts) == len(ref) and all((a - s_, b - t_) == r for (a, b), r in zip(pts, ref))
                         else 'other')
                c[('M>1' if multi else 'M=1') + ' ' + shape] += 1
                free = [t for t in weights - R if any(t in g.access[o] for o in key[0])]
                for a, b in combinations(sorted(free), 2):
                    sets = (R | {a, b}, R | {a}, R | {b}, R)
                    if not all(x in ctx for x in sets):
                        continue
                    f = [[traffic_at(C, ctx[x][0]) for C in range(top)] for x in sets]
                    inter = any(v[0] - v[1] - v[2] + v[3] != 0 for v in zip(*f) if INF not in v[1:])
                    near = abs(pos[owner[a]] - pos[owner[b]]) <= 2
                    c[f"pair {'near' if near else 'far'} {'interact' if inter else 'additive'}"] += 1
        out.update(dict(sorted(c.items())))
        print(json.dumps(out), flush=True)


# ------------------------------------------------------- online substitution

def exact_check(cases):
    from research.index_coupling.simulate_nest import simulate
    for case in cases:
        graph = graph_of(case)
        record = dict(case=case)
        start = time.perf_counter()
        base = curve(graph, **OPTIONS)
        record['baseline_seconds'] = time.perf_counter() - start
        kernel, _ = make_exact_kernel()
        stats = {}
        start = time.perf_counter()
        fast = kernel(graph, stats=stats, **OPTIONS)
        record['exact_seconds'] = time.perf_counter() - start
        record['same_curve'] = [p[:2] for p in base] == [p[:2] for p in fast]
        record.update({k: stats.get(k) for k in ('exact_checks', 'exact_hits', 'dp_transitions', 'loop_choices',
                                                 'pareto_candidates', 'merge_inputs')})
        record['closed_form_seconds'] = stats.get('exact_seconds')
        kernel, registry = make_exact_kernel()
        points = kernel(graph, witness=True, **OPTIONS)
        cache, ok = {}, 0
        start = time.perf_counter()
        for c, q, w in points:
            run = simulate(graph, expand(graph, w, registry, cache), scalar_leaf='v2')
            ok += run['valid'] and (run['peak'], run['traffic']) == (c, q)
        record.update(replay_exact=ok, replay_total=len(points), expand_and_replay_seconds=time.perf_counter() - start,
                      expanded_states=len(cache))
        print(json.dumps(record), flush=True)


def exact_once(mode, case, timing='frontier'):
    """Fresh-process search; mapping timing also charges native witness recovery."""
    import platform
    import resource
    if mode not in ('baseline', 'exact') or timing not in ('frontier', 'mapping'):
        raise ValueError((mode, timing))
    graph = graph_of(case)
    start = time.perf_counter()
    solver, registry = (curve, {}) if mode == 'baseline' else make_exact_kernel()
    setup_seconds = time.perf_counter() - start
    stats = {}
    start = time.perf_counter()
    points = solver(graph, stats=stats, witness=timing == 'mapping', **OPTIONS)
    search_seconds = time.perf_counter() - start
    cache = {}
    if timing == 'mapping' and mode == 'exact':
        native_points = [(c, q, expand(graph, w, registry, cache)) for c, q, w in points]
    else:
        native_points = points
    seconds = time.perf_counter() - start
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    keys = ('dp_transitions', 'loop_choices', 'pareto_candidates', 'merge_inputs', 'exact_checks', 'exact_hits',
            'exact_seconds')
    record = dict(mode=mode, case=case, timing=timing, seconds=seconds,
                  search_seconds=search_seconds, recovery_seconds=seconds-search_seconds,
                  setup_seconds=setup_seconds, setup_and_generation_seconds=setup_seconds+seconds,
                  peak_rss_mib=rss / 2**20 if platform.system() == 'Darwin' else rss / 2**10,
                  curve=[p[:2] for p in points], expanded_states=len(cache),
                  misses=stats['solve_cache']['misses'] + stats['group_cache']['misses'],
                  **{k: stats.get(k) for k in keys})
    if timing == 'mapping':
        from research.index_coupling.simulate_nest import simulate
        assert points
        assert all(note[0] != 'exact' for _, _, w in native_points for note in w)
        start = time.perf_counter()
        for c, q, w in native_points:
            run = simulate(graph, w, scalar_leaf='v2')
            assert run['valid'] and (run['peak'], run['traffic']) == (c, q), (case, c, q, run)
        record.update(replay_exact=len(points), replay_total=len(points),
                      replay_seconds=time.perf_counter()-start,
                      placeholders=sum(note[0] == 'exact' for _, _, w in points for note in w))
    print(json.dumps(record))


def exact_bench(out, repeats, cases):
    import subprocess
    with open(out, 'a') as stream:
        for case in cases:
            for r in range(repeats):
                for mode in ('baseline', 'exact'):
                    line = subprocess.check_output(
                        [sys.executable, '-m', 'research.index_coupling.response.experiments', 'exact-once', mode, case],
                        text=True).strip().splitlines()[-1]
                    record = dict(json.loads(line), repeat=r)
                    stream.write(json.dumps(record) + '\n')
                    stream.flush()
                    print(json.dumps({k: record[k] for k in ('case', 'mode', 'repeat', 'seconds', 'peak_rss_mib')}),
                          flush=True)


def exact_mapping_bench(out, repeats, cases):
    """Finish the existing timing ledger; no new search strategy or shape sweep."""
    import hashlib
    import os
    import platform
    import statistics
    import subprocess
    if repeats < 1 or not cases or len(set(cases)) != len(cases):
        raise ValueError('positive repeats and distinct cases required')
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[3]
    here = root / 'research/index_coupling'
    sources = ('response/experiments.py', 'response/substitution.py', 'response/forms.py',
               'response/chains.py', 'graph/curve.py', 'graph/model.py', 'graph/stacks.py',
               'simulate_nest.py', 'census_tools.py')
    manifest = dict(cases=cases, repeats=repeats, python_version=platform.python_version(),
                    system=platform.system(), machine=platform.machine(), pythonhashseed=0,
                    options=OPTIONS, worker_timeout_seconds=120,
                    git_base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                    source_sha256={f: hashlib.sha256((here/f).read_bytes()).hexdigest() for f in sources},
                    timing='witness=True search + recovery of every root point, sharing recovery cache within run',
                    excluded='imports, graph construction, kernel setup (separately reported), executor replay')
    rows, references = [], {}
    with out.open('x') as stream:
        with out.with_suffix('.manifest.json').open('x') as mf:
            json.dump(manifest, mf, indent=2)
            mf.write('\n')
        for case in cases:
            for repeat in range(repeats):
                for mode in (('baseline', 'exact') if repeat % 2 == 0 else ('exact', 'baseline')):
                    result = subprocess.run(
                        [sys.executable, '-m', 'research.index_coupling.response.experiments',
                         'exact-mapping-once', mode, case], cwd=root,
                        env=dict(os.environ, PYTHONHASHSEED='0'), capture_output=True, text=True, timeout=120,
                        check=True)
                    row = dict(json.loads(result.stdout), repeat=repeat)
                    row['same_curve'] = row['curve'] == references.setdefault(case, row['curve'])
                    assert row['same_curve'] and row['replay_exact'] == row['replay_total']
                    if mode == 'exact':
                        assert row['expanded_states'] > 0 and row['placeholders'] > 0
                    rows.append(row)
                    stream.write(json.dumps(row) + '\n')
                    stream.flush()
                    print(json.dumps({k: row[k] for k in ('case', 'mode', 'repeat', 'seconds',
                                                         'search_seconds', 'recovery_seconds', 'replay_exact')}), flush=True)
    summary = []
    for case in cases:
        modes = {}
        for mode in ('baseline', 'exact'):
            subset = [r for r in rows if r['case'] == case and r['mode'] == mode]
            modes[mode] = {k: statistics.median(r[k] for r in subset) for k in
                           ('seconds', 'search_seconds', 'recovery_seconds', 'setup_seconds',
                            'setup_and_generation_seconds', 'replay_seconds', 'peak_rss_mib')}
        summary.append(dict(case=case, modes=modes, frontier_points=len(references[case]),
                            speedup=modes['baseline']['seconds']/modes['exact']['seconds']))
    out.with_suffix('.summary.json').write_text(json.dumps(summary, indent=2) + '\n')


def main(argv):
    command, args = argv[0], argv[1:]
    cases = lambda: args or list(dag.CASES)
    if command == 'verify':
        verify()
    elif command == 'grammar':
        grammar_check(*args)
    elif command == 'exact-once':
        exact_once(*args)
    elif command == 'exact-bench':
        exact_bench(args[0], int(args[1]), args[2:])
    elif command == 'exact-mapping-once':
        exact_once(*args, timing='mapping')
    elif command == 'exact-mapping-bench':
        exact_mapping_bench(args[0], int(args[1]), args[2:])
    else:
        dict(archive=archive, op_check=op_check, op_c2=op_c2, op_work=op_work, closed_form_work=closed_form_work,
             sandwich=sandwich, residency=residency, exact_check=exact_check)[command.replace('-', '_')](cases())


if __name__ == '__main__':
    main(sys.argv[1:])
