"""Upper-bound check: does interconnect topology matter for layer-pipelined DNN graphs?

Ops of L stacked blocks are placed in topological order onto N cores in contiguous,
FLOP-balanced stages (weights and KV stationary). Every activation tensor travels
from its producer's core to each distinct consumer core. Report the busiest-link
bytes on a 1D ring (shortest direction), a 2D mesh (snake placement, XY routing),
and the per-core injection/ejection bound of an ideal crossbar.
"""
import math, sys
from collections import defaultdict


def block(prefix, M, D, A, T, F, moe=0, topk=2):
    # (name, inputs{tensor: bytes-shape}, output, flops)
    ops = []
    x = f'{prefix}x'
    def op(n, ins, out, fl): ops.append((prefix + n, ins, out, fl))
    op('q', [x], 'q', 2*M*D*A); op('k', [x], 'k', 2*M*D*A); op('v', [x], 'v', 2*M*D*A)
    op('s', ['q', 'k'], 's', 2*M*T*A); op('o', ['s', 'v'], 'o', 2*M*T*A)
    op('wo', ['o'], 'y', 2*M*A*D); op('r1', [x, 'y'], 'r1', M*D)
    if moe:
        op('route', ['r1'], 'route', 2*M*D*moe)
        for e in range(moe):
            m = M*topk/moe
            op(f'g{e}', ['r1', 'route'], f'g{e}', 2*m*D*F); op(f'u{e}', ['r1'], f'u{e}', 2*m*D*F)
            op(f'd{e}', [f'g{e}', f'u{e}'], f'y{e}', 2*m*F*D)
        op('sum', [f'y{e}' for e in range(moe)] + ['r1'], 'out', M*D*moe)
    else:
        op('g', ['r1'], 'g', 2*M*D*F); op('u', ['r1'], 'u', 2*M*D*F)
        op('d', ['g', 'u'], 'y2', 2*M*F*D); op('r2', ['r1', 'y2'], 'out', M*D)
    # tensor sizes (elements), prefixed names
    size = dict(q=M*A, k=M*A, v=M*A, s=M*T, o=M*A, y=M*D, r1=M*D, g=M*F, u=M*F, y2=M*D,
                out=M*D, route=M*moe)
    if moe:
        for e in range(moe):
            size[f'g{e}'] = size[f'u{e}'] = M*topk/moe*F; size[f'y{e}'] = M*topk/moe*D
    out_ops = [(n, [t if t == x else prefix + t for t in ins], prefix + o, fl) for n, ins, o, fl in ops]
    sizes = {prefix + k: v for k, v in size.items()}
    return out_ops, sizes, prefix + 'out'


def model(L, **kw):
    ops, sizes, prev = [], {}, None
    for l in range(L):
        o, s, out = block(f'L{l}', **kw)
        if prev:
            o = [(n, [prev if t == f'L{l}x' else t for t in ins], out_t, fl) for n, ins, out_t, fl in o]
        ops += o; sizes.update(s); prev = out
    return ops, sizes


def stages(ops, N):
    total = sum(op[3] for op in ops); where, acc = {}, 0
    for n, _, _, fl in ops:
        where[n] = min(N - 1, int(acc / total * N)); acc += fl
    return where


def loads(ops, sizes, where, N, topo):
    prod = {o: where[n] for n, _, o, _ in ops}
    flows = defaultdict(float)
    for n, ins, _, _ in ops:
        for t in ins:
            if t in prod and prod[t] != where[n]:
                flows[(t, where[n])] = sizes[t]
    link = defaultdict(float)
    for (t, dst), b in flows.items():
        src = prod[t]
        if topo == 'xbar':
            link[('out', src)] += b; link[('in', dst)] += b
        elif topo == 'ring':
            d = (dst - src) % N; step = 1 if d <= N - d else -1; c = src
            while c != dst:
                link[(c, (c + step) % N)] += b; c = (c + step) % N
        elif topo == 'chain':
            step = 1 if dst > src else -1; c = src
            while c != dst:
                link[(c, c + step)] += b; c += step
        else:  # mesh, snake order, XY routing
            w = int(math.isqrt(N))
            pos = lambda i: (i // w, i % w if (i // w) % 2 == 0 else w - 1 - i % w)
            (r, c), (r2, c2) = pos(src), pos(dst)
            while c != c2:
                n2 = c + (1 if c2 > c else -1); link[((r, c), (r, n2))] += b; c = n2
            while r != r2:
                n2 = r + (1 if r2 > r else -1); link[((r, c), (n2, c))] += b; r = n2
    return max(link.values()) if link else 0, sum(flows.values())


if __name__ == '__main__':
    llama = dict(D=4096, A=4096, F=11008)
    cases = [('decode M=1 T=4k', dict(M=1, T=4096, **llama)),
             ('prefill M=2k', dict(M=2048, T=2048, **llama)),
             ('MoE8 prefill M=2k', dict(M=2048, T=2048, D=4096, A=4096, F=14336, moe=8))]
    for name, kw in cases:
        ops, sizes = model(4, **kw)
        for N in (16, 64):
            where = stages(ops, N)
            res = {t: loads(ops, sizes, where, N, t)[0] for t in ('xbar', 'ring', 'chain', 'mesh')}
            vol = loads(ops, sizes, where, N, 'xbar')[1]
            print(f'{name:20s} N={N:3d} ops={len(ops)} vol={vol:.3g} '
                  + ' '.join(f'{t}={v/res["xbar"]:.2f}x' for t, v in res.items()))
