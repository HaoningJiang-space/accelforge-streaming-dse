"""Bounded loop-conditioned factor audit, not a generic hypergraph solver.

python -m research.index_coupling.hypergraph_audit run NEW_DIRECTORY
See LOOP_CONDITIONED_FACTORS.md for the fixed M-to-one branch and proof.
"""
import ast
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
from itertools import product
import json
from math import prod
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time

from research.index_coupling.c2_bound_audit import frontier, state_key, transformed
from research.index_coupling.census_tools import graph_of
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import tile_sizes
from research.index_coupling.graph.curve import curve, pareto
from research.index_coupling.graph.model import Graph
from research.index_coupling.response import dag, forms
from research.index_coupling.response.chains import recognise
from research.index_coupling.response.experiments import loop_actions
from research.index_coupling.response.substitution import (
    CURVE_SOURCE, OPTIONS, expand, frontier_of, make_exact_kernel, native,
)
from research.index_coupling.simulate_nest import simulate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('ffn_forward_l1_m8', 'ffn_forward_l2_m8', 'ffn_forward_l4')
MODES = ('native', 'forms', 'joint')


def restrict_branch(tree):
    """Restrict only the root group to rank M, tile 1; all descendants unchanged."""
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
    outer.body[1:1] = ast.parse('''
_branch_target = (graph.ops, tuple(graph.sizes[v] for v in sorted(graph.sizes)),
                  frozenset(external), frozenset(written))
''').body
    group = next(n for n in ast.walk(outer) if isinstance(n, ast.FunctionDef) and n.name == '_group_curve')
    rank_loop = [n for n in ast.walk(group) if isinstance(n, ast.For)
                 and isinstance(n.target, ast.Name) and n.target.id == 'v']
    tile_loop = [n for n in ast.walk(group) if isinstance(n, ast.For)
                 and isinstance(n.target, ast.Name) and n.target.id == 'b']
    assert len(rank_loop) == len(tile_loop) == 1
    rank_loop[0].body[0:0] = ast.parse('''
if (group, ext, external, owned) == _branch_target and v != 'M':
    continue
''').body
    tile_loop[0].body[0:0] = ast.parse('''
if (group, ext, external, owned) == _branch_target and b != 1:
    continue
''').body


def kernel(mode):
    if mode == 'forms':
        return make_exact_kernel(transform=restrict_branch)
    tree = ast.parse(CURVE_SOURCE.read_text(), filename=str(CURVE_SOURCE))
    restrict_branch(tree)
    ns = dict(__name__='research.index_coupling.graph._fixed_m_branch',
              __package__='research.index_coupling.graph')
    exec(compile(ast.fix_missing_locations(tree), str(CURVE_SOURCE), 'exec'), ns)
    return ns['curve'], {}


