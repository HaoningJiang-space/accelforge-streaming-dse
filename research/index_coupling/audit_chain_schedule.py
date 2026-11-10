"""Independent zero-extra, cell-schedule oracle for bounded chain checks.

All dependency-legal scalar step orders are searched, not loop grammar plans.
No eviction of a still-needed value is permitted. First-use input loads and
last-use/final-write releases minimize capacity for each fixed order; resident
weights are pinned in a charged outer frame for the independent replay.
"""
import argparse
from collections import defaultdict
from functools import lru_cache
import gzip
import hashlib
from itertools import product
import json
from pathlib import Path
from time import monotonic

from .check_chain_threshold import chain_bound
from .graph.curve import curve
from .graph.model import Graph
from .graph.stacks import ffn_stack
from .simulate_nest import Machine, Specification

HERE = Path(__file__).parent


def zero_schedule(graph, resident, state_budget=200000, seconds=30):
    spec = Specification(graph)
    resident = set(resident)
    if not resident <= spec.inputs:
        raise ValueError('oracle accepts only resident inputs')
    steps = [(op, iteration) for op in spec.ops for iteration in spec.iterations(op, spec.bounds)]
    accesses = [spec.accesses(*step) for step in steps]
    produces, consumes = defaultdict(int), defaultdict(int)
    for i, cells in enumerate(accesses):
        produces[cells[-1]] |= 1 << i
        for cell in cells[:-1]:
            consumes[cell] |= 1 << i
    all_cells = set(produces) | set(consumes)
    full = (1 << len(steps))-1
    choices = {}
    start = monotonic()
    visited = 0

    @lru_cache(None)
    def solve(done):
        nonlocal visited
        visited += 1
        if visited > state_budget or monotonic()-start > seconds:
            raise TimeoutError('bounded schedule audit exceeded its budget')
        if done == full:
            return 0
        live = set()
        for cell in all_cells:
            if cell[0] in resident:
                continue
            p, c = produces[cell], consumes[cell]
            if p:
                if p & done and ((p & done) != p or c & ~done):
                    live.add(cell)
            elif c & done and c & ~done:
                live.add(cell)
        best = float('inf')
        for i, cells in enumerate(accesses):
            if done & (1 << i):
                continue
            if any(produces[c] & done != produces[c] for c in cells[:-1]):
                continue
            peak = len(live | {c for c in cells if c[0] not in resident})
            candidate = max(peak, solve(done | (1 << i)))
            if candidate < best:
                best, choices[done] = candidate, i
        assert best < float('inf')
        return best

    capacity = solve(0)
    schedule, done = [], 0
    while done != full:
        i = choices[done]
        schedule.append(steps[i])
        done |= 1 << i
    # Replay the selected non-grammar order with the independent existing machine.
    machine = Machine(spec)
    pinned = spec.cells(resident, spec.bounds)
    machine.allocate(pinned)
    for cell in sorted(pinned):
        machine.load(cell)
    for op, iteration in schedule:
        cells = set(spec.accesses(op, iteration))
        machine.allocate(cells-machine.buffer)
        machine.step(op, iteration)
        dead = {c for c in machine.buffer-pinned if machine.future_reads[c] == 0
                and machine.done[c] == machine.required[c]}
        machine.release(dead)
    machine.release(pinned)
    replay = machine.finish()
    compulsory = sum(len(spec.cells({t}, spec.bounds)) for t in spec.inputs | spec.outputs)
    assert replay['peak'] == len(pinned)+capacity and replay['traffic'] == compulsory
    assert not replay['partial_reads'] and not replay['partial_writes']
    return dict(capacity=capacity, states=visited, schedule=schedule, replay=replay,
                pinned_cells=len(pinned), compulsory_with_frame=compulsory)


def state_of(graph, resident):
    return dict(ops=graph.ops, ext=tuple(graph.sizes[v] for v in sorted(graph.sizes)),
                external=sorted(resident), owned=(), constrained=False, stage='solve')


def compulsory(graph, resident):
    return sum(graph.size(t, set()) for t in (graph.consumed() ^ graph.produced())-set(resident))


