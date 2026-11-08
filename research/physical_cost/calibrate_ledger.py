"""Create the paid area and DDR transfer ledger from local synthesis and CACTI I/O."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

from research.physical_cost.cacti_sram import CACTI_REVISION


LIBERTY_REVISION = "9ca2a9e76b5608f71dd04db8c72ad92f54bdd132"
LIBERTY_SHA = "8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1"
GATES = {"$_AND_": ("AND2_X1",), "$_OR_": ("OR2_X1",), "$_NOT_": ("INV_X1",),
         "$_XOR_": ("XOR2_X1",), "$_XNOR_": ("XNOR2_X1",), "$_MUX_": ("MUX2_X1",),
         "$_ANDNOT_": ("AND2_X1", "INV_X1"), "$_ORNOT_": ("OR2_X1", "INV_X1")}
CHANNELS = {8: (1, 32, 1000), 16: (1, 64, 1000), 32: (2, 64, 1000), 64: (5, 32, 1600)}
# Digital PHY to I/O ratio from Sudarshan et al.'s DDR3 controller (Table 8.1).
DIGITAL_PHY_RATIO = 0.551 / 3.820


def mac_area(netlist, liberty):
    library_bytes = liberty.read_bytes()
    if sha256(library_bytes).hexdigest() != LIBERTY_SHA:
        raise ValueError("Use the pinned Nangate45 typical library")
    library = library_bytes.decode()
    areas = {}
    starts = list(re.finditer(r"\bcell\s*\(\s*([^\s)]+)\s*\)\s*\{", library))
    for i, match in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(library)
        area = re.search(r"\barea\s*:\s*([\d.]+)", library[match.end():end])
        if area:
            areas[match[1]] = float(area[1])
    synthesis = json.loads(netlist.read_text())
    counts = Counter()
    for cell in synthesis["modules"]["mac_int8"]["cells"].values():
        counts.update(GATES.get(cell["type"], (cell["type"],)))
    return {"area_um2": sum(areas[name] * n for name, n in counts.items()),
            "cell_counts": dict(sorted(counts.items())), "creator": synthesis["creator"]}


def io_table(probe):
    records = {}
    for bandwidth, (channels, lanes, clock) in CHANNELS.items():
        if channels * lanes * 2 * clock != bandwidth * 8000:
            raise AssertionError("DDR service does not match the channel configuration")
        output = subprocess.check_output([str(probe.resolve()), str(lanes), str(clock)], text=True)
        fields = {}
        for label in ("IO Area (sq.mm)", "IO Dynamic Power (mW)", "IO Termination and Bias Power (mW)",
                      "PHY Power (mW)"):
            fields[label] = list(map(float, re.findall(re.escape(label) + r"\s*=\s*([\deE.+-]+)", output)))
        area, = fields.pop("IO Area (sq.mm)")
        if any(len(values) != 3 for values in fields.values()):
            raise ValueError("Expected complete CACTI read, write and idle measurements")
        read, write, idle = [channels * sum(group) for group in zip(*fields.values(), strict=True)]
        area *= channels
        records[bandwidth] = {
            "channels": channels, "dq_per_channel": lanes, "clock_mhz": clock,
            "io_area_mm2": area, "digital_phy_area_mm2": area * DIGITAL_PHY_RATIO,
            "read_mw": read, "write_mw": write, "idle_mw": idle,
            "read_incremental_pj_bit": (read - idle) / (8 * bandwidth),
            "write_incremental_pj_bit": (write - idle) / (8 * bandwidth),
        }
        if not (read > idle and write > idle >= 0 and area > 0):
            raise ValueError("Nonphysical I/O characterization")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    parser.add_argument("liberty", type=Path)
    parser.add_argument("probe", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    record = {"cacti_revision": CACTI_REVISION, "liberty_revision": LIBERTY_REVISION,
              "liberty_sha256": LIBERTY_SHA, "mac": mac_area(args.netlist, args.liberty),
              "ddr_gb_s": io_table(args.probe)}
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