class JointFactors:
    """Joint minimization over private weights, group boundaries and exact sums."""
    def __init__(self, graph):
        self.graph = graph
        self.names = tuple(sorted(graph.sizes))
        self.chain = recognise(graph, graph.ops, tuple(graph.sizes[v] for v in self.names),
                               frozenset(), frozenset(), self.names)
        ch = self.chain
        assert ch is not None and ch.rows == graph.sizes['M'] > 1
        assert 1 in tile_sizes(graph.sizes['M'])
        self.n, self.r = len(ch.kinds), ch.rows
        self.segments = forms.segments(ch.kinds)
        assert {p for _, _, p in self.segments} <= {'c', 'e', 'cc', 'ce', 'ec', 'cec'}
        self.weights = {}
        for j, op in enumerate(graph.ops):
            missing = [t for t in graph.access[op] if 'M' not in graph.dims(t)]
            assert len(missing) == (ch.kinds[j] == 'c')
            if missing:
                self.weights[j] = (missing[0], graph.size(missing[0], ()))
        assert {t for t, _ in self.weights.values()} == {
            t for t in graph.tensors(graph.ops) if 'M' not in graph.dims(t)}
        self.sums, self.work = {0}, Counter()
        for _, size in self.weights.values():
            self.work['subset_sum_updates'] += len(self.sums)
            self.sums |= {a + size for a in self.sums}
        self.sums = tuple(sorted(self.sums))
        self.work['reservation_domain'] = len(self.sums)
        self.work['full_masks_not_enumerated'] = 2**len(self.weights)
        self.factor_seconds = 0.

    @lru_cache(maxsize=None)
    def edges(self, child_capacity):
        """Local factors depend on C-a, never just the prefix's used capacity."""
        start = time.perf_counter()
        ch, edges = self.chain, defaultdict(list)
        for j, k, pattern in self.segments:
            variables = [i for i in range(j, k) if i in self.weights]
            assert len(variables) <= 2
            for incoming in ((ch.first,) if j == 0 else (False, True)):
                for outgoing in ((ch.last,) if k == self.n else (False, True)):
                    rho = ch.sizes[j] * (incoming and j > 0) + ch.sizes[k] * (outgoing and k < self.n)
                    spill = 2 * ch.sizes[k] if k < self.n and not outgoing else 0
                    for bits in product((False, True), repeat=len(variables)):
                        kept = {i for i, keep in zip(variables, bits) if keep}
                        reservation = sum(self.weights[i][1] for i in kept)
                        extra = (self.r-1) * sum(self.weights[i][1] for i in variables if i not in kept)
                        streamed = tuple(int(i in self.weights and i not in kept) for i in range(j, k))
                        self.work['local_factor_requests'] += 1
                        q = forms._group(pattern, ch.sizes[j:k+1], child_capacity-rho,
                                         incoming, outgoing, 'halving', streamed)
                        if q != float('inf'):
                            edges[j, incoming].append((k, outgoing, reservation,
                                                       extra + self.r*(q+spill), sum(1 << i for i in kept)))
                            self.work['feasible_local_factors'] += 1
        self.factor_seconds += time.perf_counter()-start
        return edges

    def at(self, capacity):
        best = (float('inf'), 0, 0)
        for total in self.sums:
            if total > capacity:
                break
            edges = self.edges(capacity-total)
            states = [dict() for _ in range(self.n+1)]
            states[0][self.chain.first, 0] = (0, 0)
            for j in range(self.n):
                for (incoming, used), (value, mask) in states[j].items():
                    self.work['dp_states'] += 1
                    for k, outgoing, allocation, extra, local_mask in edges.get((j, incoming), ()):
                        self.work['transition_candidates'] += 1
                        if used+allocation > total:
                            continue
                        self.work['dp_transitions'] += 1
                        key, cost = (outgoing, used+allocation), value+extra
                        if cost < states[k].get(key, (float('inf'), 0))[0]:
                            states[k][key] = (cost, mask | local_mask)
            self.work['max_layer_states'] = max(self.work['max_layer_states'], max(map(len, states)))
            value, mask = states[-1].get((self.chain.last, total), (float('inf'), 0))
            if value < best[0]:
                best = value, total, mask
        return best

    def frontier(self):
        top = self.sums[-1] + 2*sum(self.chain.sizes) + self.n + 4
        points, best = [], float('inf')
        for c in range(top+1):
            q, a, mask = self.at(c)
            self.work['capacity_queries'] += 1
            if q < best:
                points.append((c, q, a, mask))
                best = q
            if q == 0:
                return points
        raise AssertionError('constructive zero-traffic bound not attained')


