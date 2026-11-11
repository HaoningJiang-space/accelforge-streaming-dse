"""Read-only root-wide work attribution; no search, pruning or solver changes.

python -m research.index_coupling.response.root_work NEW_DIRECTORY
Families are descriptive buckets, never cache keys or equivalence claims.
Free-terminal experiments measure old work removed, not achievable speedups.
"""
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from research.index_coupling.c2_bound_audit import COUNTERS, state_key
from research.index_coupling.census_tools import graph_of
from research.index_coupling.response import dag
from research.index_coupling.response.chains import recognise
from research.index_coupling.response.keep_level import curve_of
from research.index_coupling.graph.curve import curve

CASES = ('ffn_forward_l1_m8', 'ffn_forward_l2_m8', 'ffn_forward_l4', 'ffn_training_l1')


def contraction(g, s, names):
    """Canonical three-rank singleton, for the existing keep-level response."""
    if s['constrained'] or len(s['ops']) != 1:
        return None
    op = s['ops'][0]
    y = g.output(op)
    inputs = sorted(set(g.access[op]) - {y})
    if len(inputs) != 2:
        return None
    x, w = inputs
    dx, dw, dy = (set(g.dims(t)) for t in (x, w, y))
    m, d, f = dx & dy, dx & dw, dw & dy
    if not (len(m) == len(d) == len(f) == 1 and len(m | d | f) == 3
            and dx == m | d and dw == d | f and dy == m | f):
        return None
    ext = dict(zip(names, s['ext']))
    live = tuple(k for k, t in (('X', x), ('W', w), ('Y', y)) if t not in s['external'])
    return tuple(ext[next(iter(r))] for r in (m, d, f)), tuple(sorted(live))


def features(g, s, names):
    ch = recognise(g, tuple(s['ops']), tuple(s['ext']), frozenset(s['external']),
                   frozenset(s['owned']), names)
    one = contraction(g, s, names)
    unit = (s['stage'] == 'solve' and not s['constrained'] and ch is not None
            and ch.rows == 1 and 'c' in ch.kinds)
    # Unit-M chain formulas are solve-only. Local macros are not native groups.
    family = (s['stage'], len(s['ops']), s['ext'][names.index('M')] if 'M' in names else None,
              'private_chain' if ch is not None else 'other')
    return family, unit, one


def source(parent, child, names):
    p, c = parent['state'], child['state']
    if p['stage'] == 'group' and c['stage'] == 'solve':
        assert p['ops'] == c['ops']
        changed = [i for i, (x, y) in enumerate(zip(p['ext'], c['ext'])) if x != y]
        if not changed:
            return 'scalar_group_to_solve'
        assert len(changed) == 1
        i = changed[0]
        assert p['ext'][i] > c['ext'][i]
        return f"loop:{names[i]}:{p['ext'][i]}->{c['ext'][i]}"
    if p['stage'] == 'solve' and c['stage'] == 'group':
        return 'partition:whole_span' if p['ops'] == c['ops'] else 'partition:proper_span'
    raise AssertionError((p, c))


