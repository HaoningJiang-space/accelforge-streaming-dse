"""Construct target membership from final cohorts without a row-by-target matrix."""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PackedMembership:
    """Allowed-target bits in ORIGINAL target order, before schema-label sorting."""
    words: np.ndarray
    n_targets: int

    def __post_init__(self):
        if (self.n_targets < 1 or self.words.ndim != 2
                or self.words.shape[1] != (self.n_targets + 63) // 64
                or self.words.dtype != np.dtype('uint64')):
            raise ValueError('invalid packed target membership shape or dtype')
        remainder = self.n_targets % 64
        if remainder and (self.words[:, -1] >> np.uint64(remainder)).any():
            raise ValueError('packed target membership has nonzero padding bits')


def build_target_membership(nrows, n_targets, memberships, output_format='excluded'):
    """Consume (row positions, target IDs) for each final cohort/reference part.

    The default Boolean output is the independent-enumeration oracle interface.
    The packed path allocates only N*ceil(K/64) words plus row/target index scratch;
    no N*K Boolean matrix is built. Duplicate rows/targets and overlapping cohorts
    combine by union. Empty rows and targets are valid entries.
    """
    if output_format not in ('excluded', 'packed'):
        raise ValueError('membership_format must be excluded or packed')
    if nrows < 0 or n_targets < 1:
        raise ValueError('nonnegative rows and positive target count required')
    if output_format == 'excluded':
        data = np.ones((nrows, n_targets), dtype=bool)
    else:
        data = np.zeros((nrows, (n_targets + 63) // 64), dtype=np.uint64)
    for rows, targets in memberships:
        rows = np.asarray(rows, dtype=np.intp)
        targets = np.asarray(targets, dtype=np.intp)
        if (rows.ndim != 1 or targets.ndim != 1 or (rows < 0).any()
                or (rows >= nrows).any() or (targets < 0).any() or (targets >= n_targets).any()):
            raise ValueError('membership row/target index outside the output shape')
        if output_format == 'excluded':
            data[np.ix_(rows, targets)] = False
        else:
            word_masks = {}
            for target in targets:
                word, bit = divmod(int(target), 64)
                word_masks[word] = word_masks.get(word, 0) | (1 << bit)
            for word, mask in word_masks.items():
                data[rows, word] |= np.uint64(mask)
    return PackedMembership(data, n_targets) if output_format == 'packed' else data