class BreakpointFactors(JointFactors):
    """Same branch, one boundary DP per local-response breakpoint, all sums at once."""
    def __init__(self, graph, domain='halving'):
        super().__init__(graph)
        self.domain = domain
        self.local_curves = {}
        self.factors = []
        start = time.perf_counter()
        ch = self.chain
        for j, k, pattern in self.segments:
            variables = [i for i in range(j, k) if i in self.weights]
            assert len(variables) <= 2
            for incoming in ((ch.first,) if j == 0 else (False, True)):
                for outgoing in ((ch.last,) if k == self.n else (False, True)):
                    rho = ch.sizes[j] * (incoming and j > 0) + ch.sizes[k] * (outgoing and k < self.n)
                    spill = 2 * ch.sizes[k] if k < self.n and not outgoing else 0
                    for bits in product((False, True), repeat=len(variables)):
                        kept = {i for i, keep in zip(variables, bits) if keep}
                        allocation = sum(self.weights[i][1] for i in kept)
                        extra = (self.r-1) * sum(self.weights[i][1] for i in variables if i not in kept)
                        streamed = tuple(int(i in self.weights and i not in kept) for i in range(j, k))
                        key = (pattern, ch.sizes[j:k+1], incoming, outgoing, domain, streamed)
                        self.work['local_factor_requests'] += 1
                        points = self.local_frontier(key)
                        self.factors.append((j, k, incoming, outgoing, allocation, extra, rho,
                                             spill, sum(1 << i for i in kept), key, points))
        self.budgets = sorted({c + f[6] for f in self.factors for c, _ in f[-1]})
        self.work['child_budget_breakpoints'] = len(self.budgets)
        self.factor_seconds = time.perf_counter()-start

    def local_frontier(self, key):
        if key not in self.local_curves:
            pattern, sizes, incoming, outgoing, domain, streamed = key
            points, best = [], float('inf')
            for c in range(2*sum(sizes)+len(pattern)+5):
                self.work['local_capacity_probes'] += 1
                q = forms._group(pattern, sizes, c, incoming, outgoing, domain, streamed)
                if q < best:
                    points.append((c, q))
                    best = q
                if q == 0:
                    break
            assert best == 0, key
            self.local_curves[key] = tuple(points)
            self.work['local_frontiers'] += 1
            self.work['local_frontier_points'] += len(points)
        return self.local_curves[key]

    def frontier(self):
        results = []
        for budget in self.budgets:
            self.work['capacity_queries'] += 1
            edges = defaultdict(list)
            for f in self.factors:
                feasible = next(((c, q) for c, q in reversed(f[-1]) if c+f[6] <= budget), None)
                if feasible is not None:
                    edges[f[0], f[2]].append((f, feasible))
            states = [dict() for _ in range(self.n+1)]
            states[0][self.chain.first, 0] = (0, None)
            for j in range(self.n):
                for (incoming, used), (value, path) in states[j].items():
                    self.work['dp_states'] += 1
                    for f, (c, q) in edges.get((j, incoming), ()):
                        self.work['dp_transitions'] += 1
                        k, outgoing, allocation, extra = f[1], f[3], f[4], f[5]
                        cost = value+extra+self.r*(q+f[7])
                        key = outgoing, used+allocation
                        if cost < states[k].get(key, (float('inf'), None))[0]:
                            states[k][key] = cost, (path, f, (c, q))
            self.work['max_layer_states'] = max(self.work['max_layer_states'], max(map(len, states)))
            for (outgoing, allocation), (q, path) in states[-1].items():
                assert outgoing == self.chain.last
                results.append((allocation+budget, q, (allocation, path)))
        self.work['branch_candidates'] = len(results)
        return pareto(results)


def local_native(graph, ops, external, owned, domain, cache, ledger, entry='group'):
    """Conditional native frontier at the explicit entry; selected segments only."""
    tensors = graph.tensors(ops)
    external = frozenset(external & tensors)
    owned = frozenset(owned & {graph.output(op) for op in ops})
    key = ops, external, owned, domain, entry
    if key not in cache:
        ranks = {v for t in tensors for v in graph.dims(t)}
        sub = Graph({v: 1 if v == 'M' else graph.sizes[v] for v in ranks},
                    [(op, graph.access[op]) for op in ops])
        stats = {}
        pts = curve(sub, witness=True, entry=entry, external=external, written=owned,
                    tile_domain=domain, stats=stats, **OPTIONS)
        base = compulsory(sub, external)
        cache[key] = tuple((c, q-base, w) for c, q, w in pts)
        ledger['local_native_queries'] += 1
        for name in ('dp_transitions', 'loop_choices', 'pareto_candidates'):
            ledger[name] += stats[name]
        ledger['cache_misses'] += stats['solve_cache']['misses']+stats['group_cache']['misses']
    return cache[key]


