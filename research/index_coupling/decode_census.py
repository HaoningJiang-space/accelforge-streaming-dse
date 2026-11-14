"""Census: how much exact-search work in inference graphs falls under proven simplifications.

Builds single-layer inference graphs (Llama-style decoder block, MoE FFN) in the
index-coupling IR, records the unpruned v2 call DAG with BaselineRecorder, and
reports the exclusive work removed when unit-M chain states are answered by the
closed forms (CONTRACTION_ORACLE.md §15), at M = 1 (decode) and M > 1 (prefill).
"""
import argparse
import gzip
import json
from pathlib import Path
import resource
import signal
import subprocess
import sys
from time import perf_counter

from research.index_coupling.c2_bound_audit import COUNTERS, BaselineRecorder
from research.index_coupling.graph.model import Graph
from research.index_coupling.response import dag
from research.index_coupling.response.chains import archived


def decoder_block(m, d=2, a=2, t=2, f=2, kv_write=True, residual=True, swiglu=True):
    """One decoder layer. KV cache Kc/Vc over T is external, like a weight.

    Ranks: M rows (tokens), D model, A head, T cached sequence, F hidden.
    """
    ops = [('EQ', {'X0': ('M', 'D'), 'Wq': ('D', 'A'), 'Q': ('M', 'A')})]
    if kv_write:
        ops += [('EK', {'X0': ('M', 'D'), 'Wk': ('D', 'A'), 'Kn': ('M', 'A')}),
                ('EV', {'X0': ('M', 'D'), 'Wv': ('D', 'A'), 'Vn': ('M', 'A')})]
    ops += [('ES', {'Q': ('M', 'A'), 'Kc': ('T', 'A'), 'S': ('M', 'T')}),
            ('ESoft', {'S': ('M', 'T'), 'P': ('M', 'T')}),
            ('EO', {'P': ('M', 'T'), 'Vc': ('T', 'A'), 'O': ('M', 'A')}),
            ('EWo', {'O': ('M', 'A'), 'Wo': ('A', 'D'), 'Y': ('M', 'D')})]
    x = 'Y'
    if residual:
        ops.append(('ER1', {'X0': ('M', 'D'), 'Y': ('M', 'D'), 'R1': ('M', 'D')}))
        x = 'R1'
    if swiglu:
        ops += [('EG', {x: ('M', 'D'), 'Wg': ('D', 'F'), 'G': ('M', 'F')}),
                ('EU', {x: ('M', 'D'), 'Wu': ('D', 'F'), 'U': ('M', 'F')}),
                ('EZ', {'G': ('M', 'F'), 'U': ('M', 'F'), 'Z': ('M', 'F')})]
    else:
        ops += [('EG', {x: ('M', 'D'), 'Wg': ('D', 'F'), 'G': ('M', 'F')}),
                ('EZ', {'G': ('M', 'F'), 'Z': ('M', 'F')})]
    ops.append(('ED', {'Z': ('M', 'F'), 'Wd': ('F', 'D'), 'Y2': ('M', 'D')}))
    if residual:
        ops.append(('ER2', {x: ('M', 'D'), 'Y2': ('M', 'D'), 'X1': ('M', 'D')}))
    return Graph(dict(M=m, D=d, A=a, T=t, F=f), ops)


def moe(m, experts, d=2, f=2):
    """Routed MoE FFN with `experts` active experts sharing input X; outputs summed."""
    ops = []
    for e in range(experts):
        ops += [(f'EH{e}', {'X': ('M', 'D'), f'W1_{e}': ('D', 'F'), f'H{e}': ('M', 'F')}),
                (f'EZ{e}', {f'H{e}': ('M', 'F'), f'Z{e}': ('M', 'F')}),
                (f'EY{e}', {f'Z{e}': ('M', 'F'), f'W2_{e}': ('F', 'D'), f'Y{e}': ('M', 'D')})]
    ops.append(('ESum', {**{f'Y{e}': ('M', 'D') for e in range(experts)}, 'Out': ('M', 'D')}))
    return Graph(dict(M=m, D=d, F=f), ops)


CASES = {
    **{f'attn_chain_m{m}': (lambda m: decoder_block(m, kv_write=False, residual=False, swiglu=False), m)
       for m in (1, 2, 4)},
    **{f'block_plain_m{m}': (lambda m: decoder_block(m, kv_write=False, swiglu=False), m) for m in (1, 2, 4)},
    **{f'block_full_m{m}': (decoder_block, m) for m in (1, 2, 4)},
    **{f'moe{e}_m{m}': (lambda m, e=e: moe(m, e), m) for e in (2, 4) for m in (1, 2, 4)},
}


def summarise(case, graph, baseline):
    nodes = {i: n for i, n in enumerate(baseline['nodes'])}
    children = {}
    for e in baseline['edges']:
        children.setdefault(e['parent'], []).append(e['child'])
    unit = {i for i, n in nodes.items() if archived(graph, n['state'], unit_rows=True) is not None}
    chain = {i for i, n in nodes.items() if archived(graph, n['state']) is not None}
    total = {k: sum(n['work'][k] for n in nodes.values()) for k in COUNTERS}
    share = lambda ids: {k: round(sum(nodes[i]['work'][k] for i in ids) / total[k], 4) if total[k] else None
                         for k in COUNTERS}
    data = dict(root=baseline['root'])
    return dict(case=case, ops=len(graph.ops), states=len(nodes), unit_terminals=len(unit),
                total_work=total,
                removed_by_unit_closed_form=dag.terminal_work(data, nodes, children, unit),
                exclusive_share_chain_states=share(chain),
                exclusive_share_unit_chain_states=share(unit))


def worker(case, out, seconds, gib):
    resource.setrlimit(resource.RLIMIT_AS, (gib * 2**30, gib * 2**30))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError(f'{seconds}s budget')))
    signal.alarm(seconds)
    builder, m = CASES[case]
    graph = builder(m)
    start = perf_counter()
    record = dict(case=case, sizes=graph.sizes, operators=[(o, graph.access[o]) for o in graph.ops])
    try:
        baseline = BaselineRecorder().run(graph)
        record['baseline_seconds'] = round(perf_counter() - start, 3)
        record.update(summarise(case, graph, baseline), status='complete')
        with gzip.open(out / f'{case}.baseline.json.gz', 'wt') as stream:
            json.dump(baseline, stream, separators=(',', ':'))
    except (TimeoutError, MemoryError) as exc:
        record.update(status=type(exc).__name__, error=str(exc))
    finally:
        signal.alarm(0)
        record['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    (out / f'{case}.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({k: record.get(k) for k in ('case', 'status', 'states', 'baseline_seconds',
                                                  'removed_by_unit_closed_form')}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('out', type=Path)
    p.add_argument('cases', nargs='*', default=list(CASES))
    p.add_argument('--seconds', type=int, default=1800)
    p.add_argument('--gib', type=int, default=8)
    p.add_argument('--single', action='store_true', help='run one case in this process')
    args = p.parse_args()
    if sys.platform != 'linux':
        raise SystemExit('run on the Linux server with caps')
    args.out.mkdir(parents=True, exist_ok=True)
    if args.single:
        return worker(args.cases[0], args.out, args.seconds, args.gib)
    # One process per case: memo caches and the address-space cap do not leak across cases.
    for case in args.cases:
        if not (args.out / f'{case}.json').exists():
            subprocess.run([sys.executable, '-m', __spec__.name, str(args.out), case, '--single',
                            '--seconds', str(args.seconds), '--gib', str(args.gib)], check=False)


if __name__ == '__main__':
    main()
