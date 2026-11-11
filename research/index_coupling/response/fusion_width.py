"""Offline top-level group-span audit; see ../FUSION_WIDTH_AUDIT.md.

python -m research.index_coupling.response.fusion_width NEW.jsonl
No native solver is called for archived chain states. Their group responses
are read with the full projected interface. Native search is used only for
the separately declared six-op semantic control.
"""
from collections import defaultdict
from functools import lru_cache
import gzip
import hashlib
import json
from math import prod
from pathlib import Path
import sys
import time

from research.index_coupling.c2_bound_audit import COUNTERS, frontier, state_key
from research.index_coupling.census_tools import graph_of
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph
from research.index_coupling.graph.stacks import ffn_stack
from research.index_coupling.response import bounds, dag
from research.index_coupling.response.chains import archived
from research.index_coupling.response.substitution import OPTIONS
from research.index_coupling.simulate_nest import simulate

CASES = ('ffn_forward_l1_m8', 'ffn_forward_l2_m8', 'ffn_forward_l4')
HERE = Path(__file__).resolve().parent.parent


class ArchiveComposition:
    def __init__(self, graph, nodes):
        self.graph, self.nodes = graph, nodes
        self.names = tuple(sorted(graph.sizes))
        self.row_axes = frozenset.intersection(*(frozenset(graph.dims(t)) for t in graph.produced()))
        self.by_key = {state_key(n['state']): i for i, n in nodes.items()}
        self.queries = defaultdict(set)

    @lru_cache(maxsize=None)
    def projection(self, ops):
        tensors = self.graph.tensors(ops)
        used = set().union(*(set(self.graph.dims(t)) for t in tensors))
        made = {self.graph.output(op) for op in ops}
        return tensors, used, made

    def group(self, parent, ops, external, owned, k):
        tensors, used, made = self.projection(ops)
        ext = tuple(e if v in used else 1 for v, e in zip(self.names, parent['ext']))
        external, owned = frozenset(external) & tensors, frozenset(owned) & made
        sizes = dict(zip(self.names, ext))
        live = tensors - external
        scalar = all(prod(sizes[v] for v in self.graph.dims(t)) == 1 for t in live)
        # Native scalar leaf, or the whole-span v2 hold alternative. No group
        # cache entry is generated for these direct responses.
        if scalar and (len(ops) == 1 or ops == tuple(parent['ops'])):
            return ((len(live), 0),)
        key = ('group', ops, ext, tuple(sorted(external)), tuple(sorted(owned)), False)
        ident = self.by_key[key]  # missing interface is an error, never a fallback
        self.queries[k].add(ident)
        return tuple(map(tuple, self.nodes[ident]['points']))

    def response(self, node, chain, k):
        s = node['state']
        ops, n = tuple(s['ops']), len(s['ops'])
        vectors = [next(t for t in self.graph.access[ops[0]]
                        if t != self.graph.output(ops[0]) and self.row_axes <= set(self.graph.dims(t)))]
        vectors.extend(self.graph.output(op) for op in ops)
        sizes = [chain.rows * x for x in chain.sizes]
        states = [dict() for _ in range(n + 1)]
        states[0][chain.first] = ((0, 0),)
        for i in range(n):
            for incoming, prefix in states[i].items():
                for j in range(i + 1, min(n, i + k) + 1):
                    for outgoing in ((chain.last,) if j == n else (False, True)):
                        kept, dropped = set(), set()
                        for p, keep in ((i, incoming), (j, outgoing)):
                            if 0 < p < n:
                                (kept if keep else dropped).add(vectors[p])
                        reservation = sum(sizes[p] for p, keep in ((i, incoming), (j, outgoing))
                                          if keep and 0 < p < n)
                        local = self.group(s, ops[i:j], set(s['external']) | kept,
                                           set(s['owned']) | dropped, k)
                        spill = 2 * sizes[j] if j < n and not outgoing else 0
                        merged = ((max(a, reservation + b), x + y + spill)
                                  for a, x in prefix for b, y in local)
                        states[j][outgoing] = frontier((*states[j].get(outgoing, ()), *merged))
        return states[n].get(chain.last, ())


