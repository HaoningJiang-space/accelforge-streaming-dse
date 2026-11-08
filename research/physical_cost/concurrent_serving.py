"""Compile concurrent prefill and growing KV attention into an addressed DAG."""

from dataclasses import dataclass
from itertools import product

from research.physical_cost.serving_trace import Access, Program
from research.runtime.strip_codesign import ceildiv


WIDTH, HEADS = 64, 4
PREFILL = 0
WEIGHTS = 1 << 22


@dataclass(frozen=True)
class Workload:
    rows: int
    contexts: tuple[int, int]
    steps: int
    arrivals_ps: tuple[int, int, int]


@dataclass(frozen=True, order=True)
class Plan:
    rows: int
    tile: int
    slots: int
    resident: int
    partition: bool
    online: bool
    priority: int


def plans():
    return (Plan(*args) for args in product((16, 32), (32, 96), (1, 2), (0, 1, 2, 3),
                                           (False, True), (False, True), (0, 1)))


def placement(hw, work, plan):
    program = Program(hw, plan.priority)
    banks = tuple(range(hw.global_banks))
    p_banks = banks[::2] if plan.partition else banks
    d_banks = banks[1::2] if plan.partition else banks
    program.reserve("pw", WIDTH, p_banks)
    program.reserve("dw", 3 * WIDTH, d_banks)
    for slot in range(plan.slots):
        program.reserve(f"px{slot}", min(work.rows, plan.rows), p_banks)
        program.reserve(f"py{slot}", min(work.rows, plan.rows), p_banks)
    for request, context in enumerate(work.contexts, 1):
        maximum = context + work.steps
        # x, q, a K/V tile, and FP32 output accumulator.
        program.reserve(f"x{request}", 1, d_banks)
        program.reserve(f"q{request}", 1, d_banks)
        program.reserve(f"o{request}", 5 if plan.online else 4, d_banks)
        if plan.online:
            program.reserve(f"m{request}", 1, d_banks)
        size = maximum if plan.resident & (1 << (request - 1)) else min(plan.tile, maximum)
        for kind in ("k", "v"):
            program.reserve(f"{kind}{request}", size, d_banks)
        scores = min(plan.tile, maximum) if plan.online else maximum
        program.reserve(f"s{request}", ceildiv(scores * HEADS * 4, 64), d_banks)
    return program if max(program.used) * 64 <= hw.global_capacity else None


