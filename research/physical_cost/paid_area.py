"""Run the timing-class proof under a joint SRAM, MAC and DDR interface budget."""

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path

from research.physical_cost.banked_axes import AREA_CAPS, CASES, run
from research.physical_cost.banked_scale import DeepArchitecture, WORKLOADS, grid


@dataclass(frozen=True, order=True)
class PaidArchitecture(DeepArchitecture):
    mac_area_mm2: float = 0.0
    ddr_area_mm2: float = 0.0
    ddr_read_aj: int = DeepArchitecture.ddr_read_aj
    ddr_write_aj: int = DeepArchitecture.ddr_write_aj
    phy_idle_mw: float = 0.0

    def total_area_mm2(self, macros):
        return self.sram_totals(macros, "area_mm2") + self.mac_area_mm2 + self.ddr_area_mm2


class Ledger:
    def __init__(self, record, phy_scale=1.0, mac_scale=1.0, device_pj_bit=None):
        self.ports = {int(rate): value for rate, value in record["ddr_gb_s"].items()}
        self.mac_cell_mm2 = record["mac"]["area_um2"] / 1e6
        self.phy_scale = phy_scale
        self.mac_scale = mac_scale
        if device_pj_bit is None:
            port = self.ports[32]
            mean_link = (port["read_incremental_pj_bit"] + port["write_incremental_pj_bit"]) / 2
            # Preserve the previous 32-GB/s average active transfer price
            # where possible. The residual is an assumption, not a measurement.
            device_pj_bit = max(0, 7.03 - mean_link)
        self.device_pj_bit = device_pj_bit

    def description(self):
        return {"mac_cell_mm2": self.mac_cell_mm2, "mac_area_scale": self.mac_scale,
                "phy_area_scale": self.phy_scale, "device_pj_bit": self.device_pj_bit}

    def price(self, hw):
        port = self.ports[64 // hw.ddr_word_ns]
        return PaidArchitecture(
            **asdict(hw), mac_area_mm2=hw.x * hw.y * self.mac_cell_mm2 * self.mac_scale,
            ddr_area_mm2=(port["io_area_mm2"] + port["digital_phy_area_mm2"]) * self.phy_scale,
            ddr_read_aj=round(512e6 * (port["read_incremental_pj_bit"] + self.device_pj_bit)),
            ddr_write_aj=round(512e6 * (port["write_incremental_pj_bit"] + self.device_pj_bit)),
            phy_idle_mw=port["idle_mw"],
        )

    def grid(self, macros, cap, *, mac_count, ddr_word_ns):
        probe = self.price(DeepArchitecture(1, mac_count, 1, 16384, 1024, ddr_word_ns=ddr_word_ns))
        sram_cap = cap - probe.mac_area_mm2 - probe.ddr_area_mm2
        return tuple(hw for raw in grid(macros, sram_cap, mac_count=mac_count, ddr_word_ns=ddr_word_ns)
                     if (hw := self.price(raw)).total_area_mm2(macros) <= cap)

    def reference_overhead(self):
        reference = self.price(DeepArchitecture(32, 64, 4, 16384, 1024))
        return reference.mac_area_mm2 + reference.ddr_area_mm2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sram_table", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--caps", type=float, nargs="+")
    parser.add_argument("--cases", nargs="+", choices=WORKLOADS, default=CASES)
    parser.add_argument("--phy-scale", type=float, default=1.0)
    parser.add_argument("--mac-scale", type=float, default=1.0)
    parser.add_argument("--device-pj-bit", type=float)
    args = parser.parse_args()
    if min(args.phy_scale, args.mac_scale) <= 0 or (args.device_pj_bit is not None and args.device_pj_bit < 0):
        parser.error("Use positive area scales and a nonnegative DRAM device energy")
    record = json.loads(args.ledger.read_text())
    ledger = Ledger(record, args.phy_scale, args.mac_scale, args.device_pj_bit)
    caps = args.caps or [Ledger(record).reference_overhead() + sram for sram in AREA_CAPS]
    macros = {int(k): v for k, v in json.loads(args.sram_table.read_text())["macros"].items()}
    run(macros, caps, args.cases, args.output, ledger)


if __name__ == "__main__":
    main()
