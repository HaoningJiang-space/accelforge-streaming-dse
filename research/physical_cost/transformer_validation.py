"""Independent numerical, physical-address and DDR checks for complete blocks."""

from collections import Counter, defaultdict
from itertools import pairwise
from math import ceil

import numpy as np

from research.physical_cost.banked_oracle import addresses
from research.physical_cost.serving_ddr_oracle import check


def block(x, weights, heads, old=None, tile=None):
    """FP32 GQA pre-LN block; return outputs and the appended KV cache."""
    x = np.asarray(x, dtype=np.float32)
    d, rows = x.shape[1], len(x)

    def norm(a, stage):
        centered = a - a.mean(-1, keepdims=True)
        return centered / np.sqrt((centered * centered).mean(-1, keepdims=True) + 1e-5) * weights[f"g{stage}"] + weights[f"b{stage}"]

    n = norm(x, 1)
    q = (n @ weights["q"]).reshape(rows, heads, d // heads)
    k, v = n @ weights["k"], n @ weights["v"]
    past = 0 if old is None else len(old[0])
    if old is not None:
        k, v = np.concatenate((old[0], k)), np.concatenate((old[1], v))
    if tile is None:
        scores = np.einsum("rhd,td->rht", q, k) / np.sqrt(np.float32(d // heads))
        scores = np.where(np.arange(len(k))[None, None, :] <= (past + np.arange(rows))[:, None, None], scores, -np.inf)
        prob = np.exp(scores - scores.max(-1, keepdims=True))
        prob /= prob.sum(-1, keepdims=True)
        a = np.einsum("rht,td->rhd", prob, v)
    else:
        # Per-query independent streamed max/sum/value recurrence. No masked
        # all-minus-infinity tile is fed through inf-inf arithmetic.
        a = np.zeros_like(q)
        for row in range(rows):
            end = past + row + 1
            peak = np.full(heads, -np.inf, dtype=np.float32)
            denom = np.zeros(heads, dtype=np.float32)
            value = np.zeros((heads, d // heads), dtype=np.float32)
            for lo in range(0, end, tile):
                stop = min(end, lo + tile)
                scores = q[row] @ k[lo:stop].T / np.sqrt(np.float32(d // heads))
                new_peak = np.maximum(peak, scores.max(-1))
                scale = np.exp(peak - new_peak)
                probs = np.exp(scores - new_peak[:, None])
                denom = denom * scale + probs.sum(-1)
                value = value * scale[:, None] + probs @ v[lo:stop]
                peak = new_peak
            a[row] = value / denom[:, None]
    y = x + a.reshape(rows, d) @ weights["out"]
    f = norm(y, 2) @ weights["up"]
    gelu = 0.5 * f * (1 + np.tanh(np.sqrt(np.float32(2 / np.pi)) * (f + np.float32(0.044715) * f**3)))
    return y + gelu @ weights["down"], (k, v)


def numerical(width=64, heads=4):
    rng = np.random.default_rng(94123)
    weights = {name: (rng.standard_normal((k, n)) / np.sqrt(k)).astype(np.float32)
               for name, k, n in (("q", width, width), ("k", width, width // heads),
                                   ("v", width, width // heads), ("out", width, width),
                                   ("up", width, 4 * width), ("down", 4 * width, width))}
    for stage in (1, 2):
        weights[f"g{stage}"] = rng.uniform(0.8, 1.2, width).astype(np.float32)
        weights[f"b{stage}"] = rng.uniform(-0.1, 0.1, width).astype(np.float32)
    x = rng.standard_normal((35, width)).astype(np.float32)
    reference, cache = block(x, weights, heads)
    errors = []
    for tile in (1, 7, 16, 64):
        actual, kv = block(x, weights, heads, tile=tile)
        np.testing.assert_allclose(actual, reference, atol=2e-5, rtol=2e-5)
        assert all(np.array_equal(a, b) for a, b in zip(cache, kv, strict=True))
        errors.append(float(abs(actual - reference).max()))
        old = None
        values = []
        for row in x:
            out, old = block(row[None], weights, heads, old, tile)
            values.append(out[0])
        np.testing.assert_allclose(values, reference, atol=2e-5, rtol=2e-5)
        errors.append(float(abs(np.asarray(values) - reference).max()))
    return {"width": width, "heads": heads, "max_absolute_error": max(errors),
            "dtype": "float32", "prefill_rows": len(x), "decode_steps": len(x), "tile_sizes": [1, 7, 16, 64]}


def numerical_long(context, width=64, heads=4):
    rng = np.random.default_rng(8102 + context)
    weights = {name: (rng.standard_normal((k, n)) / np.sqrt(k)).astype(np.float32)
               for name, k, n in (("q", width, width), ("k", width, width // heads),
                                   ("v", width, width // heads), ("out", width, width),
                                   ("up", width, 4 * width), ("down", 4 * width, width))}
    for stage in (1, 2):
        weights[f"g{stage}"] = np.ones(width, dtype=np.float32)
        weights[f"b{stage}"] = np.zeros(width, dtype=np.float32)
    old = tuple(rng.standard_normal((context, width // heads)).astype(np.float32) for _ in range(2))
    inputs = rng.standard_normal((4, width)).astype(np.float32)
    reference, cache = block(inputs, weights, heads, old)
    errors = []
    for tile in (128, 512):
        actual, appended = block(inputs, weights, heads, old, tile)
        np.testing.assert_allclose(actual, reference, atol=2e-5, rtol=2e-5)
        assert all(np.array_equal(a, b) for a, b in zip(appended, cache, strict=True))
        errors.append(float(abs(actual - reference).max()))
    return {"context": context, "decode_steps": 4, "width": width,
            "max_absolute_error": max(errors), "tiles": [128, 512]}


def verify(program, result, macros, device, work=None, phase="episode", *, allow_reservation_overflow=False):
    """Replay all accesses and versions without using dispatcher calendars."""
    spans, finish, commands = result["trace"]
    hw = program.hardware
    macro, local = macros[hw.global_bank_bytes], macros[hw.weight_bytes_per_stripe]
    period = 1000 * ceil(max(macro["cycle_ns"], macro["access_ns"]))
    ports, cells = defaultdict(list), defaultdict(list)
    occupied = {}
    for name, region in program.regions.items():
        for loc in addresses(region, 0, region.words):
            canonical = program.aliases.get(name, name)
            assert loc not in occupied or occupied[loc] == canonical
            assert loc[1] >= 0 and (allow_reservation_overflow or loc[1] < hw.global_capacity // 64)
            occupied[loc] = canonical
    expected = Counter()
    counts = Counter()
    scans = defaultdict(Counter)
    for i, task in enumerate(program.tasks):
        if task.label in ("QK:read", "QK causal:read", "AV merge:read"):
            # Query or probability tags identify the request and logical token.
            prefix = task.accesses[0].value[1:3]
            for a in task.accesses:
                if a.value[0] in ("k", "v"):
                    scans[task.owner, prefix[1], a.value[0]].update(range(a.offset, a.offset + a.words))
        for a in task.accesses:
            for j, loc in enumerate(addresses(program.regions[a.slot], a.first, a.words)):
                expected[i, task.direction, loc, (a.value, a.offset + j),
                         None if task.dram_line is None else task.dram_line + j] += 1
    bursts = check(commands, device)
    transfers = defaultdict(list)
    for line, op, begin, end in bursts:
        transfers[line, op].append((begin, end))
    ends = [0] * len(program.tasks)
    memory, dram = [], []
    for begin, end, i, direction, bank, row, value, line in spans:
        task = program.tasks[i]
        assert begin >= max([task.release, *(finish[j] for j in task.deps)])
        assert begin < end <= finish[i]
        ports[direction, bank].append((begin, end))
        ends[i] = max(ends[i], end)
        if direction == "core":
            assert end - begin == task.cycles * 1000
            counts.update(alu=task.alu, local_read=task.local_read, local_write=task.local_write)
            continue
        assert end - begin == period and (bank, row) in occupied
        cells[bank, row].append((begin, end))
        expected[i, direction, (bank, row), value, line] -= 1
        counts[direction] += 1
        memory.append((end if direction == "w" else begin, direction == "r", (bank, row), value, begin, end))
        if line is not None:
            op = "RD" if direction == "w" else "WR"
            first, last = transfers[line, op].pop(0)
            assert (last == begin) if op == "RD" else (first >= end)
            ends[i] = max(ends[i], last)
            counts["ddr_read" if op == "RD" else "ddr_write"] += 1
            dram.append((last, op == "RD", line, value))
    assert ends == finish and all(v == 0 for v in expected.values())
    assert all(not entries for entries in transfers.values())
    for times in (*ports.values(), *cells.values()):
        assert all(a[1] <= b[0] for a, b in pairwise(sorted(times)))
    values, lifetime = {}, {}
    for _, read, loc, value, begin, end in sorted(memory):
        if read:
            assert values[loc][0] == value, (loc, values[loc], value)
            born = values[loc][1]
        else:
            born = begin
            values[loc] = value, born
        lifetime[loc, born] = end
    persistent = {}
    for addr, words, tag, offset in program.initial_backing:
        for j in range(words):
            value = tag, offset + j
            assert addr + j not in persistent or persistent[addr + j] == value
            persistent[addr + j] = value
    for _, read, line, value in sorted(dram):
        if read:
            assert persistent[line] == value, (line, persistent.get(line), value)
        else:
            persistent[line] = value
    for addr, (tag, words) in program.required_outputs.items():
        assert all(persistent[addr + j] == (tag, j) for j in range(words))
    if work is not None:
        owners = [0] if phase == "prefill" else list(range(1, len(work.contexts) + 1)) if phase == "decode" else list(range(len(work.contexts) + 1))
        token_count = (work.rows if 0 in owners else 0) + sum(work.steps for owner in owners if owner)
        assert program.matrix_macs == token_count * (10 * work.width**2 + 2 * work.width**2 // work.heads)
        per_kv = work.width // work.heads // 16
        for owner in owners:
            starts = sorted({start for req, start, _ in scans if req == owner})
            if owner:
                assert starts == list(range(work.contexts[owner - 1], work.contexts[owner - 1] + work.steps))
            else:
                assert starts[0] == 0
            for index, start in enumerate(starts):
                count = start + 1 if owner else starts[index + 1] if index + 1 < len(starts) else work.rows
                for kind in ("k", "v"):
                    assert scans[owner, start, kind] == Counter(range(count * per_kv))
            for kind_index, kind in enumerate(("k", "v"), 2):
                first, count = (0, work.rows) if owner == 0 else (work.contexts[owner - 1], work.steps)
                base = ((owner + 1) << 29) + (kind_index << 24)
                assert all(persistent[base + line] == ((kind, owner), line)
                           for line in range(first * per_kv, (first + count) * per_kv))
    assert dict(counts) == result["actions"]
    prices = {"r": round(macro["read_nj"] * 1e9), "w": round(macro["write_nj"] * 1e9),
              "local_read": round(local["read_nj"] * 1e9), "local_write": round(local["write_nj"] * 1e9),
              "ddr_read": hw.ddr_read_aj, "ddr_write": hw.ddr_write_aj, "alu": 84000}
    energy = sum(prices[k] * v for k, v in counts.items())
    end = max(finish)
    standby = round(hw.standby_mw(macros) * end * 1000)
    assert (energy, standby, end, (energy + standby) * end) == (
        result["dynamic_aj"], result["standby_aj"], result["elapsed_ps"], result["edp"])
    events = [(born, 1, loc[0]) for (loc, born) in lifetime]
    events += [(end, -1, loc[0]) for (loc, _), end in lifetime.items()]
    current = [0] * hw.global_banks
    peak = current.copy()
    for _, delta, bank in sorted(events):
        current[bank] += 64 * delta
        peak[bank] = max(peak[bank], current[bank])
        assert current[bank] >= 0 and (allow_reservation_overflow or current[bank] <= hw.global_capacity)
    return {"ddr_bursts": len(bursts), "commands": len(commands), "tasks": len(finish),
            "peak_live_bank_bytes": peak, "reserved_bank_bytes": [64 * n for n in program.used],
            "first_data_ps": bursts[0][2], "matrix_macs": program.matrix_macs,
            "attention_macs": program.attention_macs, "output_tiles": len(program.required_outputs),
            "reservation_overflow_diagnostic": allow_reservation_overflow}


def main():
    import argparse
    from dataclasses import replace
    import gzip
    import json
    from pathlib import Path
    import subprocess
    import sys

    from research.physical_cost.paid_area import PaidArchitecture
    from research.physical_cost.serving_exhaustive import write_atomic
    from research.physical_cost.serving_trace import run
    from research.physical_cost.transformer_serving import Workload, Plan, compile_program

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sram", type=Path)
    parser.add_argument("ramulator", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "-C", str(args.ramulator), "rev-parse", "HEAD"], text=True).strip()
    assert revision == "7bead6cb7c4b03e095c6d4769ae3181a8e0bf6da"
    sys.path.insert(0, str(args.ramulator / "python"))
    from ramulator.dram import DDR4

    device = DDR4(org_preset="DDR4_8Gb_x8", timing_preset="DDR4_2400R", rank=1)
    macros = {int(k): v for k, v in json.loads(args.sram.read_text())["macros"].items()}
    report = {"ramulator_revision": revision, "numeric": [numerical(64), numerical(128)],
              "long_numeric": [numerical_long(8192), numerical_long(12288)], "replays": []}
    for path in args.reports:
        data = json.loads(gzip.decompress(path.read_bytes()))
        work = Workload(**data["workload"])
        chosen = set(data["summary"]["episode_winners"] + data["summary"]["decode_ties"])
        for index in sorted(chosen):
            hw = PaidArchitecture(**data["hardware"][index])
            for phase in ("episode", "decode"):
                row = data["reference"][phase][index]
                if row["best"] is None:
                    continue
                plan = Plan(**row["best"]["plan"])
                program = compile_program(hw, work, plan, phase)
                result = run(program, macros, record=True, track_requests=True)
                assert result["edp"] == row["best"]["edp"]
                checked = verify(program, result, macros, device, work, phase)
                static = compile_program(hw, work, replace(plan, reuse=False), phase)
                static_result = None if static is None else run(static, macros)
                # Fixed-mapping paired bank layout may change even if the
                # arithmetic/DDR traffic is identical; report rather than assume.
                report["replays"].append({"case": path.stem, "index": index, "phase": phase,
                                          "oracle": checked, "dynamic_edp": result["edp"],
                                          "static_edp": None if static_result is None else static_result["edp"],
                                          "static_reserved_bytes": None if static is None else [64 * n for n in static.used]})
                del program, result, static, static_result
                write_atomic(args.output, report)
                print(path.stem, index, phase, "verified", flush=True)


if __name__ == "__main__":
    main()
