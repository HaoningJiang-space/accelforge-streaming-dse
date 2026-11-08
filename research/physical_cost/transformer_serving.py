"""Addressed pre-LN GQA Transformer block, with cold backing and KV append.

All tensors are FP32. Arithmetic uses an explicitly assumed eight INT8-MAC
equivalents per FP32 operation; this is an analytical machine, not an ISA
calibration. The block is bias-free, uses affine LayerNorm and tanh GELU.
"""

from dataclasses import dataclass
from itertools import product
from math import ceil

from research.physical_cost.serving_trace import Access, Program
from research.runtime.strip_codesign import ceildiv


FP = 8


@dataclass(frozen=True)
class Workload:
    rows: int
    contexts: tuple[int, ...]
    steps: int
    arrivals_ps: tuple[int, ...]
    width: int = 64
    heads: int = 4

    def __post_init__(self):
        assert self.width % (16 * self.heads) == 0 and self.heads > 0
        assert 1 <= self.rows <= 4096 and 1 <= self.steps <= 32
        assert 1 <= len(self.contexts) <= 8 and min(self.contexts) > 0
        assert max(self.contexts) + self.steps <= 65536
        assert len(self.arrivals_ps) == len(self.contexts) + 1 and min(self.arrivals_ps) >= 0


@dataclass(frozen=True, order=True)
class Plan:
    rows: int
    tile: int
    resident: int  # bit zero is the prefill request
    partition: bool
    online: bool
    pin: bool
    priority: int
    reuse: bool = True
    cache_divisor: int = 1


def plans(work, phase="episode"):
    masks = range(1 << (len(work.contexts) + 1))
    if phase == "decode":
        masks = range(0, 1 << (len(work.contexts) + 1), 2)
    elif phase == "prefill":
        masks = range(2)
    for p in product((16, 32) if phase != "decode" else (16,),
                     (128, 512), masks, (False, True), (True, False),
                     (True, False), (0, 1) if phase == "episode" else (1,)):
        for divisor in ((1, 4, 8) if p[2] & ~1 else (1,)):
            yield Plan(*p, cache_divisor=divisor)


