"""Enumerate every physical serving mapping with resumable per-architecture results."""

import argparse
from dataclasses import asdict
import gzip
from hashlib import sha256
import json
import multiprocessing as mp
import os
from pathlib import Path
from time import monotonic

from research.physical_cost.concurrent_search import CASES, hardware_grid
from research.physical_cost.concurrent_serving import compile_program, plans
from research.physical_cost.external_ddr import SystemLedger
from research.physical_cost.serving_trace import run


DEFAULT_CASES = ("overlap", "holdout3", "holdout4", "holdout_long")


def limit_memory(total_bytes, workers):
    """Install an inherited aggregate commit limit on Windows."""
    if os.name != "nt":
        import resource

        per_process = total_bytes // (workers + 1)
        _, hard = resource.getrlimit(resource.RLIMIT_AS)
        if hard != resource.RLIM_INFINITY:
            per_process = min(per_process, hard)
        resource.setrlimit(resource.RLIMIT_AS, (per_process, per_process))
        return

    import ctypes as c
    from ctypes import wintypes as w

    class Basic(c.Structure):
        _fields_ = [("user_process", c.c_int64), ("user_job", c.c_int64), ("flags", w.DWORD),
                    ("min_working", c.c_size_t), ("max_working", c.c_size_t), ("active", w.DWORD),
                    ("affinity", c.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]

    class Extended(c.Structure):
        _fields_ = [("basic", Basic), ("io", c.c_uint64 * 6), ("process_memory", c.c_size_t),
                    ("job_memory", c.c_size_t), ("peak_process", c.c_size_t), ("peak_job", c.c_size_t)]

    kernel = c.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = (c.c_void_p, w.LPCWSTR)
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.SetInformationJobObject.argtypes = (w.HANDLE, c.c_int, c.c_void_p, w.DWORD)
    kernel.AssignProcessToJobObject.argtypes = (w.HANDLE, w.HANDLE)
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise c.WinError(c.get_last_error())
    info = Extended()
    info.basic.flags = 0x200 | 0x2000  # JOB_MEMORY | KILL_ON_JOB_CLOSE
    info.job_memory = total_bytes
    if not kernel.SetInformationJobObject(job, 9, c.byref(info), c.sizeof(info)):
        raise c.WinError(c.get_last_error())
    if not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
        raise c.WinError(c.get_last_error())
    # Keep the handle open until process exit. Workers inherit job membership.


def evaluate_architecture(task):
    index, hw, work, macros = task
    best = None
    evaluated = 0
    for plan in plans(work):
        program = compile_program(hw, work, plan)
        if program is None:
            continue
        outcome = run(program, macros)
        evaluated += 1
        if best is None or (outcome["edp"], plan) < (best[1]["edp"], best[0]):
            best = plan, outcome
    row = {"index": index, "hardware": asdict(hw), "evaluated": evaluated}
    if best is not None:
        plan, outcome = best
        row["best"] = {"plan": asdict(plan), **outcome}
    return row


def write_atomic(path, value):
    scratch = path.with_suffix(path.suffix + ".tmp")
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    scratch.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw)
    scratch.replace(path)


def panel(pool, name, hardware, macros, output, manifest, deadline):
    started = monotonic()
    work = CASES[name]
    directory = output / name
    directory.mkdir(exist_ok=True)
    metadata = directory / "manifest.json"
    if metadata.exists() and json.loads(metadata.read_text()) != manifest:
        raise ValueError(f"Checkpoint inputs changed in {directory}")
    write_atomic(metadata, manifest)
    rows = {i: json.loads(path.read_text()) for i in range(len(hardware))
            if (path := directory / f"{i}.json").exists()}
    # Visit large SRAM capacities first to dispatch the longest jobs early.
    pending = sorted(((i, hw, work, macros) for i, hw in enumerate(hardware) if i not in rows),
                     key=lambda task: -task[1].global_banks * task[1].global_capacity)
    results = pool.imap_unordered(evaluate_architecture, pending)
    while len(rows) < len(hardware):
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise TimeoutError(f"{name} checkpoint contains {len(rows)}/{len(hardware)} architectures")
        try:
            row = results.next(timeout=min(seconds, 1.0))
        except mp.TimeoutError:
            continue
        index = row["index"]
        write_atomic(directory / f"{index}.json", row)
        rows[index] = row
        if len(rows) % 20 == 0 or len(rows) == len(hardware):
            print(name, len(rows), "/", len(hardware), flush=True)
    valid = [row for row in rows.values() if row["evaluated"]]
    optimum = min(row["best"]["edp"] for row in valid)
    report = {"case": name, "workload": asdict(work), **manifest,
              "seconds_this_run": monotonic() - started,
              "evaluated": sum(row["evaluated"] for row in rows.values()),
              "area_legal_architectures": len(hardware), "feasible_architectures": len(valid),
              "best_edp": optimum,
              "optimal_architectures": sorted(row["index"] for row in valid if row["best"]["edp"] == optimum),
              "architectures": [rows[i] for i in range(len(hardware))]}
    write_atomic(output / f"{name}.json.gz", report)
    print(name, "complete", report["evaluated"], optimum, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sram", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=DEFAULT_CASES)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--memory-gib", type=int, required=True)
    parser.add_argument("--seconds", type=float, required=True)
    args = parser.parse_args()
    if min(args.workers, args.memory_gib, args.seconds) <= 0 or args.workers > (os.cpu_count() or 1):
        parser.error("Use positive limits and at most one worker per logical CPU")
    deadline = monotonic() + args.seconds
    limit_memory(args.memory_gib * 2**30, args.workers)
    sram_raw, ledger_raw = args.sram.read_bytes(), args.ledger.read_bytes()
    sram = json.loads(sram_raw)
    macros = {int(k): v for k, v in sram["macros"].items()}
    ledger = SystemLedger(json.loads(ledger_raw))
    cap = ledger.reference_overhead() + 4.5
    hardware = hardware_grid(macros, ledger, cap)
    source = Path(__file__).parent
    files = ("concurrent_serving.py", "serving_trace.py", "serving_ddr.py",
             "banked_serving.py", "banked_scale.py", "external_ddr.py", "paid_area.py")
    manifest = {"area_cap_mm2": cap, "device": sram.get("device", "itrs-hp"),
                "sram_sha256": sha256(sram_raw).hexdigest(), "ledger_sha256": sha256(ledger_raw).hexdigest(),
                "evaluator_sha256": {name: sha256((source / name).read_bytes()).hexdigest() for name in files},
                "space_sha256": sha256(repr(hardware).encode()).hexdigest()}
    args.output.mkdir(parents=True, exist_ok=True)
    with mp.get_context("spawn").Pool(args.workers) as pool:
        for name in args.cases:
            work = asdict(CASES[name])
            # Normalize tuples to the on-disk JSON representation.
            panel_manifest = {**manifest, "workload": json.loads(json.dumps(work))}
            panel(pool, name, hardware, macros, args.output, panel_manifest, deadline)


if __name__ == "__main__":
    main()