def recover_partition(joint, point, cache, ledger):
    c, q, (allocation, path) = point
    chosen = []
    while path is not None:
        path, f, local_point = path
        chosen.append((f, local_point))
    chosen.reverse()
    graph = joint.graph
    mask = 0
    for f, _ in chosen:
        mask |= f[8]
    weights = frozenset(t for i, (t, _) in joint.weights.items() if mask >> i & 1)
    kept, dropped = set(), set()
    for f, _ in chosen:
        if f[1] < joint.n:
            (kept if f[3] else dropped).add(graph.output(graph.ops[f[1]-1]))
    groups, inner = [], []
    for f, (pc, pq) in chosen:
        ops = graph.ops[f[0]:f[1]]
        points = local_native(graph, ops, weights | kept, dropped, joint.domain, cache, ledger, entry='solve')
        match = [w for cc, qq, w in points if cc <= pc and qq == pq]
        assert match, (ops, pc, pq)
        notes = match[0]
        if notes and notes[0][0] == 'groups':
            # Local forms include full-tile cuts, so they are segment macros,
            # not necessarily one native group. Inline their first partition.
            groups.extend(notes[0][1])
            kept.update(notes[0][3])
            dropped.update(notes[0][5])
            inner.extend(notes[1:])
        else:
            groups.append(ops)
            inner.extend(notes)
    inner.insert(0, ('groups', tuple(groups), 'kept', tuple(sorted(kept)), 'via DRAM', tuple(sorted(dropped))))
    refetched = tuple(sorted(t for t, _ in joint.weights.values() if t not in weights))
    note = ('loop', graph.ops, 'M', f'tile 1 x{joint.r}', 'kept', tuple(sorted(weights)),
            'refetched', refetched)
    return c, q+compulsory(graph), (note, *inner)


def compulsory(graph, external=frozenset()):
    return sum(graph.size(t, ()) for t in (graph.consumed() ^ graph.produced()) - external)


