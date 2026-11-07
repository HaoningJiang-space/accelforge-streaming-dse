"""Compile and independently replay storage and port events for a row-local DAG."""

from collections import Counter
from dataclasses import dataclass
from itertools import product

from research.runtime.dag_model import lifetimes, validate_plan
from research.runtime.strip_codesign import COMPUTE, DRAM, GB_READ, GB_WRITE
from research.runtime.strip_overlap import Calendar, RATES


@dataclass(frozen=True)
class Event:
    kind: str
    name: str
    band: range = range(0)
    inner: range = range(0)
    columns: range = range(0)
    overlap: bool = False


class CheckedCalendar(Calendar):
    """Audit the actual intervals booked by the calendar after each transaction."""

    def __init__(self):
        super().__init__()
        self.slots = []
        self.previous = 0
        self.verified_overlap = 0

    def reserve(self, port, start, elapsed, actions):
        super().reserve(port, start, elapsed, actions)
        self.slots.append((port, start, start + elapsed, actions))

    def check(self):
        ends = {}
        for port, start, stop, words in self.slots:
            if start < ends.get(port, self.previous) or stop > self.now or stop - start < words * RATES[port]:
                raise AssertionError(f"invalid physical {port} interval")
            ends[port] = stop
        if max(ends.values()) != self.now:
            raise AssertionError("calendar does not end at the last completion")
        self.previous = self.now

    def transfer(self, words, direction):
        super().transfer(words, direction)
        self.check()
        source, target = self.slots
        if source[0] != "dram" or target[0] != direction or source[1:] != target[1:] or source[3] != words:
            raise AssertionError("DMA endpoints disagree")
        self.slots.clear()

    def rf_fill(self, words):
        super().rf_fill(words)
        self.check()
        if len(self.slots) != 1 or self.slots[0][0] != "read" or self.slots[0][3] != words:
            raise AssertionError("invalid RF fill interval")
        self.slots.clear()

    def wave(self, rows, k, n, prior, overlap):
        wave_start = self.previous
        super().wave(rows, k, n, prior, overlap)
        self.check()
        last_write = wave_start
        did_overlap = False
        for read, mac, write in zip(self.slots[::3], self.slots[1::3], self.slots[2::3], strict=True):
            if ((read[0], mac[0], write[0]) != ("read", "mac", "write")
                    or read[2] > mac[1] or mac[2] > write[1]
                    or (read[3], mac[3], write[3]) != (k + n * prior, 1, n)):
                raise AssertionError("invalid read/compute/write dependency")
            did_overlap |= read[1] < last_write
            last_write = write[2]
        if len(self.slots) != 3 * rows or (did_overlap and not overlap):
            raise AssertionError("calendar overlaps rows without SRAM staging")
        self.verified_overlap += did_overlap
        self.slots.clear()


def intervals(extent, step):
    for start in range(0, extent, step):
        yield range(start, min(extent, start + step))


def events(graph, hardware, plan):
    validate_plan(graph, hardware, plan)
    for group in plan:
        pins = {name for name, pin in zip(group.order, group.pinned) if pin}
        pinned_words = sum(graph.weight_words(graph.operators[name]) for name in pins)
        for name in group.order:
            if name in pins:
                yield Event("pin", name)
        profile = tuple(lifetimes(graph, group.order))
        for band in intervals(graph.rows, group.rows):
            for stage, (p, q) in zip(profile, group.tiles):
                op = stage.op
                for name in stage.fetch:
                    yield Event("fetch", name, band)
                yield Event("allocate", op.name, band)
                live = pinned_words + len(band) * stage.live_width
                if live > hardware.capacity_bytes:
                    raise ValueError("live activations and pinned weights exceed SRAM")
                for cols in intervals(op.width, q):
                    if op.kind == "gemm":
                        for inner in intervals(graph.widths[op.inputs[0]], p):
                            scratch = 0 if op.name in pins else len(inner) * len(cols)
                            used = live + scratch
                            if used > hardware.capacity_bytes:
                                raise ValueError("streamed weight tile exceeds SRAM")
                            staging = len(inner) + (2 if inner.start else 1) * len(cols)
                            overlap = len(band) > 1 and used + staging <= hardware.capacity_bytes
                            yield Event("gemm", op.name, band, inner, cols, overlap)
                    else:
                        overlap = len(band) > 1 and live + 3 * len(cols) <= hardware.capacity_bytes
                        yield Event(op.kind, op.name, band, columns=cols, overlap=overlap)
                if stage.drain:
                    yield Event("drain", op.name, band)
                for name in stage.release:
                    yield Event("release", name, band)
        for name in group.order:
            if name in pins:
                yield Event("unpin", name)


