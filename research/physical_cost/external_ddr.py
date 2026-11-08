"""Treat DDR bandwidth as a system condition and charge DRAM core transfers."""

import argparse
from dataclasses import replace
import json
from pathlib import Path

from research.physical_cost.banked_axes import AREA_CAPS, CASES, MAC_COUNTS, run
from research.physical_cost.banked_scale import WORKLOADS
from research.physical_cost.paid_area import Ledger


def core_pj_bit():
    """Incremental x8 DDR4 burst energy plus full-row ACT/PRE amortization."""
    # VDD rail from the DRAMPower DDR4 fixture. VDDQ I/O is priced separately.
    vdd, tck_ns, width = 1.2, 1 / 1.3, 8
    idd0, idd2n, idd3n, idd4r, idd4w = 56.25, 33.75, 39.5, 157.5, 135.0
    ras, rp, columns = 10, 10, 1024
    row_pj = vdd * tck_ns * ((idd0 - idd3n) * ras + (idd0 - idd2n) * rp)
    return tuple(vdd * tck_ns * (burst - idd3n) / (2 * width) + row_pj / (columns * width)
                 for burst in (idd4r, idd4w))


class SystemLedger(Ledger):
    def __init__(self, record):
        super().__init__(record, device_pj_bit=0)

    def price(self, hw):
        paid = super().price(hw)
        read, write = core_pj_bit()
        return replace(paid, ddr_area_mm2=0,
                       ddr_read_aj=paid.ddr_read_aj + round(512e6 * read),
                       ddr_write_aj=paid.ddr_write_aj + round(512e6 * write))

    def description(self):
        read, write = core_pj_bit()
        return {**super().description(), "ddr_area_external": True,
                "device_read_pj_bit": read, "device_write_pj_bit": write}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sram", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--bandwidth", nargs="+", type=int, choices=(8, 16, 32, 64), default=(16, 32, 64))
    parser.add_argument("--cases", nargs="+", choices=WORKLOADS, default=CASES)
    args = parser.parse_args()
    macros = {int(k): v for k, v in json.loads(args.sram.read_text())["macros"].items()}
    ledger = SystemLedger(json.loads(args.ledger.read_text()))
    caps = [ledger.reference_overhead() + area for area in AREA_CAPS]
    panels = {f"fixed_ddr_{rate}GBps": tuple((mac, 64 // rate) for mac in MAC_COUNTS)
              for rate in args.bandwidth}
    run(macros, caps, args.cases, args.output, ledger, panels)


if __name__ == "__main__":
    main()
