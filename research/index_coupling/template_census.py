"""Do exact frontiers use a size-independent set of plan templates?

For each graph family and growing extents, the exact v2 frontier is computed
with witnesses. A witness is abstracted to a template by keeping its structure
(fusion groups, kept / via-DRAM / refetched tensors, loop axes and order) and
replacing every tile size by its class: 1 (scalar), or free. If the number of
distinct templates stops growing with extent, a shape-parametric closed form
(one cost expression per template) is plausible; if it keeps growing, it is not.
"""
import argparse
import json
from pathlib import Path
import resource
import signal
import subprocess
import sys
from time import perf_counter

from research.index_coupling.decode_census import decoder_block
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph
from research.index_coupling.graph.stacks import attention_stack, ffn_stack

OPTIONS = dict(partitions='dp', scalar_leaf='v2', tile_domain='halving')


def matmul(s):
    return Graph(dict(I=s, J=s, K=s), [('E', {'A': ('I', 'J'), 'B': ('J', 'K'), 'C': ('I', 'K')})])


FAMILIES = {
    'matmul': matmul,
    'ffn1': lambda s: ffn_stack(1, m=s, d=s, f=s),
    'attn1': lambda s: attention_stack(1, m=s, p=s, d=s),
    'ffn2': lambda s: ffn_stack(2, m=s, d=s, f=s),
    # LLM-like: only the token count grows, model dims fixed.
    'ffn1_m': lambda s: ffn_stack(1, m=s, d=4, f=8),
    'block_m': lambda s: decoder_block(s, kv_write=False, swiglu=False),
}


def template(witness):
    """Size-free structure of a witness.

    The grammar tiles by recursive halving, so one loop with a free tile size
    appears as several nested same-axis notes. Transparent single-group notes
    are dropped, and a same-axis note that adds no retention and refetches the
    same tensors is merged into the level above it (as loop_normal_form.py).
    """
    out = []
    for note in witness:
        if note[0] == 'groups' and len(note[1]) == 1 and not note[3] and not note[5]:
            continue
        if note[0] == 'loop':
            _, ops, axis, _, _, kept, _, refetched = note
            level = ('loop', tuple(ops), axis, tuple(kept), tuple(refetched))
            prev = out[-1] if out else None
            if (not kept and prev and prev[0] == 'loop' and prev[1:3] == level[1:3]
                    and prev[4] == level[4]):
                continue
            out.append(level)
        else:
            out.append(tuple(tuple(x) if isinstance(x, list) else x for x in note))
    return tuple(out)


def worker(family, s, out, seconds, gib):
    resource.setrlimit(resource.RLIMIT_AS, (gib * 2**30, gib * 2**30))
    def timeout(*_):
        raise TimeoutError(f'{seconds}s budget')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(seconds)
    graph = FAMILIES[family](s)
    record = dict(family=family, extent=s, sizes=graph.sizes)
    start = perf_counter()
    try:
        points = curve(graph, witness=True, **OPTIONS)
        templates = [template(w) for _, _, w in points]
        record.update(status='complete', seconds=round(perf_counter() - start, 3), points=len(points),
                      templates=len(set(templates)),
                      frontier=[[c, q, templates.index(t)] for (c, q, _), t in zip(points, templates)],
                      template_list=[list(map(list, t)) for t in dict.fromkeys(templates)])
    except (TimeoutError, MemoryError) as exc:
        record.update(status=type(exc).__name__, seconds=round(perf_counter() - start, 3))
    finally:
        signal.alarm(0)
    record['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    (out / f'{family}_s{s}.json').write_text(json.dumps(record) + '\n')
    print(json.dumps({k: record.get(k) for k in ('family', 'extent', 'status', 'seconds', 'points', 'templates')}),
          flush=True)
    return record['status'] == 'complete'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('out', type=Path)
    p.add_argument('families', nargs='*', default=list(FAMILIES))
    p.add_argument('--extents', type=int, nargs='+', default=[2, 4, 8, 16, 32, 64])
    p.add_argument('--seconds', type=int, default=900)
    p.add_argument('--gib', type=int, default=8)
    p.add_argument('--single', nargs=2, metavar=('FAMILY', 'EXTENT'))
    args = p.parse_args()
    if sys.platform != 'linux':
        raise SystemExit('run on the Linux server with caps')
    args.out.mkdir(parents=True, exist_ok=True)
    if args.single:
        return worker(args.single[0], int(args.single[1]), args.out, args.seconds, args.gib)
    for family in args.families:
        for s in args.extents:
            path = args.out / f'{family}_s{s}.json'
            if not path.exists():
                subprocess.run([sys.executable, '-m', __spec__.name, str(args.out), '--single', family, str(s),
                                '--seconds', str(args.seconds), '--gib', str(args.gib)], check=False)
            if not path.exists() or json.loads(path.read_text())['status'] != 'complete':
                break  # larger extents of this family will not finish either


if __name__ == '__main__':
    main()
