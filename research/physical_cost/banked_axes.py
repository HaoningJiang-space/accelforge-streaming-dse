"""Measure exact architecture-first proof work as physical service choices grow."""

import argparse
from dataclasses import asdict, dataclass, replace
import gzip
from itertools import product
import json
from pathlib import Path
from time import perf_counter

from research.physical_cost.banked_scale import (
    WORKLOADS, Evaluator, breakpoints, catalog, grid, service,
)
from research.physical_cost.banked_serving import mappings


MAC_COUNTS = (1024, 2048, 4096)
DDR_TICKS = (1, 2, 4, 8)
AREA_CAPS = (1.35, 2.7, 4.5)
CASES = ("holdout576", "kv_long", "kv_asymmetric")
AXES = tuple(product(MAC_COUNTS, DDR_TICKS))
PANELS = {
    "reference": ((2048, 2),),
    "ddr_axis": tuple((2048, tick) for tick in DDR_TICKS),
    "both_axes": AXES,
    **{f"fixed_ddr_{64 // tick}GBps": tuple((mac, tick) for mac in MAC_COUNTS) for tick in DDR_TICKS},
}


@dataclass
class Stratum:
    area_admitted: int
    feasible: int
    nominal_classes: set
    rows: dict


def prepare(macros, work, caps, plans, grid_factory=grid):
    """Share capacity catalogs across area caps and keep cap-specific dominance."""
    strata = {}
    profiles = 0
    for mac, tick in AXES:
        hardware = grid_factory(macros, max(caps), mac_count=mac, ddr_word_ns=tick)
        rows, count = catalog(hardware, work, macros, plans)
        profiles += count
        areas = {hw: hw.total_area_mm2(macros) for hw in hardware}
        for cap in caps:
            admitted = [hw for hw in hardware if areas[hw] <= cap]
            feasible = tuple(hw for hw in admitted if hw in rows)
            reduced = breakpoints(feasible, rows)
            strata[mac, tick, cap] = Stratum(len(admitted), len(feasible),
                                             {service(hw, macros) for hw in feasible},
                                             {hw: rows[hw] for hw in reduced})
    return strata, profiles


def solve(strata, work, macros, plans):
    rows = {hw: row for stratum in strata for hw, row in stratum.rows.items()}
    reduced = breakpoints(tuple(rows), rows)
    timings = {rows[hw].timing for hw in reduced}
    data = {
        "area_admitted": sum(stratum.area_admitted for stratum in strata),
        "feasible": sum(stratum.feasible for stratum in strata),
        "nominal_classes": len(set().union(*(stratum.nominal_classes for stratum in strata))),
        "effective_classes": len(timings),
        "breakpoints": len(reduced),
    }
    if not reduced:
        return data
    evaluator = Evaluator(work, macros, plans, rows)
    opened = set()
    score, (hw, index, prefer), visits, checks = evaluator.exact(reduced, opened_classes=opened)
    unresolved = [candidate for candidate in reduced if rows[candidate].lower < score]
    return {
        **data, "exact_edp_aj_ns": score, "winner": asdict(hw),
        "winner_area_mm2": hw.total_area_mm2(macros),
        "winner_mapping": asdict(replace(plans[index], prefer=prefer)),
        "architectures_opened": visits, "classes_opened": len(opened),
        "classes_below_incumbent": len({rows[h].timing for h in unresolved}),
        "architectures_below_incumbent": len(unresolved),
        "classes_compiled": len({timing for timing, _ in evaluator.compiled}),
        "classes_dispatched": len({timing for (timing, _), _ in evaluator.times}),
        "unique_compilations": len(evaluator.compiled), "unique_schedules": len(evaluator.times),
        "schedule_checks": checks,
    }


def run(macros, caps, cases, output, ledger=None):
    area_key = "total_area_mm2" if ledger is not None else "sram_area_mm2"
    caps_key = "total_area_caps_mm2" if ledger is not None else "sram_area_caps_mm2"
    report = {"mac_counts": MAC_COUNTS, "ddr_word_ns": DDR_TICKS,
              "area_kind": area_key, caps_key: caps, "panels": PANELS, "cases": {}}
    if ledger is not None:
        report["ledger"] = ledger.description()
    for name in cases:
        start = perf_counter()
        work = WORKLOADS[name]
        plans = tuple(m for m in mappings() if m.prefer == "P" and (m.resident or not work.reserve_values))
        strata, profiles = prepare(macros, work, caps, plans, grid if ledger is None else ledger.grid)
        results = []
        for cap, (label, axes) in product(caps, PANELS.items()):
            result = solve([strata[mac, tick, cap] for mac, tick in axes], work, macros, plans)
            results.append({area_key: cap, "panel": label, **result})
            print(name, cap, label, result["effective_classes"], result.get("classes_opened"),
                  result.get("classes_dispatched"), result.get("exact_edp_aj_ns"), flush=True)
        report["cases"][name] = {"workload": asdict(work), "generated_profiles": profiles,
                                 "total_seconds": perf_counter() - start, "cells": results}
        output.write_bytes(gzip.compress(json.dumps(report, indent=2).encode(), mtime=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--caps", nargs="+", type=float, default=AREA_CAPS)
    parser.add_argument("--cases", nargs="+", choices=WORKLOADS, default=CASES)
    args = parser.parse_args()
    if any(cap <= 0 for cap in args.caps):
        parser.error("SRAM area caps must be positive")
    macros = {int(size): value for size, value in json.loads(args.table.read_text())["macros"].items()}
    run(macros, args.caps, args.cases, args.output)


if __name__ == "__main__":
    main()