def analyze(case):
    g = graph_of(case)
    names = tuple(sorted(g.sizes))
    data, nodes, children = dag.load(case)
    assert data['grammar'] == 'v2' and dag.reach(data['root'], children) == set(nodes)
    assert len({state_key(n['state']) for n in nodes.values()}) == len(nodes)
    totals = {k: sum(n['work'][k] for n in nodes.values()) for k in COUNTERS}
    assert all(totals[k] == data['stats'][k] for k in COUNTERS)
    families, node_family, unit, single = defaultdict(set), {}, set(), set()
    single_keys, unit_keys = set(), set()
    for i, n in nodes.items():
        f, is_unit, one = features(g, n['state'], names)
        families[f].add(i)
        node_family[i] = f
        if is_unit:
            unit.add(i)
            ch = recognise(g, tuple(n['state']['ops']), tuple(n['state']['ext']),
                           frozenset(n['state']['external']), frozenset(n['state']['owned']), names)
            unit_keys.add((ch.kinds, ch.sizes, ch.first, ch.last, ch.streamed))
        if one is not None:
            single.add(i)
            single_keys.add(one)

    incoming, sources, calls = defaultdict(set), defaultdict(Counter), defaultdict(Counter)
    for e in data['edges']:
        p, c = e['parent'], e['child']
        label = source(nodes[p], nodes[c], names)
        incoming[c].add(p)
        sources[c][label] += 1
        calls[c][label] += e['calls']
    assert sum(sum(c.values()) for c in sources.values()) == len(data['edges'])

    def work(ids):
        return {k: sum(nodes[i]['work'][k] for i in ids) for k in COUNTERS}

    def fraction(w):
        return {k: w[k]/totals[k] if totals[k] else 0 for k in COUNTERS}

    def replacement(terminals):
        reached = dag.reach(data['root'], children, terminal=terminals)
        expanded = reached-terminals
        removed = set(nodes)-expanded
        return dict(guard_states=len(terminals), reached_replacements=len(reached & terminals),
                    original_states_still_expanded=len(expanded),
                    replaced_own_work=work(reached & terminals),
                    unreachable_descendant_work=work(set(nodes)-reached),
                    removed_work=work(removed), removed_fraction=fraction(work(removed)))

    portfolios = {'unit_chain_solve': unit, 'single_contraction_both_entries': single,
                  'union': unit | single}
    covered = {name: replacement(ids) for name, ids in portfolios.items()}
    residual = dag.reach(data['root'], children, terminal=unit)-unit
    residual_work = work(residual)

    rows = []
    for family, ids in sorted(families.items(), key=str):
        incoming_sources, incoming_calls = Counter(), Counter()
        for i in ids:
            incoming_sources.update(sources[i]); incoming_calls.update(calls[i])
        own, rest = work(ids), work(ids & residual)
        rows.append(dict(family=family, states=len(ids), own_work=own,
                         own_fraction=fraction(own), work_after_free_unit=rest,
                         share_of_residual={k: rest[k]/residual_work[k] if residual_work[k] else 0 for k in COUNTERS},
                         unit_guard=len(ids & unit), single_guard=len(ids & single),
                         multiple_parent_states=sum(len(incoming[i]) > 1 for i in ids),
                         max_parents=max(len(incoming[i]) for i in ids),
                         parent_count_histogram=dict(Counter(len(incoming[i]) for i in ids)),
                         source_edges=dict(incoming_sources), source_calls=dict(incoming_calls)))

    # Only the top three families per residual counter get zero-cost thought experiments.
    # Selection is retrospective prioritization, not a certified replacement rule.
    selected = {tuple(r['family']) for k in COUNTERS for r in
                sorted(rows, key=lambda r: r['work_after_free_unit'][k], reverse=True)[:3]
                if r['work_after_free_unit'][k]}
    for row in rows:
        f = tuple(row['family'])
        if f in selected:
            ideal = replacement(unit | families[f])
            ideal['incremental_removed_work_after_unit'] = {
                k: ideal['removed_work'][k]-covered['unit_chain_solve']['removed_work'][k] for k in COUNTERS}
            ideal['incremental_fraction_of_original'] = fraction(ideal['incremental_removed_work_after_unit'])
            row['hypothetical_free_family_after_unit'] = ideal

    top = sorted({i for k in COUNTERS for i in sorted(residual, key=lambda i: nodes[i]['work'][k], reverse=True)[:10]})
    top_nodes = [dict(id=i, state=nodes[i]['state'], family=node_family[i], work=nodes[i]['work'],
                      frontier=nodes[i]['points'], parents=sorted(incoming[i]),
                      source_edges=dict(sources[i]), source_calls=dict(calls[i])) for i in top]
    path = dag.ARCHIVE/case/'baseline.json.gz'
    return dict(case=case, grammar='v2', archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                state_count=len(nodes), edge_count=len(data['edges']), totals=totals,
                families=rows, provider_portfolios=covered,
                distinct_provider_keys=dict(unit= len(unit_keys), single=len(single_keys)),
                residual_work_after_free_unit=residual_work, top_residual_states=top_nodes,
                ledger_scope='exclusive counters only; replacement construction and witnesses are not free in an implementation',
                new_constructor_cost=None, new_witness_cost=None)


