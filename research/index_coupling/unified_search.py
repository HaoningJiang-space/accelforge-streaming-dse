"""Three certified reductions of ONE serial order-complete grammar.

The inner recurrence is the unchanged curve.py, optionally using its cut DP
and an in-memory, guarded scalar-separator certificate. The outer quotient
uses certified whole-graph automorphisms and decorated-order stabilizers.
This is a bounded reference architecture, not a scalable general-DAG solver.
"""
import ast
from collections import Counter, defaultdict
from dataclasses import asdict
from functools import wraps
import hashlib
from itertools import permutations, product
import json
from math import prod
from pathlib import Path
from time import perf_counter

from .graph.branch_symmetry import Renaming, is_automorphism, topological_orders
from .graph.curve import curve, pareto
from .graph.fork_quotient import Plan, renamed, reordered
from .graph.model import Graph


def mixed_branch_graph(shape=(2, 2, 2, 2)):
    if len(shape) != 4 or any(type(n) is not int or n < 1 for n in shape):
        raise ValueError('four positive integer extents required')
    ops = [('EX', {'A': ('I', 'J'), 'B': ('J', 'K'), 'X': ('I', 'K')})]
    for i in range(3):
        ops.append((f'E{i}', {'X': ('I', 'K'), f'C{i}': ('K', 'L'), f'U{i}': ('I', 'L')}))
    ops.extend([
        ('F', {'U0': ('I', 'L'), 'D0': ('L',), 'V0': ('I', 'L')}),
        ('Join', {'V0': ('I', 'L'), 'U1': ('I', 'L'), 'U2': ('I', 'L'), 'Y': ('I', 'L')}),
    ])
    return Graph(dict(zip(('I', 'J', 'K', 'L'), shape)), ops)


def validate_graph(graph):
    if len(set(graph.ops)) != len(graph.ops) or len(graph.produced()) != len(graph.ops):
        raise ValueError('distinct operators and single tensor writers required')
    if any(type(n) is not int or n < 1 for n in graph.sizes.values()):
        raise ValueError('positive integer extents required')
    for op in graph.ops:
        for t, ds in graph.access[op].items():
            if (tuple(ds) != tuple(graph.dims(t)) or len(ds) != len(set(ds))
                    or not set(ds) <= set(graph.sizes)):
                raise ValueError('one consistent rank projection per tensor required')
    next(topological_orders(graph))  # Reject cycles; do not enumerate orders here.


def identity(graph):
    return Renaming({o: o for o in graph.ops}, {t: t for t in graph.tensors(graph.ops)})


def certified_automorphisms(graph):
    """Small-graph exhaustive detection; never infer symmetry from byte counts.

Map operators within input/output projection classes. Their outputs determine
the produced-tensor map; enumerate graph-input maps within projection classes.
The full incidence checker validates every candidate. No rank renaming.
"""
    op_classes, input_classes = defaultdict(list), defaultdict(list)
    for o in graph.ops:
        out = graph.output(o)
        key = (tuple(graph.dims(out)), tuple(sorted(tuple(ds) for t, ds in
               graph.access[o].items() if t != out)))
        op_classes[key].append(o)
    for t in sorted(graph.consumed() - graph.produced()):
        input_classes[tuple(graph.dims(t))].append(t)
    oc, ic = list(op_classes.values()), list(input_classes.values())
    groups, tested = [], 0
    for op_targets in product(*(permutations(c) for c in oc)):
        om = {a: b for c, target in zip(oc, op_targets) for a, b in zip(c, target)}
        made = {graph.output(o): graph.output(om[o]) for o in graph.ops}
        for input_targets in product(*(permutations(c) for c in ic)):
            tm = dict(made)
            tm.update({a: b for c, target in zip(ic, input_targets) for a, b in zip(c, target)})
            mapping = Renaming(om, tm)
            tested += 1
            if is_automorphism(graph, mapping):
                groups.append(mapping)
    return tuple(groups), tested


