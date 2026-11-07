"""Schedule dense strip mapping transfers on shared and independent ports."""

from collections import Counter
from dataclasses import dataclass, field

from research.runtime.strip_codesign import COMPUTE, DRAM, GB_READ, GB_WRITE, evaluate
from research.runtime.strip_native_timing import shape_classes
from research.runtime.strip_trace import replay


RATES = {"dram": DRAM[1], "read": GB_READ[1], "write": GB_WRITE[1], "mac": COMPUTE[1]}


@dataclass
class Calendar:
    now: int = 0
    end: dict = field(default_factory=dict)
    words: Counter = field(default_factory=Counter)
    overlapped_waves: int = 0
    overlapped_ticks: int = 0

    def reserve(self, port, start, elapsed, actions):
        if start < self.end.get(port, 0) or elapsed < RATES[port] * actions:
            raise AssertionError(f"illegal {port} reservation")
        self.end[port] = start + elapsed
        self.words[port] += actions

    def transfer(self, words, direction):
        # A DMA stream occupies both ends for the slower port's time.
        delay = max(RATES["dram"], RATES[direction]) * words
        self.reserve("dram", self.now, delay, words)
        self.reserve(direction, self.now, delay, words)
        self.now += delay

    def rf_fill(self, words):
        duration = RATES["read"] * words
        self.reserve("read", self.now, duration, words)
        self.now += duration

    def wave(self, rows, k, n, prior, overlap):
        reads = k + n * prior
        a, b, c = reads * RATES["read"], RATES["mac"], n * RATES["write"]
        serial = a + b + c
        period = max(a, b, c) if overlap else serial
        if period < serial and rows > 1:
            self.overlapped_waves += 1
            self.overlapped_ticks += (rows - 1) * (serial - period)
        # The interval shifts make the read -> compute -> write precedence
        # explicit. At most one row of input and one output are in staging.
        for row in range(rows):
            start = self.now + row * period
            self.reserve("read", start, a, reads)
            self.reserve("mac", start + a, b, 1)
            self.reserve("write", start + a + b, c, n)
        self.now += (rows - 1) * period + serial


def tiles(extent, width):
    for size, repetitions in shape_classes(extent, width):
        yield from (size for _ in range(repetitions))


def audit(rows, widths, hardware, plan):
    """Check every port interval and conserve the independently counted traffic."""
    _, wave_peak, words = replay(rows, widths, hardware, plan)
    ledger = Calendar()
    calendar_peak = wave_peak
    for segment in plan:
        resident = 0
        for i, pin in enumerate(segment.pinned, segment.start):
            if pin:
                weight = widths[i] * widths[i+1]
                ledger.transfer(weight, "write")
                resident += weight
        for band in tiles(rows, segment.rows):
            ledger.transfer(band * widths[segment.start], "write")
            for i, ((p, q), pin) in enumerate(zip(segment.tiles, segment.pinned), segment.start):
                k, n = widths[i], widths[i+1]
                live = resident + band * (k + n)
                for no in tiles(n, q):
                    for step, ki in enumerate(tiles(k, p)):
                        wave = ki * no
                        used = live + (0 if pin else wave)
                        # Separate one-row ingress and egress staging, charged
                        # to SRAM. The first reduction wave has no prior sum.
                        staging = ki + (2 if step else 1) * no
                        overlap = band > 1 and used + staging <= hardware.capacity_bytes
                        calendar_peak = max(calendar_peak, used + (staging if overlap else 0))
                        if not pin:
                            ledger.transfer(wave, "write")
                        ledger.rf_fill(wave)
                        ledger.wave(band, ki, no, bool(step), overlap)
            ledger.transfer(band * widths[segment.stop], "read")
    expected = Counter()
    for (_, level, _, direction), count in words.items():
        if level == "DRAM":
            expected["dram"] += count
        elif level == "SRAM":
            expected[direction] += count
    expected["mac"] = sum(rows * ((widths[i] + p - 1) // p) * ((widths[i+1] + q - 1) // q)
                          for segment in plan for i, (p, q) in enumerate(segment.tiles, segment.start))
    if ledger.words != expected:
        raise AssertionError("port calendar and independent transfer volumes differ")
    service = {port: count * RATES[port] for port, count in expected.items()}
    _, serial = evaluate(rows, widths, hardware, plan)[0]
    if not max(service.values()) <= ledger.now <= serial:
        raise AssertionError("invalid port schedule bounds")
    return dict(service_ticks=service, end_ticks=ledger.now, serial_ticks=serial,
                peak_bytes=calendar_peak, overlapped_waves=ledger.overlapped_waves,
                overlapped_ticks=ledger.overlapped_ticks)