def run(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve()
    files = (here, here.with_name('dag.py'), here.with_name('chains.py'),
             here.parent.parent/'c2_bound_audit.py')
    manifest = dict(cases=CASES, source_sha256={str(p.relative_to(here.parent.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                    kind='retrospective archive attribution, not a frozen prediction or performance benchmark')
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    for case in CASES:
        result = analyze(case)
        (out/f'{case}.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(dict(case=case, states=result['state_count'],
                              covered={k:v['removed_fraction'] for k,v in result['provider_portfolios'].items()})), flush=True)


def provider(case, out):
    """Fresh-process diagnostic of an existing response constructor, no replacement."""
    g = graph_of(case)
    names = tuple(sorted(g.sizes))
    data, nodes, children = dag.load(case)
    unit, singleton, keys = set(), set(), {}
    for i, n in nodes.items():
        _, is_unit, one = features(g, n['state'], names)
        if is_unit:
            unit.add(i)
        if one is not None:
            singleton.add(i); keys[i] = one
    reached = dag.reach(data['root'], children, terminal=unit | singleton)
    requested = sorted({keys[i] for i in (reached & singleton)-unit})
    reference = defaultdict(list)
    for i, key in keys.items():
        reference[key].append(i)
    with Path(out).open('x') as f:
        def emit(row):
            f.write(json.dumps(row)+'\n'); f.flush()
        emit(dict(kind='scope', case=case, requested_keys=len(requested),
                  reached_single_states=len((reached & singleton)-unit),
                  witness_cost=None, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
        start = time.perf_counter()
        points = curve(g, witness=True, partitions='dp', scalar_leaf='v2')
        seconds = time.perf_counter()-start
        assert [list(p[:2]) for p in points] == data['points']
        emit(dict(kind='native_root', generation_seconds=seconds, points=len(points),
                  note='one diagnostic run, not a speedup benchmark; witness emitted but not replayed here'))
        total, verified = 0., 0
        for key in requested:
            emit(dict(kind='start_key', key=key))
            start = time.perf_counter()
            pts = curve_of(*key, 'halving')
            elapsed = time.perf_counter()-start
            total += elapsed
            for i in reference[key]:
                assert [list(p[:2]) for p in pts] == nodes[i]['points'], (case, key, i)
                verified += 1
            emit(dict(kind='finished_key', key=key, seconds=elapsed,
                      matched_states=len(reference[key]), frontier_points=len(pts)))
        emit(dict(kind='complete', response_seconds=total, verified_states=verified,
                  requested_keys=len(requested), witness_cost=None))


def providers(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    results = []
    for case in CASES:
        path = out/f'{case}.jsonl'
        try:
            p = subprocess.run([sys.executable, '-m', __spec__.name, 'provider', case, str(path)],
                               env=dict(os.environ, PYTHONHASHSEED='0'), capture_output=True, text=True,
                               timeout=30)
            assert p.returncode == 0, p.stderr
            status = 'complete'
        except subprocess.TimeoutExpired:
            status = 'timeout_30s'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        done = [r for r in rows if r['kind'] == 'finished_key']
        root = next((r for r in rows if r['kind'] == 'native_root'), None)
        result = dict(case=case, status=status, requested_keys=rows[0]['requested_keys'],
                      completed_keys=len(done), completed_response_seconds=sum(r['seconds'] for r in done),
                      native_root_seconds=root['generation_seconds'] if root else None,
                      verified_states=sum(r['matched_states'] for r in done), witness_cost=None)
        results.append(result)
        print(json.dumps(result), flush=True)
    (out/'summary.json').write_text(json.dumps(results, indent=2)+'\n')


if __name__ == '__main__':
    if sys.argv[1] == 'provider':
        provider(*sys.argv[2:])
    elif sys.argv[1] == 'providers':
        providers(sys.argv[2])
    else:
        run(sys.argv[1])
