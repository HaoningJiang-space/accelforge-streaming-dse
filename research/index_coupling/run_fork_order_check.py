"""Order-complete, single-shape follow-up; keeps logical tensor identities.

The shape was selected because the archived P18 orders disagree. It is a
diagnostic control, not a held-out prediction. No reference grammar is modified.
"""
from itertools import combinations
import json
from pathlib import Path
import resource
import subprocess
from time import perf_counter

from .analyze_p18_profile import read_curves
from .curve_model import curve, pareto
from .nest_model import Graph, fork
from .simulate_nest import simulate


SHAPE = (16, 4, 16, 4)
BASE_ROLES = 'kki'


def reordered(graph, original_roles, desired_roles):
    """Permute independent consumers, without renaming their data or operators."""
    assert sorted(original_roles) == sorted(desired_roles)
    available = {r:[op for op,x in zip(graph.ops[1:],original_roles) if x==r]
                 for r in ('k','i')}
    order = [graph.ops[0]] + [available[r].pop(0) for r in desired_roles]
    return Graph(dict(graph.sizes), [(op,dict(graph.access[op])) for op in order])


def main():
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 125))
    path = Path(__file__).parent/'results/p18.jsonl'
    archived, digest = read_curves(path)
    print(json.dumps(dict(kind='metadata',
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        tracked_dirty=bool(subprocess.check_output(['git','diff','--name-only','HEAD'],text=True)),
        input_sha256=digest,shape=SHAPE,roles=BASE_ROLES,
        purpose='known order-sensitive case; order-complete control, not held out')),flush=True)
    base = fork(*SHAPE, BASE_ROLES)
    graphs, all_points, frontiers = {}, [], {}
    for positions in combinations(range(len(BASE_ROLES)), BASE_ROLES.count('i')):
        roles = ''.join('i' if j in positions else 'k' for j in range(len(BASE_ROLES)))
        graph = graphs[roles] = reordered(base,BASE_ROLES,roles)
        started = perf_counter()
        points = curve(graph,witness=True)
        frontiers[roles] = [[c,q] for c,q,_ in points]
        if (SHAPE,roles) in archived:
            assert frontiers[roles] == archived[(SHAPE,roles)]
        all_points.extend((c,q,roles,w) for c,q,w in points)
        print(json.dumps(dict(kind='order',roles=roles,ops=graph.ops,
            points=frontiers[roles],seconds=perf_counter()-started,
            archived_match=(SHAPE,roles) in archived)),flush=True)
    envelope = pareto(all_points)
    for c,q,roles,witness in envelope:
        actual = simulate(graphs[roles],witness)
        assert actual['peak'] == c and actual['traffic'] == q
        print(json.dumps(dict(kind='execution',capacity=c,traffic=q,roles=roles,
                              actual=actual)),flush=True)

    def at(points,c):
        return min(q for cap,q in points if cap<=c)

    points = [[c,q] for c,q,*_ in envelope]
    improvements = {}
    for roles, old in frontiers.items():
        caps = sorted({c for p in (points,old) for c,_ in p})
        improvements[roles] = [[c,at(old,c),at(points,c)] for c in caps if at(points,c)<at(old,c)]
    print(json.dumps(dict(kind='summary',frontier=points,
        order_count=len(frontiers),executed_points=len(envelope),
        improvements=improvements,
        relative_to_pure=[
            [c,at(archived[(SHAPE,'kkk')],c),q] for c,q in points],
        new_mapping_search=True, search_acceleration_claim=False)),flush=True)


if __name__ == '__main__':
    main()