def union_dependencies(roots, children):
    seen, stack = set(), list(roots)
    while stack:
        i = stack.pop()
        if i not in seen:
            seen.add(i)
            stack.extend(children.get(i, ()))
    return seen


def audit(case, details):
    start = time.perf_counter()
    data, nodes, children = dag.load(case)
    load_seconds = time.perf_counter() - start
    graph = graph_of(case)
    chains = {i: ch for i, n in nodes.items() if (ch := archived(graph, n['state'])) is not None}
    multi = {i: ch for i, ch in chains.items() if ch.rows > 1}
    unit = {i for i, ch in chains.items() if ch.rows == 1}
    engine = ArchiveComposition(graph, nodes)
    equal = {k: set() for k in (1, 2, 3)}
    evaluated = {}
    start = time.perf_counter()
    for i, ch in multi.items():
        node, n = nodes[i], len(nodes[i]['state']['ops'])
        actual = tuple(map(tuple, node['points']))
        responses = {k: engine.response(node, ch, k) for k in sorted({1, 2, 3, n})}
        assert responses[n] == actual, (case, i, 'unrestricted reconstruction')
        caps = sorted({c for pts in (*responses.values(), actual) for c, _ in pts})
        for c in caps:
            values = [traffic_at(c, responses[k]) for k in (1, 2, 3)] + [traffic_at(c, actual)]
            assert all(a >= b for a, b in zip(values, values[1:])), (case, i, c, values)
            assert values[0] == bounds.upper(ch, c), (case, i, c, 'singleton cross-check')
        for k in equal:
            if responses[k] == actual:
                equal[k].add(i)
        evaluated[i] = responses
        details.write(json.dumps(dict(case=case, id=i, ops=node['state']['ops'], rows=ch.rows,
                                      actual=actual, restricted={k: responses[k] for k in (1, 2, 3)},
                                      local_work=node['work'])) + '\n')
    construction_seconds = time.perf_counter() - start
    unit_work = dag.terminal_work(data, nodes, children, unit)
    total = {k: sum(n['work'][k] for n in nodes.values()) for k in COUNTERS}
    result = dict(case=case, load_seconds=load_seconds, composition_and_check_seconds=construction_seconds,
                  qualifying_multi_row=len(multi), baseline_total_work=total, unit_only=unit_work,
                  unrestricted_reconstruction_equal=len(multi), levels=[])
    for k, matched in equal.items():
        long = {i for i in multi if len(nodes[i]['state']['ops']) > k}
        queried = engine.queries[k]
        contexts = defaultdict(set)
        for i in queried:
            s = nodes[i]['state']
            contexts[(tuple(s['ops']), tuple(s['ext']), tuple(s['owned']))].add(tuple(s['external']))
        deps = union_dependencies(queried, children)
        union = dag.terminal_work(data, nodes, children, unit | matched)
        local = {counter: sum(nodes[i]['work'][counter] for i in matched) for counter in COUNTERS}
        local_long = {counter: sum(nodes[i]['work'][counter] for i in long & matched) for counter in COUNTERS}
        local_long_total = {counter: sum(nodes[i]['work'][counter] for i in long) for counter in COUNTERS}
        level = dict(k=k, equal=len(matched), nontrivial_states=len(long), nontrivial_equal=len(long & matched),
                     equal_exclusive_work=local, nontrivial_equal_exclusive_work=local_long,
                     nontrivial_total_exclusive_work=local_long_total,
                     free_terminal_only=dag.terminal_work(data, nodes, children, matched),
                     free_terminal_union_unit=union,
                     added_dp_percentage_points=round(100*(union['dp_transitions']-unit_work['dp_transitions']), 2),
                     group_interfaces=len(queried), group_context_free_keys=len(contexts),
                     max_contexts_per_group_key=max(map(len, contexts.values()), default=0),
                     group_dependency_states=len(deps),
                     group_dependency_work={c: sum(nodes[i]['work'][c] for i in deps) for c in COUNTERS})
        if data['root'] in multi:
            level['root_equal'] = data['root'] in matched
            level['root_extra_curve'] = evaluated[data['root']][k]
        failures = long - matched
        if failures:
            i = max(failures, key=lambda i: nodes[i]['work']['dp_transitions'])
            caps = {c for pts in (evaluated[i][k], nodes[i]['points']) for c, _ in pts}
            cap = min(c for c in caps if traffic_at(c, evaluated[i][k]) > traffic_at(c, nodes[i]['points']))
            restricted = traffic_at(cap, evaluated[i][k])
            level['largest_local_dp_failure'] = dict(id=i, state=nodes[i]['state'], work=nodes[i]['work'],
                                                     capacity=cap, actual=traffic_at(cap, nodes[i]['points']),
                                                     restricted='infeasible' if restricted == float('inf') else restricted)
        result['levels'].append(level)
    return result


