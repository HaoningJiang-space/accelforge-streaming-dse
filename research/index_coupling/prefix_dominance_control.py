"""Constructive post-hoc control: incomparable longer prefixes really occur.

python -m research.index_coupling.prefix_dominance_control --out NEW.json
This control was constructed after the frozen one/two-loop census.
"""
import argparse
import json
from pathlib import Path

from .graph.curve import curve
from .graph.model import Graph
from .simulate_nest import simulate


def run():
    graph = Graph(dict(M=4, D=1, F=4), [
        ('E', {'X': ('M', 'D'), 'W': ('D', 'F'), 'Y': ('M', 'F')})])
    group = ('groups', (('E',),), 'kept', (), 'via DRAM', ())
    early = (group, ('loop', ('E',), 'M', 'tile 1 x4', 'kept', ('W',), 'refetched', ()),
             group, ('loop', ('E',), 'F', 'tile 1 x4', 'kept', ('X',), 'refetched', ()))
    late = (group, ('loop', ('E',), 'M', 'tile 2 x2', 'kept', (), 'refetched', ('W',)),
            group, ('loop', ('E',), 'F', 'tile 1 x4', 'kept', ('X',), 'refetched', ()),
            group, ('loop', ('E',), 'M', 'tile 1 x2', 'kept', ('W',), 'refetched', ()))
    baseline = curve(graph, partitions='dp', scalar_leaf='v2')
    records = []
    for name, witness, label, expected in (
            ('retain_W_early', early, (5, 0, 16), (6, 24)),
            ('retain_W_late', late, (3, 4, 16), (4, 28))):
        replay = simulate(graph, witness, scalar_leaf='v2')
        assert replay['valid'] and (replay['peak'], replay['traffic']) == expected
        assert expected in baseline, 'both plans must be root Pareto points'
        records.append(dict(name=name, prefix_label=label, witness=witness,
                            peak=replay['peak'], total_traffic=replay['traffic'], valid=True))
    return dict(scope='Post-hoc constructive control, not a held-out prediction',
                grammar='v2', tile_domain='halving', shape=dict(M=4, D=1, F=4),
                common_start=dict(stage='group', ops=['E'], ext=dict(M=4, D=1, F=4), external=[], owned=[]),
                common_end=dict(stage='solve', ops=['E'], ext=dict(M=1, D=1, F=1), external=['W', 'X'], owned=[]),
                suffix_capacity=1, suffix_extra_traffic=0, compulsory_traffic=24,
                root_frontier=baseline, plans=records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = run()
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(frontier=result['root_frontier'], verified_plans=len(result['plans']))))
