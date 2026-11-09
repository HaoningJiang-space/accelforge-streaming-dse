"""Replay the unmaterialized shared-input FFN control with per-residency audits.

Bounded diagnostic for archived P14-FFN' gaps, not a new search mechanism.
Run on the experiment server. The cell executor is unchanged; an audit records
which operators reuse each graph-input cell during the same resident episode.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter

from research.index_coupling.graph import curve as curve_module
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.model import ffn
from research.index_coupling.graph.references import ffn_case
from research.index_coupling.graph.views import ffm_like_part
from research.index_coupling import simulate_nest as oracle


class InputEpisodeAudit(oracle.Machine):
    def __init__(self, spec):
        super().__init__(spec)
        self.current_op = None
        self.episodes = defaultdict(set)
        self.episode_histogram = defaultdict(Counter)

    def step(self, op, iteration):
        self.current_op = op
        super().step(op, iteration)

    def load(self, cell, accumulator=False):
        value = super().load(cell, accumulator)
        if not accumulator and cell[0] in self.spec.inputs:
            self.episodes[cell].add(self.current_op)
        return value

    def release(self, cells):
        for cell in cells:
            if cell in self.episodes:
                users = tuple(sorted(self.episodes.pop(cell)))
                self.episode_histogram[cell[0]][users] += 1
        super().release(cells)

    def finish(self):
        result = super().finish()
        oracle.require(not self.episodes, 'unclosed input residency episode')
        result['input_residency_episodes'] = {
            tensor: [{'users': list(users), 'cell_episodes': count}
                     for users, count in sorted(hist.items())]
            for tensor, hist in sorted(self.episode_histogram.items())}
        # Each graph-input residency episode starts with exactly one DRAM read.
        oracle.require(all(sum(hist.values()) == self.reads[tensor]
                           for tensor, hist in self.episode_histogram.items()),
                       'episode counts disagree with executed input reads')
        return result


class SeparateInputConsumers(oracle.Machine):
    """Keep reservations/schedule fixed; reload selected inputs per consumer.

    A read-only value may be discarded while its reservation stays allocated.
    This is an executable traffic ablation, not a model of FFM's entire grammar.
    """
    def __init__(self, spec, selected):
        super().__init__(spec)
        self.selected = set(selected)
        oracle.require(self.selected <= spec.inputs, 'only graph inputs may be separated')
        self.used_by = defaultdict(set)
        self.current_op = None

    def step(self, op, iteration):
        self.current_op = op
        super().step(op, iteration)

    def load(self, cell, accumulator=False):
        if not accumulator and cell[0] in self.selected:
            if self.used_by[cell] and self.current_op not in self.used_by[cell]:
                self.values.pop(cell, None)
            self.used_by[cell].add(self.current_op)
        return super().load(cell, accumulator)

    def release(self, cells):
        super().release(cells)
        for cell in cells:
            self.used_by.pop(cell, None)


def counterfactual(path):
    records = [json.loads(line) for line in Path(path).read_text().splitlines()]
    plan = next(row for row in records if row.get('capacity_budget') == 80)
    graph = ffn(8, 4, 8)
    spec = oracle.Specification(graph)
    def tuples(value):
        return tuple(tuples(x) for x in value) if isinstance(value, list) else value
    root = oracle.parse_witness(spec, tuples(plan['witness']))
    for selected in ((), ('X',), ('dY',), ('X', 'dY'), ('W1', 'W2', 'X', 'dY')):
        machine = SeparateInputConsumers(spec, selected)
        for kind, payload in oracle.events(spec, root):
            if kind == 'step':
                machine.step(*payload)
            else:
                getattr(machine, kind)(payload)
        result = machine.finish()
        oracle.require(result['peak'] == plan['model_peak'], 'changed reservation peak')
        print(json.dumps({'kind': 'fixed_witness_input_separation',
                          'source_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                          'separated_inputs': selected, 'execution': result,
                          'scope': 'Post-hoc traffic ablation; same schedule and allocation, not native FFM.'}),
              flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capacities', nargs='+', type=int, default=[80, 147, 148])
    parser.add_argument('--counterfactual', help='saved model replay JSONL; no curve regeneration')
    args = parser.parse_args()
    if args.counterfactual:
        counterfactual(args.counterfactual)
        return
    graph = ffn(8, 4, 8)
    start = perf_counter()
    points = ffm_like_part(graph, (), separate_inputs=False, witness=True,
                           max_capacity=max(args.capacities))
    build_seconds = perf_counter() - start
    archive_path = Path(__file__).parent / 'results/ffn_parts/ffm_like_shared_inputs.jsonl'
    archived = next(json.loads(line)['points'] for line in archive_path.read_text().splitlines()
                    if json.loads(line)['part'] == 'ffm_like_si:')
    _, _, reference = ffn_case()
    metadata = {
        'kind': 'metadata', 'part': 'ffm_like_si:', 'shape': [8, 4, 8],
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'source_sha256': {Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                          for m in (curve_module, oracle)},
        'archive_sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        'build_seconds': build_seconds,
        'scope': 'Empty materialization subset; simplified FFN arithmetic and alias semantics.',
    }
    print(json.dumps(metadata), flush=True)
    for capacity in args.capacities:
        peak, traffic, witness = min((p for p in points if p[0] <= capacity), key=lambda p: p[1])
        oracle.require(traffic == traffic_at(capacity, archived), 'archived traffic mismatch')
        spec = oracle.Specification(graph)
        root = oracle.parse_witness(spec, witness)
        machine = InputEpisodeAudit(spec)
        for kind, payload in oracle.events(spec, root):
            if kind == 'step':
                machine.step(*payload)
            else:
                getattr(machine, kind)(payload)
        executed = machine.finish()
        oracle.require((executed['peak'], executed['traffic']) == (peak, traffic),
                       'executed result differs from model')
        print(json.dumps({'kind': 'execution', 'capacity_budget': capacity,
                          'model_peak': peak, 'model_traffic': traffic,
                          'ffm_archived_traffic': traffic_at(capacity, reference),
                          'witness': witness, 'execution': executed}), flush=True)


if __name__ == '__main__':
    main()