def retained(work, plan, owner):
    if not plan.resident & (1 << owner):
        return 0
    total = work.rows if owner == 0 else work.contexts[owner - 1] + work.steps
    if owner == 0 or plan.cache_divisor == 1:
        return total
    # Shared frozen prefix policy, aligned to both declared tile lengths.
    return max(0, (work.contexts[owner - 1] // plan.cache_divisor // 512) * 512)


def matrices(work):
    d, h = work.width, work.width // work.heads
    return (("q", d, d), ("k", d, h), ("v", d, h), ("out", d, d),
            ("up", d, 4 * d), ("down", 4 * d, d))


def backing(owner, name, first=0):
    # 2^24 lines per tensor; no overlap even at the largest declared dimensions.
    names = ("input", "q", "k", "v", "output", "norm", "weights")
    return ((owner + 1) << 29) + (names.index(name) << 24) + first


def placement(hw, work, plan, phase="episode"):
    assert phase in ("episode", "decode", "prefill")
    p = Program(hw, plan.priority)
    p.aliases = {}
    d, h = work.width, work.width // work.heads
    banks = tuple(range(hw.global_banks))
    p.reserve("norm", d // 4, banks)  # two affine LayerNorms: four D-vectors
    if plan.pin:
        for name, k, n in matrices(work):
            p.reserve("w_" + name, k * n // 16, banks)
    owners = range(len(work.contexts) + 1)
    if phase == "decode":
        owners = range(1, len(work.contexts) + 1)
    elif phase == "prefill":
        owners = range(1)
    for owner in owners:
        order = banks[owner % 2::2] if plan.partition else banks
        rows = min(plan.rows, work.rows) if owner == 0 else 1
        count = work.rows if owner == 0 else work.contexts[owner - 1] + work.steps
        sizes = {"x": rows * d // 16, "n": rows * d // 16,
                 "q": rows * d // 16, "a": rows * d // 16,
                 "y": rows * d // 16, "f": rows * d // 4,
                 "s": ceildiv(rows * work.heads * (min(plan.tile, count) if plan.online else count), 16),
                 "stats": ceildiv(2 * rows * work.heads, 16),
                 "mix": ceildiv(2 * rows * work.heads, 16)}
        for name in ("k", "v"):
            cache = retained(work, plan, owner)
            sizes[name] = (cache if cache else min(plan.tile, count)) * h // 16
            if 0 < cache < count:
                sizes[name + "t"] = min(plan.tile, count - cache) * h // 16
        if not plan.pin:
            sizes["w"] = max(k * n // 16 for _, k, n in matrices(work))
        # The same request executes these phases in dependency order. Attention
        # scores and the FFN tile never overlap; Q is dead before the output
        # projection; LN1 is dead before attention, and attention is dead before LN2.
        aliases = {"f": "s", "y": "q", "n": "a"} if plan.reuse else {}
        for name, target in aliases.items():
            sizes[target] = max(sizes[name], sizes[target])
        for name, words in sizes.items():
            if name not in aliases:
                p.reserve(f"r{owner}_{name}", words, order)
        for name, target in aliases.items():
            p.regions[f"r{owner}_{name}"] = p.regions[f"r{owner}_{target}"]
            p.aliases[f"r{owner}_{name}"] = f"r{owner}_{target}"
    if max(p.used) * 64 > hw.global_capacity:
        return None
    return p


def compile_program(hw, work, plan, phase="episode"):
    p = placement(hw, work, plan, phase)
    if p is None:
        return None
    d, heads, h = work.width, work.heads, work.width // work.heads
    owners = sorted({int(name.split("_")[0][1:]) for name in p.regions if name.startswith("r")})
    origin = min(work.arrivals_ps[1:]) if phase == "decode" else (work.arrivals_ps[0] if phase == "prefill" else 0)
    release = {i: work.arrivals_ps[i] - origin for i in owners}
    global_release = min(release.values())
    reads_from_backing = []
    p.expected_kv = {}
    p.required_outputs = {}
    p.initial_backing = reads_from_backing
    p.matrix_macs = 0
    p.attention_macs = 0

    def access(owner, slot, tag, words, first=0, offset=0):
        return Access(f"r{owner}_{slot}", first, words, tag, offset)

    def dma(owner, name, a, addr, deps=(), write=False, initial=False):
        if initial:
            reads_from_backing.append((addr, a.words, a.value, a.offset))
        return p.add(owner, name, deps, "r" if write else "w", (a,), release[owner], dram_line=addr)

    def alu(owner, name, deps, reads, writes, ops, parallel=None, cycles=None, private=(0, 0)):
        read = p.add(owner, name + ":read", deps, "r", tuple(reads), release[owner])
        compute = p.add(owner, name, (read,), release=release[owner],
                        cycles=cycles or max(1, ceildiv(FP * ops, parallel or hw.x)), alu=FP * ops,
                        local_read=private[0], local_write=private[1])
        return p.add(owner, name + ":write", (compute,), "w", tuple(writes), release[owner])

    norm = Access("norm", 0, d // 4, ("norm",))
    # One shared immutable set of norm/linear weights in pinned mode.
    first_owner = min(owners, key=release.get)
    norms = dma(first_owner, "norm weights", norm, backing(9, "norm"), initial=True)
    weights, loads, offsets = {}, {}, {}
    off = 0
    for name, k, n in matrices(work):
        offsets[name] = off
        if plan.pin:
            weights[name] = Access("w_" + name, 0, k * n // 16, ("weight", name))
            loads[name] = dma(first_owner, "weight " + name, weights[name], backing(9, "weights", off), initial=True)
        off += k * n // 16

    def linear(owner, name, inp, out, rows, k, n, deps):
        a = weights.get(name)
        if a is None:
            a = access(owner, "w", ("weight", name), k * n // 16)
            ready = dma(owner, "weight " + name, a, backing(9, "weights", offsets[name]), deps, initial=True)
        else:
            ready = loads[name]
        # Reduction slices fit the private buffer. Accumulators stay in the
        # output registers across slices; the model has no overlap at this core.
        columns = ceildiv(n, hw.x)
        chunk = min(k, hw.private_capacity // (4 * columns))
        if chunk < 1:
            raise ValueError("No legal private weight slice")
        cycles = sum(FP * rows * ceildiv(min(chunk, k - start), hw.y) * columns
                     for start in range(0, k, chunk))
        stripe = ceildiv(k * columns * 4, 8)
        cycles += stripe * (rows + 1)
        local = ceildiv(k * n * 4, 8)
        p.matrix_macs += rows * k * n
        return alu(owner, name, (*deps, ready), (inp, a), (out,), rows * k * n,
                   cycles=cycles, private=(local * rows, local))

    def norm_layer(owner, stage, inp, out, rows, deps):
        affine = Access("norm", (stage - 1) * d // 8, d // 8, ("norm",), (stage - 1) * d // 8)
        return alu(owner, f"LN{stage}", (*deps, norms), (inp, affine), (out,), rows * (8 * d + 16))

    def kv(owner, kind, first, count):
        cache = retained(work, plan, owner)
        if cache and first < cache:
            assert first + count <= cache
            return access(owner, kind, (kind, owner), count * h // 16, first * h // 16, first * h // 16)
        return access(owner, kind + ("t" if cache else ""), (kind, owner), count * h // 16, 0, first * h // 16)

    def attention(owner, q, rows, count, prefix, deps, query_start):
        prior, state, stats, logits_tiles = tuple(deps), None, None, []
        tiled = [(lo, min(plan.tile, count - lo)) for lo in range(0, count, plan.tile)]

        def stage(kind, lo, num, after):
            a = kv(owner, kind, lo, num)
            if lo < retained(work, plan, owner):
                return a, after
            task = dma(owner, "stream " + kind, a, backing(owner, kind, lo * h // 16), after,
                       initial=owner > 0 and lo + num <= work.contexts[owner - 1])
            # A tail can mix old tokens with appended values; declare only old cells initial.
            if owner > 0:
                old = max(0, min(num, work.contexts[owner - 1] - lo)) * h // 16
                reads_from_backing.append((backing(owner, kind, lo * h // 16), old, a.value, a.offset))
            return a, (task,)

        def scores(lo, num, after):
            key, after = stage("k", lo, num, after)
            first = 0 if plan.online else ceildiv(lo * rows * heads, 16)
            score = access(owner, "s", ("scores", *prefix, lo), ceildiv(rows * heads * num, 16), first)
            macs = rows * heads * num * h
            p.attention_macs += macs
            compute = FP * rows * heads * ceildiv(h, hw.y) * ceildiv(num, hw.x)
            task = alu(owner, "QK causal" if owner == 0 else "QK", after, (q, key), (score,), macs,
                       cycles=compute + 2 * ceildiv(num * h * 4, 8))
            return score, task

        def av(lo, num, weights, after, mix=None):
            nonlocal state, stats
            value, after = stage("v", lo, num, after)
            out = access(owner, "a", ("attention sum", *prefix, lo), rows * d // 16)
            reads = (weights, value) + ((mix,) if mix is not None else ()) + ((state, stats) if state is not None and plan.online else
                                        ((state,) if state is not None else ()))
            next_stats = access(owner, "stats", ("merged stats", *prefix, lo), ceildiv(2 * rows * heads, 16))
            macs = rows * heads * num * h
            p.attention_macs += macs
            writes = (out, next_stats) if plan.online else (out,)
            ops = macs + (rows * (2 * d + 6 * heads) if plan.online else 0)
            task = alu(owner, "AV merge", after, reads, writes, ops, parallel=hw.x * hw.y)
            state, stats = out, next_stats
            return (task,)

        for lo, num in tiled:
            score, task = scores(lo, num, prior)
            probs = Access(score.slot, score.first, score.words, ("probabilities", *prefix, lo))
            if plan.online:
                reads = (score,) + ((stats,) if state is not None else ())
                mix = access(owner, "mix", ("block stats", *prefix, lo), ceildiv(2 * rows * heads, 16))
                normalize = alu(owner, "online softmax mask" if owner == 0 else "online softmax", (task,),
                                reads, (probs, mix), rows * heads * (18 * num + 24))
                prior = av(lo, num, probs, (normalize,), mix)
            else:
                logits_tiles.append((lo, num, score, probs))
                prior = (task,)
        if not plan.online:
            task = alu(owner, "dense softmax mask" if owner == 0 else "dense softmax", prior,
                       tuple(t[2] for t in logits_tiles), tuple(t[3] for t in logits_tiles),
                       rows * heads * (32 * count + 16))
            prior = (task,)
            for lo, num, _, probs in logits_tiles:
                prior = av(lo, num, probs, prior)
        if plan.online:
            out = access(owner, "a", ("attention", *prefix), rows * d // 16)
            done = alu(owner, "attention divide", prior, (state, stats), (out,), rows * d * 2)
            prior, state = (done,), out
        # Independent validation checks these expected logical intervals.
        p.expected_kv[owner, prefix] = (count, rows, query_start)
        return state, prior

    def tail(owner, x, a, rows, prefix, deps):
        y = access(owner, "y", ("projected", *prefix), rows * d // 16)
        done = linear(owner, "out", a, y, rows, d, d, deps)
        residual = access(owner, "x", ("residual1", *prefix), rows * d // 16)
        done = alu(owner, "residual1", (done,), (x, y), (residual,), rows * d)
        n = access(owner, "n", ("LN2", *prefix), rows * d // 16)
        done = norm_layer(owner, 2, residual, n, rows, (done,))
        f = access(owner, "f", ("ffn", *prefix), rows * d // 4)
        done = linear(owner, "up", n, f, rows, d, 4 * d, (done,))
        g = access(owner, "f", ("gelu", *prefix), rows * d // 4)
        done = alu(owner, "GELU", (done,), (f,), (g,), rows * 4 * d * 20)
        y = access(owner, "y", ("down", *prefix), rows * d // 16)
        done = linear(owner, "down", g, y, rows, 4 * d, d, (done,))
        out = access(owner, "y", ("output", *prefix), rows * d // 16)
        done = alu(owner, "residual2", (done,), (residual, y), (out,), rows * d)
        return out, (done,)

    for owner in owners:
        cache = retained(work, plan, owner)
        previous, fills = (), ()
        if owner > 0 and cache:
            count = min(cache, work.contexts[owner - 1])
            fills = tuple(dma(owner, "initial " + kind, kv(owner, kind, 0, count),
                              backing(owner, kind), initial=True) for kind in ("k", "v"))
        chunks = ((start, min(plan.rows, work.rows - start)) for start in range(0, work.rows, plan.rows)) if owner == 0 else (
            (work.contexts[owner - 1] + step, 1) for step in range(work.steps))
        for start, rows in chunks:
            prefix = (owner, start)
            x = access(owner, "x", ("input", *prefix), rows * d // 16)
            read = dma(owner, "input", x, backing(owner, "input", start * d // 16), previous, initial=True)
            n = access(owner, "n", ("LN1", *prefix), rows * d // 16)
            done = norm_layer(owner, 1, x, n, rows, (read, *fills))
            outputs = {"q": access(owner, "q", ("query", *prefix), rows * d // 16),
                       "k": kv(owner, "k", start, rows), "v": kv(owner, "v", start, rows)}
            prior = (done,)
            for kind in ("q", "k", "v"):
                done = linear(owner, kind, n, outputs[kind], rows, d, d if kind == "q" else h, prior)
                prior = (done,)
                # Persist every new KV even in resident mode; all modes pay the same append.
                if kind != "q":
                    out = dma(owner, "append " + kind, outputs[kind], backing(owner, kind, start * h // 16),
                              prior, write=True)
                    prior = (out,)
            if owner == 0:
                out = dma(owner, "save query", outputs["q"], backing(owner, "q", start * d // 16), prior, write=True)
                previous = (out,)
            else:
                a, prior = attention(owner, outputs["q"], 1, start + 1, prefix, prior, start)
                out, prior = tail(owner, x, a, 1, prefix, prior)
                done = dma(owner, "output", out, backing(owner, "output", start * d // 16), prior, write=True)
                previous = (done,)
                p.required_outputs[backing(owner, "output", start * d // 16)] = (out.value, out.words)
            fills = ()
        if owner == 0:
            for start in range(0, work.rows, plan.rows):
                rows = min(plan.rows, work.rows - start)
                prefix = (owner, start)
                q = access(owner, "q", ("query", *prefix), rows * d // 16)
                read = dma(owner, "restore query", q, backing(owner, "q", start * d // 16), previous)
                x = access(owner, "x", ("input", *prefix), rows * d // 16)
                load = dma(owner, "restore skip", x, backing(owner, "input", start * d // 16), (read,), initial=True)
                # Charge rectangular tiles including masked upper-triangular entries.
                a, prior = attention(owner, q, rows, start + rows, prefix, (load,), start)
                out, prior = tail(owner, x, a, rows, prefix, prior)
                done = dma(owner, "output", out, backing(owner, "output", start * d // 16), prior, write=True)
                previous = (done,)
                p.required_outputs[backing(owner, "output", start * d // 16)] = (out.value, out.words)
    return p
