"""Read-only summaries for terminal two-Einsum Join experiments.

These are additive partial-cost bounds only. They are not graph working-set
certificates and do not establish incumbent membership at another target.
"""
from dataclasses import dataclass
from fractions import Fraction
import math

import numpy as np

ENERGY = 'Total<SEP>energy'
LATENCY = 'Total<SEP>latency'


def _downward_float32(value):
    if not math.isfinite(value) or value < 0:
        raise ValueError('requires finite nonnegative objectives')
    with np.errstate(over='ignore',under='ignore',invalid='ignore'):
        value32 = np.float32(value)
        if not np.isfinite(value32):
            raise ValueError('float32 overflow')
        return max(0.,float(np.nextafter(value32,np.float32(-np.inf))))


def _downward_sum(left, right):
    a,b = _downward_float32(left),_downward_float32(right)
    with np.errstate(over='ignore',under='ignore',invalid='ignore'):
        total = np.float32(a)+np.float32(b)
    if not np.isfinite(total):
        raise ValueError('float32 sum overflow')
    return max(0.,float(np.nextafter(total,np.float32(-np.inf))))


@dataclass(frozen=True)
class BranchSummary:
    """Immutable lower-bound metadata; no input rows or mapping provenance."""
    left_rows: int
    right_rows: int
    shared_tensors: tuple[str, ...]
    matched_pairs: int | None
    energy_lower: Fraction | None
    latency_lower: Fraction | None
    working_set_lower_bits: int | None
    unsupported_reason: str | None

    @property
    def edp_lower(self):
        if self.energy_lower is None or self.latency_lower is None:
            return None
        return self.energy_lower * self.latency_lower

    @classmethod
    def from_frames(cls, left, right, shared_tensors=(), matched_pairs=None):
        """Build a terminal two-Einsum summary; unsupported data stays unknown."""
        try:
            mins = []
            for column in (ENERGY,LATENCY):
                values = []
                for frame in (left,right):
                    if column not in frame or not len(frame):
                        raise ValueError('missing objective or empty group')
                    if frame[column].dtype not in (np.dtype('float32'),np.dtype('float64')):
                        raise ValueError('unsupported objective dtype')
                    arr = frame[column].to_numpy()
                    if not np.isfinite(arr).all() or (arr<0).any():
                        raise ValueError('nonfinite or negative objective')
                    values.append(float(arr.min()))
                mins.append(Fraction.from_float(_downward_sum(*values)))
            return cls(len(left),len(right),tuple(sorted(map(str,shared_tensors))),matched_pairs,
                       mins[0],mins[1],None,None)
        except (TypeError,ValueError,OverflowError) as error:
            return cls(len(left),len(right),tuple(sorted(map(str,shared_tensors))),matched_pairs,
                       None,None,None,str(error))