def scalar_separator_certificate(graph, ops, ext, external, owned, names):
    """Prove (operand-slot lower bound, zero INTERNAL extra traffic), or decline.

Caller establishes a legal ordered, unconstrained solve in the exact default
single-writer grammar. External allocations and compulsory/final boundary
transfers remain caller-owned. Does not replace the mandatory scalar leaf.
"""
    if len(ops) < 2:
        return None
    sizes = dict(zip(names, ext))
    resident = set(external)
    used = [set(graph.access[o]) for o in ops]
    live = set.union(*used) - resident
    size = lambda t: prod(sizes[v] for v in graph.dims(t))
    if all(size(t) == 1 for t in live):
        return None
    occurrences = {t: [i for i, ts in enumerate(used) if t in ts] for t in live}
    shared = {t for t, positions in occurrences.items() if len(positions) > 1}
    if not shared or any(size(t) != 1 for t in shared):
        return None
    slots = [len(ts - resident) for ts in used]
    peaks, streams = [], []
    for i, ts in enumerate(used):
        private = ts - resident - shared
        active = sorted({v for t in private for v in graph.dims(t) if sizes[v] > 1})
        if any(v not in graph.dims(t) for v in active for t in private):
            return None
        reservation = sum(min(occurrences[t]) <= i <= max(occurrences[t]) for t in shared)
        peaks.append(reservation + len(private))
        streams.append(active)
    lower = max(slots)
    if max(peaks) != lower:
        return None
    notes = [('groups', tuple((o,) for o in ops), 'kept', tuple(sorted(shared)), 'via DRAM', ())]
    for op, axes in zip(ops, streams):
        for j, axis in enumerate(axes):
            if j:
                notes.append(('groups', ((op,),), 'kept', (), 'via DRAM', ()))
            notes.append(('loop', (op,), axis, f'tile 1 x{sizes[axis]}', 'kept', (), 'refetched', ()))
    return dict(capacity=lower, extra_traffic=0, shared=tuple(sorted(shared)),
                operand_slots=slots, singleton_peaks=peaks, streams=streams, notes=tuple(notes))


def state_record(stage, ops, ext, external, owned, constrained=False):
    return dict(stage=stage, ops=tuple(ops), ext=tuple(ext), external=tuple(sorted(external)),
                owned=tuple(sorted(owned)), constrained=constrained)


def state_key(state):
    return json.dumps(state, sort_keys=True, separators=(',', ':'))


def make_kernel(*, certificate=False, observer=None, events=None):
    """Adapt in memory; retain the source scalar leaf and every other recurrence.

Observers run once per response-cache miss. Certificate tags annotate witness
provenance only and are stripped before any executor receives a plan.
"""
    if not certificate and observer is None:
        return curve
    path = Path(__file__).parent / 'graph/curve.py'
    tree = ast.parse(path.read_text(), filename=str(path))
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
    solver = next(n for n in ast.walk(outer) if isinstance(n, ast.FunctionDef) and n.name == '_solve')
    stack = []

    def observe(stage):
        def decorate(fn):
            if observer is None and not certificate:
                return fn
            @wraps(fn)
            def call(ops, ext, external, owned, *args):
                state = state_record(stage, ops, ext, external, owned, args[0] if args else False)
                stack.append(state)
                try:
                    result = fn(ops, ext, external, owned, *args)
                    if observer is not None and stage != 'cut_dp':
                        observer(state, tuple((c, q) for c, q, _ in result))
                    return result
                finally:
                    stack.pop()
            return call
        return decorate

    def response(graph, ops, ext, external, owned, names, witness, max_capacity, stats):
        start = perf_counter()
        cert = scalar_separator_certificate(graph, ops, ext, external, owned, names)
        if stats is not None:
            stats['certificate_checks'] = stats.get('certificate_checks', 0) + 1
            stats['certificate_seconds'] = stats.get('certificate_seconds', 0.) + perf_counter() - start
        if cert is None:
            return None
        if stats is not None:
            stats['certificate_hits'] = stats.get('certificate_hits', 0) + 1
        state = state_record('solve', ops, ext, external, owned)
        key = hashlib.sha256(state_key(state).encode()).hexdigest()[:24]
        if events is not None:
            events[key] = dict(state=state, certificate=cert, ancestors=list(stack[:-1]))
        if cert['capacity'] > max_capacity:
            return ()
        notes = (('__certificate__', key),) + cert['notes'] if witness else ()
        return ((cert['capacity'], 0, notes),)

    if certificate:
        outer.body[1:1] = ast.parse('''
_certificate_enabled = (grid is None and spill_cost == 2 and write_through
    and split_shared and not legacy_nested_writes and not canonical_spans
    and not independent_ops)
''').body
        leaf = ast.dump(ast.parse('not constrained and all(size(t, ext) == 1 for t in live)', mode='eval').body)
        positions = [i for i, n in enumerate(solver.body) if isinstance(n, ast.If) and ast.dump(n.test) == leaf]
        if len(positions) != 1:
            raise ValueError('source scalar-leaf rule changed')
        hook = ast.parse('''
if _certificate_enabled and not constrained and (allowed_mask is None or ops != graph.ops):
    _cert = _response(graph, ops, ext, external, owned, names, witness, max_capacity, stats)
    if _cert is not None:
        return _cert
''').body
        solver.body[positions[0] + 1:positions[0] + 1] = hook
    for fn in [n for n in ast.walk(outer) if isinstance(n, ast.FunctionDef)]:
        stage = {'_solve': 'solve', '_group_curve': 'group', 'cut_dp': 'cut_dp'}.get(fn.name)
        if stage:
            fn.decorator_list.append(ast.Call(ast.Name('_observe', ast.Load()), [ast.Constant(stage)], []))
    namespace = dict(__name__='research.index_coupling.graph._unified_experiment',
                     __package__='research.index_coupling.graph', _response=response, _observe=observe)
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), namespace)
    return namespace['curve']


