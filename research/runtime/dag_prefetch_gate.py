"""Replay a fixed, auditable design pool with optional next-wave weight DMA."""

import argparse
import json
from pathlib import Path

from research.joint_budget.protocol import Hardware
from research.runtime.dag_calendar import events, replay, RATES
from research.runtime.dag_cases import CASES
from research.runtime.dag_model import Group
from research.runtime.dag_staging_gate import mm3


def run(source):
    result = []
    for row in source:
        graph = {"3mm": mm3, **CASES}[row["case"]]()
        candidates = []
        seen = set()
        for label, design in {"finite": row["finite"], **row["controls"]}.items():
            hardware = Hardware(**design["architecture"])
            groups = tuple(Group(tuple(g["order"]), g["rows"], tuple(map(tuple, g["tiles"])), tuple(g["pinned"]))
                           for g in design["groups"])
            key = hardware, groups
            if key in seen:
                continue
            seen.add(key)
            witness = tuple(events(graph, hardware, groups))
            plain = replay(graph, hardware, witness)
            ahead = replay(graph, hardware, witness, prefetch=True)
            per_word = max(RATES["dram"], RATES["write"])
            if (plain["actions"] != ahead["actions"] or plain["energy"] != ahead["energy"]
                    or plain["ticks"]-ahead["ticks"] != per_word*ahead["prefetched_weight_words"]
                    or plain["ticks"] != design["ticks"]):
                raise AssertionError("prefetch replay changed the workload or its traffic")
            candidates.append(dict(source=label, architecture=design["architecture"], groups=design["groups"],
                                   original_edp=design["edp"], edp=ahead["energy"]*ahead["ticks"], **ahead))
        best = min(candidates, key=lambda candidate: candidate["edp"])
        result.append(dict(case=row["case"], budget_bytes=row["budget_bytes"], best=best["source"],
                           edp_reduction=1-best["edp"]/row["finite"]["edp"], candidates=candidates))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(json.loads(args.source.read_text(encoding="utf-8")))
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    for row in result:
        print(row["case"], row["budget_bytes"], row["best"], row["edp_reduction"])


if __name__ == "__main__":
    main()
