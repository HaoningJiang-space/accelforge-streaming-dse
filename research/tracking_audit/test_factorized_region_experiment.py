import copy
from unittest.mock import patch

import numpy as np
import pytest

from research.tracking_audit import benchmark_parametric_template as b
from research.tracking_audit import parametric_operator as op
from research.tracking_audit.benchmark_parametric_operator import FAMILY
from research.tracking_audit.factorized_region_experiment import CandidatePool, SharedEvaluationRegions
from research.tracking_audit.parametric_template import Box, RegionEnumerator
from research.tracking_audit.profile_parametric_factorization import ProfiledRegions


def test_pool_preserves_ids_order_and_dtype():
    pool = CandidatePool()
    a = np.array([[2, 1], [1, 2], [2, 1]], dtype=np.int64)
    assert pool.intern(('x', 'y'), a).tolist() == [0, 1, 0]
    assert pool.intern(('x', 'y'), a[::-1]).tolist() == [0, 1, 0]
    assert pool.intern(('x', 'y'), a.astype(np.float32)).tolist() == [2, 3, 2]
    assert pool.intern(('y', 'x'), a).tolist() == [4, 5, 4]
    assert pool.intern(('x', 'y'), a.astype(object)) is None


def test_profiler_preserves_region_results():
    b.common.af.set_n_parallel_jobs(1)
    b.common.clear_switches()
    program = op.prepare_all(256, tuple(hi for _,hi in FAMILY.ranges))[0]
    objectives, axes = b.parameterize(program)
    family = Box((*FAMILY.ranges[:2], tuple(8*x for x in FAMILY.ranges[2])))
    def build(cls):
        return cls(b.tiles, copy.deepcopy(objectives), family, axes=axes,
                   **copy.deepcopy(program.kwargs)).build()
    expected, actual = build(RegionEnumerator), build(ProfiledRegions)
    assert len(expected.leaves) == len(actual.leaves)
    for left, right in zip(expected.leaves, actual.leaves):
        assert left.targets == right.targets and left.history == right.history
        np.testing.assert_array_equal(left.choices, right.choices)
    for peak in actual.report()['depth_peaks']:
        assert peak['unique_prefix_rows'] <= peak['live_row_occurrences']


@pytest.mark.parametrize('index', [1, 3])
def test_cached_engine_preserves_every_region_and_order(index):
    b.common.af.set_n_parallel_jobs(1)
    b.common.clear_switches()
    program = op.prepare_all(256, tuple(hi for _,hi in FAMILY.ranges))[index]
    objectives, axes = b.parameterize(program)
    family = Box((*FAMILY.ranges[:2], tuple(8*x for x in FAMILY.ranges[2])))
    def build(cls):
        return cls(b.tiles, copy.deepcopy(objectives), family, axes=axes,
                   **copy.deepcopy(program.kwargs)).build()
    expected = build(RegionEnumerator)
    actual = build(SharedEvaluationRegions)
    assert len(actual.leaves) == len(expected.leaves)
    for left, right in zip(actual.leaves, expected.leaves):
        assert left.targets == right.targets
        assert left.history == right.history
        assert left.choices.dtype == right.choices.dtype
        np.testing.assert_array_equal(left.choices, right.choices)
    assert actual.cache_stats['hits'] > 0


def test_six_template_joint_frontier_at_every_execution_cell():
    b.common.af.set_n_parallel_jobs(1)
    b.common.clear_switches()
    programs = op.prepare_all(256, tuple(hi for _,hi in FAMILY.ranges))
    expected = op.CompiledOperator(programs, FAMILY)
    with patch.object(b, 'RegionEnumerator', SharedEvaluationRegions):
        actual = op.CompiledOperator(programs, FAMILY)
    assert len(expected.execution_cells) == 1382
    assert expected.execution_cells == actual.execution_cells
    for boxes in expected.execution_cells.values():
        for box in boxes:
            point = tuple((lo+hi)//2 for lo,hi in box.ranges)
            left, _ = expected.query(point)
            right, _ = actual.query(point)
            np.testing.assert_array_equal(left, right)