def control():
    graph = ffn_stack(2, m=8, d=1, f=1)
    external = frozenset(t for op in graph.ops for t in graph.access[op] if 'M' not in graph.dims(t))
    # A real caller loop pins the weights and executes the conditional child
    # twice. Every activation gets a fresh FRAME rank; weights lack it.
    framed = Graph(dict(graph.sizes, FRAME=2),
                   [(op, {t: ('FRAME', *ds) if 'M' in ds else ds for t, ds in graph.access[op].items()})
                    for op in graph.ops])
    baseline = curve(graph, external=external, witness=True, **OPTIONS)
    candidates = {k: [] for k in (1, 2, 3, 6)}
    for mask in range(1 << (len(graph.ops) - 1)):
        cuts = [0] + [i for i in range(1, len(graph.ops)) if mask >> (i-1) & 1] + [len(graph.ops)]
        groups = tuple(graph.ops[a:b] for a, b in zip(cuts, cuts[1:]))
        points = curve(graph, external=external, root_groups=groups, witness=True, **OPTIONS)
        for k in candidates:
            if max(map(len, groups)) <= k:
                candidates[k].extend(points)
    curves, replays = {}, 0
    for k, points in candidates.items():
        curves[k] = frontier(p[:2] for p in points)
        for c, q in curves[k]:
            witness = next(w for pc, pq, w in points if (pc, pq) == (c, q))
            notes = (('groups', (graph.ops,), 'kept', (), 'via DRAM', ()),
                     ('loop', graph.ops, 'FRAME', 'tile 1 x2', 'kept', tuple(sorted(external)), 'refetched', ()),
                     *witness)
            run = simulate(framed, notes, scalar_leaf='v2')
            reservation = sum(graph.size(t, ()) for t in external)
            assert run['valid'] and (run['peak'], run['traffic']) == (reservation+c, reservation+2*q)
            replays += 1
    assert curves[6] == frontier(p[:2] for p in baseline)
    at_two = {k: traffic_at(2, pts) for k, pts in curves.items()}
    assert at_two == {1: 96, 2: 48, 3: 32, 6: 16}, at_two
    return dict(case='constructed_control', curves=curves, total_traffic_at_capacity_2=at_two,
                exact_replays=replays)


def main(out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x') as stream, gzip.open(out.with_suffix('.states.jsonl.gz'), 'xt') as details:
        # Record immutable inputs and this exact offline composition source.
        sources = ('FUSION_WIDTH_AUDIT.md', 'response/fusion_width.py', 'response/bounds.py',
                   'response/chains.py', 'graph/curve.py', 'graph/model.py', 'graph/stacks.py', 'simulate_nest.py')
        manifest = dict(protocol_commit='8245fcd6',
                        source_sha256={f: hashlib.sha256((HERE/f).read_bytes()).hexdigest() for f in sources},
                        archive_sha256={c: hashlib.sha256((dag.ARCHIVE/c/'baseline.json.gz').read_bytes()).hexdigest()
                                        for c in CASES})
        stream.write(json.dumps(dict(manifest=manifest)) + '\n')
        for case in CASES:
            record = audit(case, details)
            stream.write(json.dumps(record) + '\n')
            stream.flush()
            print(json.dumps(dict(case=case, states=record['qualifying_multi_row'],
                                  levels=[{k: r[k] for k in ('k', 'equal', 'nontrivial_states',
                                                           'nontrivial_equal', 'added_dp_percentage_points')}
                                          for r in record['levels']])), flush=True)
        record = control()
        stream.write(json.dumps(record) + '\n')
        print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
