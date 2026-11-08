"""Characterize the SRAM macros used by the mixed-workload gate."""

import argparse
import csv
import json
import math
from pathlib import Path
import subprocess


CACTI_REVISION = "1ffd8dfb10303d306ecd8d215320aea07651e878"
TECH_NM = 45
CAPACITIES = (1024, 4096, 16384, 65536)


def word_bytes(capacity):
    return 8 if capacity <= 4096 else 64


def scratchpad_config(template, capacity, device="itrs-hp"):
    settings = {
        "-size (bytes)": str(capacity),
        "-block size (bytes)": str(word_bytes(capacity)),
        "-associativity": "1",
        "-read-write port": "0",
        "-exclusive read port": "1",
        "-exclusive write port": "1",
        "-UCA bank count": "1",
        "-technology (u)": "0.045",
        "-output/input bus width": str(8 * word_bytes(capacity)),
        "-cache type": '"ram"',
        "-Add ECC": '- "false"',
    }
    if device != "itrs-hp":
        for array in ("Data", "Tag"):
            for kind in ("cell", "peripheral"):
                settings[f"-{array} array {kind} type"] = f'- "{device}"'
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
        "Output width (bits)": 8 * word_bytes(capacity),
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
    return {"word_bytes": word_bytes(capacity), **macro}


def characterize(source, output, device="itrs-hp"):
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
        "read_ports": 1,
        "write_ports": 1,
        "macros": {},
    }
    if device != "itrs-hp":
        table["device"] = device
    binary = source / "cacti"
    if not binary.is_file():
        binary = binary.with_suffix(".exe")
    for capacity in CAPACITIES:
        cfg = output / f"sram_{capacity}.cfg"
        cfg.write_text(scratchpad_config(template, capacity, device), encoding="utf-8")
        log_path = cfg.with_suffix(".log")
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run(
                [binary, "-infile", cfg], cwd=source,
                stdout=log, stderr=subprocess.STDOUT, timeout=120,
            )
        if result.returncode:
            raise RuntimeError(f"CACTI failed for {capacity}:\n{log_path.read_text()[-2500:]}")
        table["macros"][capacity] = read_macro(cfg.with_suffix(".cfg.out"), capacity)
    (output / "sram.json").write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
    print("CACTI_SRAM " + json.dumps(table, separators=(",", ":")), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--device", choices=("itrs-hp", "itrs-lstp"), default="itrs-hp")
    args = parser.parse_args()
    characterize(args.source, args.output, args.device)


if __name__ == "__main__":
    main()