def worker(case, mode):
    graph = graph_of(case)
    start = time.perf_counter()
    solver, registry = kernel(mode) if mode not in ('joint', 'breakpoints') else (None, {})
    setup_seconds = time.perf_counter()-start
    start = time.perf_counter()
    stats, cache = {}, {}
    joint, recovery_work = None, Counter()
    if mode == 'breakpoints':
        joint = BreakpointFactors(graph)
        extra_points = joint.frontier()
    elif mode == 'joint':
        joint = JointFactors(graph)
        extra_points = joint.frontier()
        base = compulsory(graph)
        points = [(c, q+base, (a, mask)) for c, q, a, mask in extra_points]
    else:
        points = solver(graph, entry='group', witness=True, stats=stats, **OPTIONS)
    search_seconds = time.perf_counter()-start
    if mode == 'breakpoints':
        native_points = [recover_partition(joint, point, cache, recovery_work) for point in extra_points]
    elif mode == 'joint':
        native_points = []
        ext = tuple(1 if v == 'M' else graph.sizes[v] for v in joint.names)
        for c, q, a, mask in extra_points:
            kept = frozenset(t for i, (t, _) in joint.weights.items() if mask >> i & 1)
            dropped = tuple(sorted(t for t, _ in joint.weights.values() if t not in kept))
            d = (joint.r-1)*sum(s for t, s in joint.weights.values() if t not in kept)
            assert (q-d) % joint.r == 0
            state = (graph.ops, joint.names, ext, kept, frozenset(), 'halving')
            inner = native(graph, state, c-a, (q-d)//joint.r, cache)
            note = ('loop', graph.ops, 'M', f'tile 1 x{joint.r}', 'kept', tuple(sorted(kept)),
                    'refetched', dropped)
            native_points.append((c, q+base, (note, *inner)))
    elif mode == 'forms':
        native_points = [(c, q, expand(graph, w, registry, cache)) for c, q, w in points]
    else:
        native_points = points
    seconds = time.perf_counter()-start
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    record = dict(case=case, mode=mode, setup_seconds=setup_seconds, search_seconds=search_seconds,
                  recovery_seconds=seconds-search_seconds, generation_seconds=seconds,
                  setup_and_generation_seconds=setup_seconds+seconds,
                  peak_rss_mib=rss/(2**20 if platform.system() == 'Darwin' else 2**10),
                  frontier=[list(p[:2]) for p in native_points], recovery_queries=len(cache),
                  local_group_cache=forms._group.cache_info()._asdict(),
                  whole_chain_formula_cache=frontier_of.cache_info()._asdict(),
                  native_stats=stats,
                  joint_work=dict(joint.work) if joint else None,
                  recovery_work=dict(recovery_work),
                  factor_construction_seconds=joint.factor_seconds if joint else None)
    start = time.perf_counter()
    for c, q, w in native_points:
        notes = (('groups', (graph.ops,), 'kept', (), 'via DRAM', ()), *w)
        run = simulate(graph, notes, scalar_leaf='v2')
        assert run['valid'] and (run['peak'], run['traffic']) == (c, q)
    record.update(exact_replays=len(native_points), replay_seconds=time.perf_counter()-start)
    print(json.dumps(record), flush=True)


def extract(case):
    graph = graph_of(case)
    data, nodes, children = dag.load(case)
    root = nodes[data['root']]['state']
    key = ('group', *state_key(root)[1:])
    parent = next(i for i, n in nodes.items() if state_key(n['state']) == key)
    actions = [a for a in loop_actions(graph, nodes, children, parent) if a['axis'] == 'M' and a['tile'] == 1]
    weights = sorted(t for t in graph.tensors(graph.ops) if 'M' not in graph.dims(t))
    assert len(actions) == 2**len(weights)
    records, masks = [], set()
    names = sorted(graph.sizes)
    ext = tuple(1 if v == 'M' else graph.sizes[v] for v in names)
    for a in actions:
        kept = frozenset(nodes[a['child']]['state']['external'])
        assert kept <= set(weights) and kept not in masks
        masks.add(kept)
        child = nodes[a['child']]['state']
        assert state_key(child) == ('solve', tuple(graph.ops), ext, tuple(sorted(kept)), (), False)
        unary = [(t, graph.size(t, ()), 1, int(t in kept)) for t in weights]
        allocation = sum(s*x for _, s, _, x in unary)
        extra = (graph.sizes['M']-1)*sum(s*(1-x) for _, s, _, x in unary)
        assert (allocation, extra, graph.sizes['M']) == (a['allocation'], a['extra'], a['trips'])
        assert tuple(a['actual']) == transformed(nodes[a['child']]['points'], allocation, extra, a['trips'])
        records.append(dict(parent=parent, child=a['child'], scope=graph.ops,
                            guard=dict(rank='M', tile=1, trips=a['trips']),
                            unary_weight_factors=unary, allocation=allocation, extra=extra,
                            child_state=child))
    extra_curve = frontier(p for a in actions for p in a['actual'])
    branch = [[c, q+compulsory(graph)] for c, q in extra_curve]
    full = [p[:2] for p in data['points']]
    matched = [p for p in full if traffic_at(p[0], branch) == p[1]]
    return dict(case=case, choices=len(records), factors=records, branch_frontier=branch,
                root_frontier=full, root_points_attained=matched)


def check_local(out):
    """Audit both entries: segment macros need not equal the native group curve."""
    records = []
    for case in CASES:
        graph = graph_of(case)
        for domain in ('halving', 'divisors'):
            joint = BreakpointFactors(graph, domain)
            cache, ledger = {}, Counter()
            mismatches = []
            for f in joint.factors:
                j, k, incoming, outgoing = f[:4]
                ops = graph.ops[j:k]
                external = {t for i, (t, _) in joint.weights.items() if f[8] >> i & 1}
                if incoming:
                    external.add(next(t for t in graph.access[ops[0]]
                                      if t != graph.output(ops[0]) and 'M' in graph.dims(t)))
                if outgoing:
                    external.add(graph.output(ops[-1]))
                owned = {graph.output(ops[-1])} if k < joint.n and not outgoing else set()
                native_points = local_native(graph, ops, external, owned, domain, cache, ledger)
                actual = tuple(p[:2] for p in native_points)
                if actual != f[-1]:
                    mismatches.append(dict(ops=ops, key=f[9], formula=f[-1], native=actual))
                solve_points = local_native(graph, ops, external, owned, domain, cache, ledger, entry='solve')
                for c, q in f[-1]:
                    assert traffic_at(c, solve_points) <= q, (case, domain, f[9], c, q)
            records.append(dict(case=case, domain=domain, factors_checked=len(joint.factors),
                                distinct_local_frontiers=len(joint.local_curves),
                                native_work=dict(ledger), mismatches=mismatches))
    result = dict(protocol_commit='96a752a4', source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  records=records)
    with Path(out).open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(factors_checked=sum(r['factors_checked'] for r in records), domains=2,
                         mismatches=sum(len(r['mismatches']) for r in records))))


