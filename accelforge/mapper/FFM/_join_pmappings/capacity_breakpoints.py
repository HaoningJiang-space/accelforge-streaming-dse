"""Final-frontier capacity queries for a fixed-cost, capacity-only scan."""
from dataclasses import dataclass
import hashlib
from numbers import Integral
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CapacityBreakpoints:
    requirements: np.ndarray
    edps: np.ndarray
    positions: np.ndarray
    capacity_scale: float | int
    mode: str
    snapshot_fingerprint: str
    source_id_column: str | None
    source_ids: tuple | None
    reservation_column: str
    model_id: str | None
    mapspace_id: str | None
    coverage_status: str

    def query(self, capacity):
        """Return (EDP, original row position); reject queries above the input range.

        A returned result is optimal only within the supplied candidate snapshot.
        Positions are valid only for that snapshot; use verify_snapshot before
        resolving them, or provide a stable source ID column when building.
        """
        if self.mode == 'exact_integer':
            if isinstance(capacity, (bool, np.bool_)) or not isinstance(capacity, Integral):
                raise ValueError('exact_integer queries require an integer capacity')
            if capacity < 0 or capacity > self.capacity_scale:
                raise ValueError('capacity is outside the generated range')
            threshold = int(capacity)
            info = np.iinfo(self.requirements.dtype)
            if threshold > info.max:
                i = len(self.requirements) - 1
                return None if i < 0 else (self.edps[i].item(), int(self.positions[i]))
            threshold = np.asarray(threshold, dtype=self.requirements.dtype)[()]
        else:
            if not np.isfinite(capacity) or capacity < 0 or capacity > self.capacity_scale:
                raise ValueError('capacity is outside the generated range')
            threshold = capacity / self.capacity_scale
            if self.requirements.dtype.kind == 'f' and self.requirements.dtype.itemsize < 8:
                threshold = np.asarray(threshold, dtype=self.requirements.dtype).item()
        i = np.searchsorted(self.requirements, threshold, side='right') - 1
        return None if i < 0 else (self.edps[i].item(), int(self.positions[i]))

    def query_source_id(self, capacity):
        if self.source_ids is None:
            raise ValueError('no stable source ID column was supplied')
        result = self.query(capacity)
        return None if result is None else (result[0], self.source_ids[result[1]])

    def verify_snapshot(self, data):
        """Check ordered query fields and stable IDs, not opaque Mapping objects."""
        if self.source_id_column is None:
            raise ValueError('stable source IDs are required for provenance verification')
        return self.snapshot_fingerprint == _fingerprint(data, self.reservation_column, self.source_id_column)


def _fingerprint(data, reservation, source_id_column):
    cols = [reservation, 'Total<SEP>energy', 'Total<SEP>latency']
    if source_id_column is not None:
        cols.append(source_id_column)
    # Order, values, and index are included; opaque provenance is external.
    hashes = pd.util.hash_pandas_object(data[cols], index=True).to_numpy(dtype=np.uint64)
    return hashlib.sha256(hashes.tobytes()).hexdigest()


def build_capacity_breakpoints(data, reservation, capacity_scale, *, mode='ffm_compatible',
                               source_id_column=None, model_id=None, mapspace_id=None,
                               coverage_status='unverified'):
    """Build from a completed Join with costs fixed across the scanned capacity.

    In exact_integer mode `reservation` must be an independently preserved,
    exact integer bit/byte requirement in the same units as capacity_scale and
    query values. Rounded normalized fractions cannot recover that information.
    This function does not certify that the supplied candidates cover the space.
    """
    from accelforge.mapper.FFM._pareto_df.capacity_membership import is_membership_col, is_excluded_col
    if any(is_membership_col(c) or is_excluded_col(c) for c in data):
        raise ValueError('target-specific membership requires declared-target queries, not resource-only breakpoints')
    if mode not in ('ffm_compatible', 'exact_integer'):
        raise ValueError('unknown capacity comparison mode')
    if mode == 'exact_integer':
        if isinstance(capacity_scale, (bool, np.bool_)) or not isinstance(capacity_scale, Integral) or capacity_scale <= 0:
            raise ValueError('exact_integer capacity_scale must be a positive integer')
        scale = int(capacity_scale)
    else:
        if not np.isfinite(capacity_scale) or capacity_scale <= 0:
            raise ValueError('capacity_scale must be finite and positive')
        scale = float(capacity_scale)
    requirements = data[reservation].to_numpy()
    energy = data['Total<SEP>energy'].to_numpy()
    latency = data['Total<SEP>latency'].to_numpy()
    if any(a.dtype.kind not in 'biuf' for a in (requirements, energy, latency)):
        raise ValueError('requirements and costs must be numeric')
    # Costs are compared as float64. A fixed-width integer product could wrap around
    # (2**32 * 2**32 == 0 in uint64), so integer costs must fit a float64 exactly.
    for name, a in (('energy', energy), ('latency', latency)):
        if a.dtype.kind in 'iu' and len(a) and (np.abs(a) > 2**53).any():
            raise ValueError(f'integer {name} exceeds exact float range')
    energy, latency = energy.astype(np.float64), latency.astype(np.float64)
    edps = energy * latency
    if mode == 'exact_integer':
        if requirements.dtype.kind not in 'iu':
            raise ValueError('exact_integer requires a preserved integer requirement column')
        if len(requirements) and ((requirements < 0).any() or (requirements > scale).any()):
            raise ValueError('integer requirements are outside the generated range')
    elif requirements.dtype.kind in 'iu':
        if len(requirements) and (requirements > 2**53).any():
            raise ValueError('integer reservation exceeds exact float range')
        requirements = requirements.astype(np.float64)
    if any(not np.isfinite(a).all() or (a < 0).any() for a in (requirements, energy, latency, edps)):
        raise ValueError('requirements and costs must be finite and nonnegative')
    if source_id_column is not None:
        ids = data[source_id_column]
        if ids.isna().any() or ids.duplicated().any():
            raise ValueError('source IDs must be non-null and unique')
        source_ids = tuple(ids.tolist())
    else:
        source_ids = None
    order = np.argsort(requirements, kind='stable')
    selected, best = [], float('inf')
    for i in order:
        if edps[i] < best:
            best = edps[i]
            if selected and requirements[selected[-1]] == requirements[i]:
                selected[-1] = i
            else:
                selected.append(i)
    selected = np.asarray(selected, dtype=np.int64)
    return CapacityBreakpoints(requirements[selected], edps[selected], selected, scale, mode,
        _fingerprint(data, reservation, source_id_column), source_id_column, source_ids,
        reservation, model_id, mapspace_id, coverage_status)
