"""Characterize the SRAM macros used by the mixed-workload gate."""

import argparse
import csv
import json
import math
from pathlib import Path
import subprocess


CACTI_REVISION = "1ffd8dfb10303d306ecd8d215320aea07651e878"
TECH_NM = 45
WORD_BYTES = 64
CAPACITIES = (1024, 4096, 16384, 65536)


def scratchpad_config(template, capacity):
    settings = {
        "-size (bytes)": str(capacity),
        "-block size (bytes)": str(WORD_BYTES),
        "-associativity": "1",
        "-read-write port": "0",
        "-exclusive read port": "1",
        "-exclusive write port": "1",
        "-UCA bank count": "1",
        "-technology (u)": "0.045",
        "-output/input bus width": str(8 * WORD_BYTES),
        "-cache type": '"ram"',
        "-Add ECC": '- "false"',
    }
    configured = []
    for line in template.splitlines():
        for key in settings:
            if line.startswith(key + " "):
                line = f"{key} {settings.pop(key)}"
                break
        configured.append(line)
    if settings:
        raise ValueError(f"CACTI template lacks settings {sorted(settings)}")
    return "\n".join(configured) + "\n"


def read_macro(path, capacity):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, skipinitialspace=True))
    if len(rows) != 1:
        raise ValueError(f"Expected one CACTI row in {path}, got {len(rows)}")
    row = {key.strip(): value for key, value in rows[0].items()}
    expected = {
        "Tech node (nm)": TECH_NM,
        "Capacity (bytes)": capacity,
        "Number of banks": 1,
        "Output width (bits)": 8 * WORD_BYTES,
    }
    for key, value in expected.items():
        if float(row[key]) != value:
            raise ValueError(f"CACTI returned unexpected {key}: {row[key]}")
    quantities = {
        "access_ns": "Access time (ns)",
        "cycle_ns": "Random cycle time (ns)",
        "read_nj": "Dynamic read energy (nJ)",
        "write_nj": "Dynamic write energy (nJ)",
        "leak_mw": "Standby leakage per bank(mW)",
        "area_mm2": "Area (mm2)",
    }
    macro = {key: float(row[column]) for key, column in quantities.items()}
    if any(not math.isfinite(value) or value <= 0 for value in macro.values()):
        raise ValueError(f"Invalid SRAM characterization for {capacity}: {macro}")
    return macro


def characterize(source, output):
    source, output = source.resolve(), output.resolve()
    revision = subprocess.check_output(
        ["git", "-C", source, "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != CACTI_REVISION:
        raise ValueError(f"Unexpected CACTI revision {revision}")
    output.mkdir(parents=True, exist_ok=False)
    template = (source / "cache.cfg").read_text(encoding="utf-8")
    table = {
        "cacti_revision": revision,
        "technology_nm": TECH_NM,
        "word_bytes": WORD_BYTES,
        "read_ports": 1,
        "write_ports": 1,
        "macros": {},
    }
    for capacity in CAPACITIES:
        cfg = output / f"sram_{capacity}.cfg"
        cfg.write_text(scratchpad_config(template, capacity), encoding="utf-8")
        with cfg.with_suffix(".log").open("w", encoding="utf-8") as log:
            subprocess.run(
                [source / "cacti", "-infile", cfg], cwd=source,
                stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120,
            )
        table["macros"][capacity] = read_macro(cfg.with_suffix(".cfg.out"), capacity)
    (output / "sram.json").write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
    print("CACTI_SRAM " + json.dumps(table, separators=(",", ":")), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    characterize(args.source, args.output)


if __name__ == "__main__":
    main()