def initial_value(name, i, j):
    return (sum(map(ord, name)) + 17 * i + 13 * j) % 256


def scalar_graph(graph):
    """Independent numeric reference for small microbenchmarks."""
    values = {name: {(i, j): initial_value(name, i, j) for i, j in product(range(graph.rows), range(width))}
              for name, width in graph.inputs}
    for op in graph.ops:
        if op.kind == "gemm":
            source = op.inputs[0]
            values[op.name] = {(i, j): sum(values[source][i, k] * initial_value(op.name, k, j)
                                          for k in range(graph.widths[source])) % 256
                               for i, j in product(range(graph.rows), range(op.width))}
        else:
            a, b = (values[name] for name in op.inputs)
            if op.kind == "add":
                values[op.name] = {point: (a[point] + b[point]) % 256 for point in a}
            else:
                values[op.name] = {point: (a[point] * b[point]) % 256 for point in a}
    return {name: values[name] for name in graph.outputs}


def replay(graph, hardware, schedule, numeric=False):
    """Check address versions, local SRAM ownership and exclusive port intervals."""
    cal = CheckedCalendar()
    counts = Counter()
    resident = {}
    pinned = {}
    produced = Counter()
    stored = {name: (1 << graph.rows) - 1 for name, _ in graph.inputs}
    host = {}
    if numeric:
        host = {name: {(r, c): initial_value(name, r, c) for r, c in product(range(graph.rows), range(w))}
                for name, w in graph.inputs}
    values, coverage = {}, {}
    peak = 0

    def live(scratch=0):
        nonlocal peak
        used = sum(len(band) * graph.widths[name] for name, band in resident.items())
        used += sum(pinned.values()) + scratch
        peak = max(peak, used)
        if used > hardware.capacity_bytes:
            raise ValueError("address replay exceeds SRAM capacity")

    def bitrows(band):
        return ((1 << len(band)) - 1) << band.start

    def allocate(name, band):
        if name in resident:
            raise ValueError("duplicate SRAM allocation")
        resident[name] = band
        coverage[name] = [0] * graph.widths[name]
        live()

    def ready(name, band):
        if resident.get(name) != band or any(part != -1 for part in coverage[name]):
            raise ValueError(f"read of unavailable tensor {name}")

    def dma(name, words, direction):
        counts["dram", name, "read" if direction == "write" else "write"] += words
        counts[direction, name, direction] += words
        cal.transfer(words, direction)

    for event in schedule:
        kind, name, band, ks, ns = event.kind, event.name, event.band, event.inner, event.columns
        if kind == "pin":
            if name in pinned or resident:
                raise ValueError("weight pin overlaps a live activation or duplicate pin")
            pinned[name] = graph.weight_words(graph.operators[name])
            if not pinned[name]:
                raise ValueError("cannot pin a pointwise operator")
            live()
            dma("W:" + name, pinned[name], "write")
            continue
        if kind == "unpin":
            if resident or name not in pinned:
                raise ValueError("invalid weight lifetime")
            del pinned[name]
            continue
        if not 0 <= band.start < band.stop <= graph.rows or band.step != 1:
            raise ValueError("invalid activation row interval")
        width = graph.widths[name]
        words = len(band) * width
        if kind == "fetch":
            mask = bitrows(band)
            if stored.get(name, 0) & mask != mask:
                raise ValueError(f"DRAM use before writeback for {name}")
            allocate(name, band)
            coverage[name][:] = [-1] * width
            if numeric:
                values[name] = {(r, c): host[name][r, c] for r, c in product(band, range(width))}
            dma(name, words, "write")
        elif kind == "allocate":
            if name not in graph.operators or produced[name] & bitrows(band):
                raise ValueError("output rows have already been computed")
            allocate(name, band)
            if numeric:
                values[name] = {}
        elif kind == "drain":
            ready(name, band)
            mask = bitrows(band)
            if stored.get(name, 0) & mask:
                raise ValueError("duplicate DRAM writeback")
            stored[name] = stored.get(name, 0) | mask
            if numeric:
                host.setdefault(name, {}).update(values[name])
            dma(name, words, "read")
        elif kind == "release":
            ready(name, band)
            del resident[name], coverage[name]
            if numeric:
                del values[name]
        else:
            op = graph.operators[name]
            if (kind != op.kind or resident.get(name) != band or ns.step != 1
                    or not 0 <= ns.start < ns.stop <= width):
                raise ValueError("invalid compute event")
            for source in op.inputs:
                ready(source, band)
            if kind == "gemm":
                source = op.inputs[0]
                k = graph.widths[source]
                if (ks.step != 1 or not 0 <= ks.start < ks.stop <= k
                        or any(coverage[name][j] != ks.start for j in ns)):
                    raise ValueError("overlapping, missing or uninitialized partial sum")
                if len(ks) > hardware.py or len(ns) > hardware.px:
                    raise ValueError("physical GEMM wave fanout exceeded")
                wave = len(ks) * len(ns)
                scratch = 0 if name in pinned else wave
                if name not in pinned:
                    dma("W:" + name, wave, "write")
                counts["read", "W:" + name, "read"] += wave
                counts["rf", "W:" + name, "write"] += wave
                counts["rf", "W:" + name, "read"] += wave * len(band)
                cal.rf_fill(wave)
                read_inputs = len(ks)
                counts["read", source, "read"] += len(band) * len(ks)
                if ks.start:
                    counts["read", name, "read"] += len(band) * len(ns)
                if numeric:
                    for r, j in product(band, ns):
                        initial = values[name][r, j] if ks.start else 0
                        values[name][r, j] = (initial + sum(values[source][r, x] * initial_value(name, x, j)
                                                           for x in ks)) % 256
                for j in ns:
                    coverage[name][j] = -1 if ks.stop == k else ks.stop
                operations = wave * len(band)
            else:
                if len(ns) > hardware.px * hardware.py or any(coverage[name][j] for j in ns):
                    raise ValueError("duplicate or oversized pointwise wave")
                scratch, read_inputs = 0, 2 * len(ns)
                for source in op.inputs:
                    counts["read", source, "read"] += len(band) * len(ns)
                if numeric:
                    a, b = (values[x] for x in op.inputs)
                    for point in product(band, ns):
                        values[name][point] = (a[point] + b[point] if kind == "add" else a[point] * b[point]) % 256
                for j in ns:
                    coverage[name][j] = -1
                operations = len(band) * len(ns)
            prior = bool(ks.start)
            staging = read_inputs + len(ns) * (1 + prior)
            live(scratch + (staging if event.overlap else 0))
            counts["write", name, "write"] += len(band) * len(ns)
            counts["mac", name, "cycles"] += len(band)
            counts["ops", name, "compute"] += operations
            cal.wave(len(band), read_inputs, len(ns), prior, event.overlap)
            if all(x == -1 for x in coverage[name]):
                produced[name] |= bitrows(band)

    complete = (1 << graph.rows) - 1
    if resident or pinned or any(produced[op.name] != complete for op in graph.ops):
        raise ValueError("unfinished compute or SRAM lifetime")
    if any(stored.get(name, 0) != complete for name in graph.outputs):
        raise ValueError("missing output writeback")
    if numeric and {name: host[name] for name in graph.outputs} != scalar_graph(graph):
        raise AssertionError("DAG numeric replay differs from scalar reference")
    totals = Counter()
    for (level, _, _), count in counts.items():
        totals[level] += count
    if any(cal.words[level] != totals[level] for level in RATES):
        raise AssertionError("address replay does not conserve port actions")
    energy = (totals["dram"] * DRAM[0] + totals["read"] * GB_READ[0]
              + totals["write"] * GB_WRITE[0] + totals["ops"] * COMPUTE[0])
    service = {level: totals[level] * rate for level, rate in RATES.items()}
    if cal.now < max(service.values()) or cal.verified_overlap != cal.overlapped_waves:
        raise AssertionError("schedule exceeds a physical port")
    return dict(energy=energy, ticks=cal.now, peak_bytes=peak, service_ticks=service,
                overlapped_waves=cal.overlapped_waves,
                actions={"/".join(key): value for key, value in sorted(counts.items())})