def compile_program(hw, work, plan):
    program = placement(hw, work, plan)
    if program is None:
        return None

    def dma(owner, label, access, addr, deps=(), write=False, release=0):
        return program.add(owner, label, deps, "r" if write else "w", (access,), release, dram_line=addr)

    def alu(owner, label, deps, reads, cycles, actions, writes, private=(0, 0)):
        fetch = program.add(owner, label + ":read", deps, "r", reads)
        operate = program.add(owner, label, (fetch,), cycles=cycles, alu=actions,
                              local_read=private[0], local_write=private[1])
        return program.add(owner, label + ":write", (operate,), "w", writes)

    def gemm(owner, label, deps, reads, r, k, n, writes, separate_weights=False):
        # Output lanes follow X, reduction lanes follow Y.
        if k * ceildiv(n, hw.x) > hw.private_capacity:
            raise ValueError("GEMM stripe exceeds private SRAM")
        active = min(hw.x, n)
        stripe = [ceildiv(k * len(range(lane, n, hw.x)), 8) for lane in range(active)]
        fills = r if separate_weights else 1
        cycles = r * ceildiv(k, hw.y) * ceildiv(n, hw.x) + max(stripe) * (fills + r)
        return alu(owner, label, deps, reads, cycles, r * k * n, writes,
                   (sum(stripe) * r, sum(stripe) * fills))

    p_weight = Access("pw", 0, WIDTH, ("pw",))
    p_arrival = work.arrivals_ps[0]
    p_weights = dma(PREFILL, "prefill weights", p_weight, WEIGHTS, release=p_arrival)
    free = {}
    for i, row in enumerate(range(0, work.rows, plan.rows)):
        slot = i % plan.slots
        rows = min(plan.rows, work.rows - row)
        x = Access(f"px{slot}", 0, rows, ("prefill input", i))
        y = Access(f"py{slot}", 0, rows, ("prefill output", i))
        read = dma(PREFILL, "prefill input", x, (1 << 19) + row, free.get(slot, ()),
                   release=p_arrival)
        done = gemm(PREFILL, "prefill", (p_weights, read), (p_weight, x), rows, WIDTH, WIDTH, (y,))
        drain = dma(PREFILL, "prefill output", y, (1 << 20) + row, (done,), write=True)
        free[slot] = (drain,)

    d_weight = Access("dw", 0, 3 * WIDTH, ("dw",))
    d_weights = dma(1, "decode weights", d_weight, WEIGHTS + (1 << 12),
                    release=min(work.arrivals_ps[1:]))
    for request, context in enumerate(work.contexts, 1):
        arrival = work.arrivals_ps[request]
        resident = bool(plan.resident & (1 << (request - 1)))
        base = request << 16

        def kv(kind, token, count, stage=0):
            return Access(f"{kind}{request}", token if resident else stage, count, (kind, request), token)

        def backing(kind, token):
            return base + (0 if kind == "k" else 1 << 14) + token

        fills = ()
        if resident:
            fills = tuple(dma(request, f"initial {kind}", kv(kind, 0, context), backing(kind, 0),
                              release=arrival) for kind in ("k", "v"))
        previous = ()
        for step in range(work.steps):
            token = context + step
            prefix = (request, step)
            hidden = Access(f"x{request}", 0, 1, ("hidden", *prefix))
            query = Access(f"q{request}", 0, 1, ("query", *prefix))
            new_k, new_v = kv("k", token, 1), kv("v", token, 1)
            input_task = dma(request, "decode input", hidden, base + (1 << 15) + step,
                             previous, release=arrival)
            projection = tuple(
                gemm(request, f"project {label}", (input_task, d_weights, *fills),
                     (Access("dw", i * WIDTH, WIDTH, ("dw",), i * WIDTH), hidden),
                     1, WIDTH, WIDTH, (out,))
                for i, (label, out) in enumerate(zip(("q", "k", "v"), (query, new_k, new_v), strict=True))
            )
            prior = projection
            if not resident:
                prior = tuple(dma(request, f"append {kind}", access, backing(kind, token),
                                  projection, write=True)
                              for kind, access in (("k", new_k), ("v", new_v)))
            state = None
            score_slot = f"s{request}"

            def stage(kind, start, count, deps):
                access = kv(kind, start, count)
                if not resident:
                    deps = (dma(request, f"stream {kind}", access, backing(kind, start), deps),)
                return access, deps

            def scores(start, count, deps):
                key, deps = stage("k", start, count, deps)
                offset = 0 if plan.online else start * HEADS * 4 // 64
                logits = Access(score_slot, offset, ceildiv(count * HEADS * 4, 64),
                                ("scores", *prefix, start))
                done = gemm(request, "QK", deps, (query, key), HEADS, WIDTH // HEADS, count,
                            (logits,), separate_weights=True)
                return logits, done

            def weighted(start, count, deps, weights, state):
                value, deps = stage("v", start, count, deps)
                next_state = Access(f"o{request}", 0, 5 if plan.online else 4,
                                    ("value sum", *prefix, start))
                reads = (*weights, value) if state is None else (*weights, value, state)
                # FP32 weighted accumulation and the online rescale are charged
                # as emulated arithmetic on the same compute budget.
                ops = 8 * WIDTH * count + (8 * (WIDTH + HEADS) if plan.online and state else 0)
                done = alu(request, "AV and merge", deps, reads, ceildiv(ops, hw.x * hw.y),
                           ops, (next_state,))
                return next_state, (done,)

            tiles = tuple((start, min(plan.tile, token + 1 - start))
                          for start in range(0, token + 1, plan.tile))
            if plan.online:
                for start, count in tiles:
                    logits, done = scores(start, count, prior)
                    weights = Access(score_slot, logits.first, logits.words, ("weights", *prefix, start))
                    mix = Access(f"m{request}", 0, 1, ("max and sum", *prefix, start))
                    previous_stats = () if state is None else (
                        Access(state.slot, 4, 1, state.value, 4),
                    )
                    # Max and sum reductions, exp, scale and state maintenance.
                    ops = HEADS * (18 * count + 24)
                    norm = alu(request, "online softmax", (done,), (logits, *previous_stats),
                               ceildiv(ops, hw.x) + 2 * (count - 1).bit_length(), ops, (weights, mix))
                    state, prior = weighted(start, count, (norm,), (weights, mix), state)
            else:
                tiles_of_logits = []
                for start, count in tiles:
                    logits, done = scores(start, count, prior)
                    tiles_of_logits.append(logits)
                    prior = (done,)
                all_weights = tuple(Access(score_slot, item.first, item.words,
                                           ("weights", *prefix, start))
                                    for item, (start, _) in zip(tiles_of_logits, tiles, strict=True))
                ops = HEADS * 32 * (token + 1)
                norm = alu(request, "dense softmax", prior, tuple(tiles_of_logits),
                           ceildiv(ops, hw.x) + 2 * token.bit_length(), ops, all_weights)
                prior = (norm,)
                for (start, count), weights in zip(tiles, all_weights, strict=True):
                    state, prior = weighted(start, count, prior, (weights,), state)
            result = Access(f"o{request}", 0, 4, ("result", *prefix))
            # Dense weights are normalized before AV. Online weights are
            # normalized only after the final block.
            ops = 16 * WIDTH if plan.online else 0
            if ops:
                output = alu(request, "final divide", prior, (state,), ceildiv(ops, hw.x), ops, (result,))
            else:
                output, result = prior[0], state
            out = dma(request, "decode output", result, base + (1 << 15) + 4096 + step * 4,
                      (output,), write=True)
            previous = (out,)
            fills = ()
        if resident:
            for kind in ("k", "v"):
                dma(request, f"flush {kind}", kv(kind, context, work.steps), backing(kind, context),
                    previous, write=True)
    return program
