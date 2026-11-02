"""Exact final-frontier capacity queries for the fixed-cost GLB scan only."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class CapacityBreakpoints:
    # Requirements use the same normalized units as the input reservation.
    requirements: np.ndarray
    edps: np.ndarray
    positions: np.ndarray
    capacity_scale: float

    def query(self, capacity):
        """Return (EDP, original positional row) or None if no mapping fits."""
        if not np.isfinite(capacity) or capacity < 0:
            raise ValueError('capacity must be finite and nonnegative')
        # Pandas/NumPy compare float32 Series against a Python scalar after
        # rounding that scalar to the Series dtype. Preserve that boundary.
        threshold = capacity / self.capacity_scale
        if self.requirements.dtype.kind == 'f' and self.requirements.dtype.itemsize < 8:
            threshold = np.asarray(threshold, dtype=self.requirements.dtype).item()
        i = np.searchsorted(self.requirements, threshold, side='right') - 1
        return None if i < 0 else (self.edps[i].item(), int(self.positions[i]))


def build_capacity_breakpoints(data, reservation, capacity_scale):
    """Build only after the full Join, when energy*latency is the objective.

    Costs must be independent of the scanned capacity. This function does not
    establish candidate-space coverage or evaluate the returned mappings.
    """
    if not np.isfinite(capacity_scale) or capacity_scale <= 0:
        raise ValueError('capacity_scale must be finite and positive')
    requirements = data[reservation].to_numpy()
    energy = data['Total<SEP>energy'].to_numpy()
    latency = data['Total<SEP>latency'].to_numpy()
    # Match the final FFM objective calculation, including pandas dtype rules.
    edps = (data['Total<SEP>energy'] * data['Total<SEP>latency']).to_numpy()
    if any(a.dtype.kind not in 'biuf' for a in (requirements, energy, latency, edps)):
        raise ValueError('requirements and costs must be numeric')
    if requirements.dtype.kind in 'iu':
        if len(requirements) and (requirements > 2**53).any():
            raise ValueError('integer reservation exceeds exact float range')
        requirements = requirements.astype(np.float64)
    if any(not np.isfinite(a).all() or (a < 0).any() for a in (requirements, energy, latency, edps)):
        raise ValueError('requirements and costs must be finite and nonnegative')
    order = np.argsort(requirements, kind='stable')
    selected = []
    best = float('inf')
    for i in order:
        if edps[i] < best:
            best = edps[i]
            if selected and requirements[selected[-1]] == requirements[i]:
                selected[-1] = i
            else:
                selected.append(i)
    selected = np.asarray(selected, dtype=np.int64)
    return CapacityBreakpoints(requirements[selected], edps[selected], selected, float(capacity_scale))