def run(out, modes=MODES, repeats=3, protocol='b3cd183d'):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    sources = ('hypergraph_audit.py', 'LOOP_CONDITIONED_FACTORS.md', 'CONTRACTION_ORACLE.md', 'graph/curve.py',
               'response/forms.py', 'response/chains.py', 'response/substitution.py', 'simulate_nest.py')
    manifest = dict(protocol_commit=protocol, cases=CASES, modes=modes, repeats=repeats, hashseed=0,
                    worker_timeout_seconds=120, python=platform.python_version(), system=platform.system(),
                    machine=platform.machine(),
                    sources={f: hashlib.sha256((HERE/f).read_bytes()).hexdigest() for f in sources})
    if 'breakpoints' in modes:
        manifest['interface_correction_commit'] = 'de21093b'
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    refs = {c: extract(c) for c in CASES}
    (out/'factors.json').write_text(json.dumps(refs)+'\n')
    records = []
    with (out/'runs.jsonl').open('x') as stream:
        for case in CASES:
            for repeat in range(repeats):
                order = (modes if repeat % 2 == 0 else tuple(reversed(modes))) if repeats == 3 else (
                    modes[repeat % len(modes):]+modes[:repeat % len(modes)])
                for mode in order:
                    try:
                        p = subprocess.run([sys.executable, '-m', 'research.index_coupling.hypergraph_audit',
                                            'worker', case, mode], cwd=ROOT, env=dict(os.environ, PYTHONHASHSEED='0'),
                                           capture_output=True, text=True, timeout=120, check=True)
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                        text = str(error.stderr or '').replace(str(ROOT), '<repo>')
                        stream.write(json.dumps(dict(case=case, mode=mode, repeat=repeat,
                                                     status=type(error).__name__, stderr=text))+'\n')
                        stream.flush()
                        raise
                    row = dict(json.loads(p.stdout), repeat=repeat)
                    assert row['frontier'] == refs[case]['branch_frontier'], (case, mode)
                    records.append(row)
                    stream.write(json.dumps(row)+'\n')
                    stream.flush()
                    print(json.dumps({k: row[k] for k in ('case', 'mode', 'repeat', 'search_seconds',
                                                         'recovery_seconds', 'generation_seconds')}), flush=True)
    scores = []
    for case in CASES:
        medians = {}
        for mode in modes:
            rows = [r for r in records if r['case'] == case and r['mode'] == mode]
            medians[mode] = {k: statistics.median(r[k] for r in rows) for k in
                             ('setup_seconds', 'search_seconds', 'recovery_seconds', 'generation_seconds',
                              'setup_and_generation_seconds', 'peak_rss_mib')}
        scores.append(dict(case=case, medians=medians,
                           joint_vs_native=medians['native']['generation_seconds']/medians['joint']['generation_seconds'],
                           joint_vs_forms=medians['forms']['generation_seconds']/medians['joint']['generation_seconds'],
                           frontier_points=len(refs[case]['branch_frontier']),
                           root_points=len(refs[case]['root_frontier']),
                           root_points_attained=len(refs[case]['root_points_attained'])))
        if 'breakpoints' in modes:
            scores[-1]['breakpoints_vs'] = {mode: medians[mode]['generation_seconds']/
                                                   medians['breakpoints']['generation_seconds']
                                            for mode in MODES}
    (out/'summary.json').write_text(json.dumps(scores, indent=2)+'\n')


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        worker(*sys.argv[2:])
    elif sys.argv[1] == 'check-local':
        check_local(sys.argv[2])
    elif sys.argv[1] == 'run-breakpoints':
        run(sys.argv[2], MODES+('breakpoints',), 5, '96a752a4')
    else:
        assert sys.argv[1] == 'run'
        run(sys.argv[2])