class UnifiedSearch:
    """All global topological orders; independent D/Q/C switches.

D=cut DP, Q=certified state/order quotient, C=scalar-separator certificate.
Each query uses the same conditional boundary and retains a single global
order. Canonical state and order detection are intentionally exhaustive here.
"""
    def __init__(self, graph, switches='111', *, observer=None, profile=True):
        if len(switches) != 3 or set(switches) - {'0', '1'}:
            raise ValueError('switches are three bits D,Q,C')
        validate_graph(graph)
        self.graph, self.switches = graph, switches
        self.observer, self.profile = observer, profile
        begin = perf_counter()
        self.group, tested = certified_automorphisms(graph) if switches[1] == '1' else ((identity(graph),), 0)
        self.stats = dict(automorphisms=len(self.group), automorphism_candidates=tested,
                          symmetry_setup_seconds=perf_counter() - begin, queries=0, cache_hits=0,
                          order_candidates=0, order_calls=0, order_skips=0, symmetry_query_seconds=0.)
        self.cache, self.proofs = {}, {}

    def canonical(self, external, owned, entry):
        images = [((tuple(sorted(p.tensors[t] for t in external)),
                    tuple(sorted(p.tensors[t] for t in owned)), entry), p) for p in self.group]
        return min(images, key=lambda x: x[0])

    def query(self, *, external=(), owned=(), entry='solve'):
        graph = self.graph
        if not set(external) <= graph.tensors(graph.ops) or not set(owned) <= graph.produced():
            raise ValueError('unknown external tensor or write owner')
        if entry not in ('solve', 'group'):
            raise ValueError('unknown entry')
        self.stats['queries'] += 1
        start = perf_counter()
        key, mapping = self.canonical(external, owned, entry)
        resident, written, entry = key
        stable = [p for p in self.group if {p.tensors[t] for t in resident} == set(resident)
                  and {p.tensors[t] for t in written} == set(written)]
        self.stats['symmetry_query_seconds'] += perf_counter() - start
        if key in self.cache:
            self.stats['cache_hits'] += 1
        else:
            candidates, seen = [], set()
            for order in topological_orders(graph):
                self.stats['order_candidates'] += 1
                begin = perf_counter()
                orbit = min(tuple(p.ops[o] for o in order) for p in stable)
                self.stats['symmetry_query_seconds'] += perf_counter() - begin
                if orbit in seen:
                    self.stats['order_skips'] += 1
                    continue
                seen.add(orbit)
                def observe(state, points):
                    if self.observer is not None:
                        self.observer(order, state, points)
                events = {}
                kernel = make_kernel(certificate=self.switches[2] == '1',
                                     observer=observe if self.observer is not None else None, events=events)
                stats = {} if self.profile else None
                result = kernel(reordered(graph, order), partitions='dp' if self.switches[0] == '1' else 'enumerate',
                                witness=True, external=resident, written=written, entry=entry, stats=stats)
                self.stats['order_calls'] += 1
                if stats is not None:
                    for field in ('partition_masks', 'partition_choices', 'dp_states', 'dp_transitions',
                                  'loop_choices', 'pareto_candidates', 'certificate_checks',
                                  'certificate_hits', 'certificate_seconds'):
                        self.stats[field] = self.stats.get(field, 0) + stats.get(field, 0)
                    for field in ('solve', 'group'):
                        self.stats[field + '_entries'] = self.stats.get(field + '_entries', 0) + stats[field + '_cache']['currsize']
                for cid, event in events.items():
                    self.proofs[order, cid] = event
                for c, q, notes in result:
                    ids = tuple(note[1] for note in notes if note[0] == '__certificate__')
                    clean = tuple(note for note in notes if note[0] != '__certificate__')
                    candidates.append((c, q, (Plan(order, clean), ids)))
            self.cache[key] = pareto(candidates)
        ro, rt = ({v: k for k, v in mapping.ops.items()}, {v: k for k, v in mapping.tensors.items()})
        return tuple((c, q, renamed(plan, ro, rt), dict(order=plan.order, certificates=ids,
                     restore_ops=ro, restore_tensors=rt)) for c, q, (plan, ids) in self.cache[key])


def serializable_point(point):
    c, q, plan, provenance = point
    return dict(capacity=c, traffic=q, plan=asdict(plan), provenance=provenance)
