"""Burst and command timing for one open-page DDR4-2400R x64 rank."""

from collections import deque
from dataclasses import dataclass


CK = 833  # ps, Ramulator DDR4_2400R preset
BURST = 4
CL, CWL = 16, 12
REFI, RFC = 9363, 421


@dataclass(frozen=True, slots=True)
class Command:
    cycle: int
    op: str
    group: int
    bank: int
    row: int
    address: int | None = None
    arrival_ps: int = 0


class DDR:
    """Issue FCFS column requests, with explicit open rows and refresh."""

    def __init__(self, record=False):
        self.trace = [] if record else None
        self.ca = 0
        self.dq = 0
        self.refresh_at = REFI
        self.row = [-1] * 16
        self.active = [-1000] * 16
        self.activate = deque([-1000] * 4, maxlen=4)
        self.group_act = [-1000] * 4
        self.precharge = [-1000] * 16
        self.close = [0] * 16
        self.read = self.write = -1000
        self.group_read = [-1000] * 4
        self.group_write = [-1000] * 4
        self.counts = dict.fromkeys(("ACT", "PREpb", "PREab", "RD", "WR", "REFab"), 0)

    def _emit(self, cycle, op, group=-1, bank=-1, row=-1, address=None, arrival=0):
        self.ca = cycle + 1
        self.counts[op] += 1
        if self.trace is not None:
            self.trace.append(Command(cycle, op, group, bank, row, address, arrival))

    def _refresh(self):
        # Start with enough slack to close every bank before the deadline.
        at = max(self.ca, self.refresh_at - 128)
        if any(row >= 0 for row in self.row):
            at = max(at, max(self.close))
            self._emit(at, "PREab")
            self.row[:] = [-1] * 16
            self.precharge[:] = [at] * 16
        at = max(at, max(self.precharge) + 16, self.activate[-1] + 55)
        assert at <= self.refresh_at
        self._emit(at, "REFab")
        self.ca = at + RFC
        self.refresh_at = at + REFI

    def burst(self, address, write, arrival_ps):
        """Return first and last data beat boundaries for one aligned 64-byte line."""
        arrival = (arrival_ps + CK - 1) // CK
        while max(arrival, self.ca) >= self.refresh_at - 128:
            self._refresh()
        stripe = address // 128
        group = stripe % 4
        bank = stripe // 4 % 4
        row = address // 2048  # 128 cache lines per bank row
        slot = 4 * group + bank
        at = max(arrival, self.ca)
        if self.row[slot] != row:
            if self.row[slot] >= 0:
                at = max(at, self.close[slot])
                self._emit(at, "PREpb", group, bank, self.row[slot])
                self.precharge[slot] = at
            at = max(self.ca, arrival, self.precharge[slot] + 16, self.active[slot] + 55,
                     self.activate[-1] + 4, self.group_act[group] + 6, self.activate[0] + 26)
            self._emit(at, "ACT", group, bank, row)
            self.row[slot] = row
            self.active[slot] = at
            self.group_act[group] = at
            self.activate.append(at)
            self.close[slot] = at + 39
        at = max(self.ca, arrival, self.active[slot] + 16)
        if write:
            at = max(at, self.dq - CWL, self.read + 10, self.write + 4,
                     self.group_write[group] + 6)
            self._emit(at, "WR", group, bank, row, address, arrival_ps)
            self.write = self.group_write[group] = at
            self.close[slot] = max(self.close[slot], at + CWL + BURST + 18)
        else:
            at = max(at, self.dq - CL, self.read + 4, self.group_read[group] + 6,
                     self.write + 19, self.group_write[group] + 25)
            self._emit(at, "RD", group, bank, row, address, arrival_ps)
            self.read = self.group_read[group] = at
            self.close[slot] = max(self.close[slot], at + 9)
        data = at + (CWL if write else CL)
        self.dq = data + BURST
        return data * CK, self.dq * CK