def run():
    results = []
    for layers in (1, 2):
        graph = ffn_stack(layers, m=1)
        weights = sorted(t for t in graph.tensors(graph.ops) if t.startswith('W'))
        for bits in product((False, True), repeat=len(weights)):
            resident = {w for w, bit in zip(weights, bits) if bit}
            answer = zero_schedule(graph, resident)
            lower = chain_bound(graph, state_of(graph, resident))
            points = curve(graph, external=resident, partitions='dp', scalar_leaf='v2')
            zero = next(c for c, q in points if q == compulsory(graph, resident))
            assert lower <= answer['capacity'] <= zero
            results.append(dict(layers=layers, resident=sorted(resident), bound=lower,
                                grammar_zero=zero, **answer))
    # Confirm the reported larger-shape construction in a real parent frame.
    from .test_streamed_bridge import framed_streamed_witness
    graph = ffn_stack(1, m=1, d=4, f=8)
    resident = {'W1_0', 'W2_0'}
    c, q, witness = curve(graph, external=resident, partitions='dp', scalar_leaf='v2', witness=True)[-1]
    assert q == compulsory(graph, resident)
    from .simulate_nest import simulate
    framed, notes, peak, traffic = framed_streamed_witness(graph, resident, ((c, 0, witness),))
    replay = simulate(framed, notes, scalar_leaf='v2')
    assert (replay['peak'], replay['traffic']) == (peak, traffic)
    # A deliberate out-of-domain incidence example: multiplication is diagonal,
    # so counting rank-free operands alone does not recognize a dense contraction.
    diagonal = Graph({'M':1,'I':2}, [('E', {'X':('M','I'), 'W':('I',), 'Y':('M','I')})])
    wrong_bound = chain_bound(diagonal, state_of(diagonal, set()))
    actual = curve(diagonal, scalar_leaf='v2')[-1]
    assert wrong_bound > actual[0] and actual[1] == compulsory(diagonal, set())
    archived = []
    for layers in (1,2,3,4):
        path = HERE/f'results/c2_bound/ffn_forward_l{layers}/analysis.json'
        report = json.loads(path.read_text())
        family = next(f for f in report['top_families'] if f['axis'] == 'M' and f['tile'] == 1)
        baseline_path = path.parent/'baseline.json.gz'
        with gzip.open(baseline_path,'rt') as stream:
            nodes = {n['id']:n for n in json.load(stream)['nodes']}
        boundary = {'W1_0',f'W2_{layers-1}'}
        for action in family['actions']:
            missing = set(action['lacking'])-set(action['keep'])
            predicted = 4+bool(missing-boundary)
            assert nodes[action['child']]['points'][-1] == [predicted,0]
        archived.append(dict(layers=layers, subsets=len(family['actions']),
            raw_sha256=hashlib.sha256(baseline_path.read_bytes()).hexdigest(), all_equal=True))
    sources = ('audit_chain_schedule.py','check_chain_threshold.py','graph/curve.py',
               'graph/model.py','graph/stacks.py','simulate_nest.py',
               'test_streamed_bridge.py','test_scalar_bridge.py')
    return dict(scope='Retrospective independent bounded audit, not a frozen prediction.',
        source_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in sources},
        schedule_cases=results, archived_binary_cases=archived,
        rectangular=dict(shape=dict(M=1,D=4,F=8), resident=sorted(resident),
            grammar_zero=c, whole_intermediate_count=16, witness=witness, replay=replay,
            framed_witness=notes, expected_frame_peak=peak, expected_frame_traffic=traffic),
        guard_counterexample=dict(graph_sizes=diagonal.sizes, graph_access=diagonal.access,
            unchecked_chain_bound=wrong_bound, actual=actual,
            note='Outside the documented dense-chain domain; archived eligible cases remain valid.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = run()
    with args.out.open('x') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps(dict(schedule_cases=len(result['schedule_cases']),
        replayed=len(result['schedule_cases'])+1,
        bounds_valid=all(r['bound']<=r['capacity'] for r in result['schedule_cases']),
        schedule_equals_grammar=sum(r['capacity']==r['grammar_zero'] for r in result['schedule_cases']),
        rectangular_zero=result['rectangular']['grammar_zero'],
        guard_counterexample=result['guard_counterexample'])))


if __name__ == '__main__':
    main()
