"""Packed membership must match the unpacked Boolean partial order exactly."""
import copy
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from accelforge.mapper.FFM._pareto_df import pareto
from accelforge.mapper.FFM._pareto_df.capacity_membership import (
    PREFIX, pack_exclusions, validate_membership, validate_same_membership,
    membership_for_target, expand_membership, booleanize_exclusions,
    is_membership_col, is_excluded_col,
)
from accelforge.mapper.FFM._pareto_df.df_convention import col_used_in_pareto, scaled_latency2col
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.mapper.FFM._join_pmappings.incremental_pareto import prepare_frontier_schema


def packed(excluded, **columns):
    n, k = excluded.shape
    fractions = [(i + 1) / k for i in range(k)]
    return pd.DataFrame({**columns, **pack_exclusions('GlobalBuffer', fractions, excluded, n)}), fractions


@pytest.mark.parametrize('k', [1, 63, 64, 65, 128, 129])
@pytest.mark.parametrize('n', [0, 11])
def test_word_roundtrip_and_high_bits(k, n):
    excluded = np.random.default_rng(k).integers(0, 2, (n, k)).astype(bool)
    frame, fractions = packed(excluded)
    assert len(validate_membership(frame)) == (k + 63) // 64
    for i, f in enumerate(fractions):
        np.testing.assert_array_equal(membership_for_target(frame, 'GlobalBuffer', f), ~excluded[:, i])
    expanded = expand_membership(frame)
    for i, f in enumerate(fractions):
        np.testing.assert_array_equal(expanded[f'Total<SEP>capacity_excluded<SEP>GlobalBuffer<SEP>{f!r}'], excluded[:, i])
    all_allowed = pd.DataFrame(pack_exclusions('GlobalBuffer', fractions, None, 1))
    if k >= 64:
        assert all_allowed.iloc[0, 0] == np.uint64(2**64 - 1)


@pytest.mark.parametrize('seed', [1, 31, 801])
@pytest.mark.parametrize('k', [3, 64, 65, 129])
def test_pareto_matches_boolean_oracle_with_boundaries_and_ties(monkeypatch, seed, k):
    rng = np.random.default_rng(seed)
    excluded = rng.random((120, k)) < .18
    excluded[-5:] = excluded[:5]
    costs = rng.integers(0, 8, (120, 3)).astype(np.float32)
    costs[-5:] = costs[:5]
    boundary = rng.integers(0, 3, 120)
    boundary[-5:] = boundary[:5]
    frame, _ = packed(excluded, **{'Total<SEP>energy': costs[:, 0], 'Total<SEP>latency': costs[:, 1],
                                 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right': costs[:, 2],
                                 'fused_loop<SEP>boundary': boundary, 'origin': np.arange(120)})
    frame.index = [7] * len(frame)  # selection must be positional, not index-label based.
    monkeypatch.setenv('AF_CAPACITY_MEMBERSHIP', 'counts')
    reference = pareto.makepareto(expand_membership(frame))
    result = expand_membership(pareto.makepareto(frame))
    pd.testing.assert_frame_equal(result[reference.columns], reference)
    assert prepare_frontier_schema(frame) is None


def test_superset_is_not_integer_order_and_equal_points_keep_first(monkeypatch):
    frame, _ = packed(np.array([[False, True], [True, False], [False, False], [False, False]]),
                      **{'Total<SEP>energy': [1., 1., 2., 2.], 'origin': ['a', 'b', 'c', 'tie']})
    result = pareto.makepareto(frame)
    assert result.origin.tolist() == ['a', 'b', 'c']
    frame['Total<SEP>energy'] = 1.
    assert pareto.makepareto(frame).origin.tolist() == ['c']
    one, _ = packed(np.zeros((2, 64), dtype=bool),
                    **{'Total<SEP>energy': np.array([2**60 + 1, 2**60], dtype=np.int64)})
    assert pareto.makepareto(one).index.tolist() == [1]


def test_invalid_schema_precision_and_tolerance_fail_closed(monkeypatch):
    frame, fractions = packed(np.zeros((2, 64), dtype=bool), **{'Total<SEP>energy': [1., 2.]})
    column = validate_membership(frame)[0]
    with pytest.raises(ValueError, match='uint64'):
        validate_membership(frame.astype({column: np.float64}))
    with pytest.raises(ValueError, match='lacks membership'):
        membership_for_target(frame, 'GlobalBuffer', .00001)
    different, _ = packed(np.zeros((2, 63), dtype=bool))
    with pytest.raises(ValueError, match='different'):
        validate_same_membership([frame, different])
    with pytest.raises(ValueError, match='mixed'):
        validate_membership(frame.assign(**{'Total<SEP>capacity_excluded<SEP>GlobalBuffer<SEP>1.0': 0.}))
    malformed = pd.DataFrame({PREFIX + 'invalid': np.array([0], dtype=np.uint64)})
    with pytest.raises(ValueError, match='schema'):
        validate_membership(malformed)
    with pytest.raises(ValueError, match='duplicate capacity'):
        pack_exclusions('GlobalBuffer', [.5, .5], None, 1)
    invalid_cost = frame.copy()
    invalid_cost['Total<SEP>energy'] = np.nan
    with pytest.raises(ValueError, match='finite'):
        pareto.makepareto(invalid_cost)
    with pytest.raises(ValueError, match='omit'):
        pareto.makepareto(frame, columns=['Total<SEP>energy'])
    with pytest.raises(ValueError, match='boundary key'):
        pareto.makepareto(frame, split_by_cols=[column])
    with pytest.raises(ValueError, match='different'):
        PmappingDataframe.concat([
            PmappingDataframe(frame, 2, 2, skip_pareto=True),
            PmappingDataframe(frame.drop(columns=column), 2, 2, skip_pareto=True),
        ])
    invalid_bits = different.copy()
    invalid_bits.iloc[0, 0] = np.uint64(2**63)
    with pytest.raises(ValueError, match='outside'):
        validate_membership(invalid_bits)
    monkeypatch.setattr(pareto, 'TOLERANCE', .01)
    with pytest.raises(ValueError, match='zero Pareto'):
        pareto.makepareto(frame)


def test_boolean_counts_reduce_by_zero_equivalence():
    a = 'Total<SEP>capacity_excluded<SEP>GlobalBuffer<SEP>0.5'
    b = 'Total<SEP>capacity_excluded<SEP>GlobalBuffer<SEP>1.0'
    frame = pd.DataFrame({a: [0., 2., 3.], b: [1., 0., 2.]})
    pd.testing.assert_frame_equal(booleanize_exclusions(frame), pd.DataFrame({a: [0., 1., 1.], b: [1., 0., 1.]}))
    assert frame[a].tolist() == [0., 2., 3.]  # no mutation of the input.


def test_resource_only_breakpoints_reject_target_specific_membership():
    from accelforge.mapper.FFM._join_pmappings.capacity_breakpoints import build_capacity_breakpoints
    frame, _ = packed(np.array([[False, True], [True, False]]),
                      **{'Total<SEP>energy': [1., 2.], 'Total<SEP>latency': [1., 2.], 'resource': [.1, .2]})
    for data in (frame, expand_membership(frame)):
        with pytest.raises(ValueError, match='declared-target'):
            build_capacity_breakpoints(data, 'resource', 1.)


@pytest.mark.parametrize('streaming,numeric', [('0', '0'), ('16', '0'), ('16', '1')])
def test_real_join_intersects_words_and_streaming_falls_back_safely(monkeypatch, streaming, numeric):
    # Repository-owned, trusted pickle, also used by the Streaming regressions.
    path = Path(__file__).parents[1] / 'streaming_join/fixtures/real_join_large_tag1.pkl'
    with path.open('rb') as handle:
        left, right, args, kwargs = copy.deepcopy(pickle.load(handle))
    left._data = left.data.iloc[:96].copy()
    rng = np.random.default_rng(7)
    words = []
    for side, name in ((left, 'left_origin'), (right, 'right_origin')):
        exclusions = rng.random((len(side.data), 65)) < .2
        metadata, _ = packed(exclusions)
        words.append(metadata)
        for column in metadata:
            side._data[column] = metadata[column].to_numpy()
        side._data[name] = np.arange(len(side.data))
    monkeypatch.setenv('AF_STREAMING_JOIN_PAIRS', streaming)
    monkeypatch.setenv('AF_NUMERIC_JOIN', numeric)
    monkeypatch.setenv('AF_PARTITIONED_FRONTIER', '1')
    result = left.merge_next(right, *args, **kwargs)
    assert len(result.data)
    for column in validate_membership(result.data):
        a = words[0][column].to_numpy()[result.data.left_origin.to_numpy(dtype=int)]
        b = words[1][column].to_numpy()[result.data.right_origin.to_numpy(dtype=int)]
        np.testing.assert_array_equal(result.data[column].to_numpy(), a & b)


def test_real_grid_preserves_each_targets_cost_frontier_and_mapping(monkeypatch):
    import common
    common.af.set_n_parallel_jobs(1)
    case = common.Case('matmuls', 'nvdla', (2, 4, 8))
    caps = [64 / 2**20, 128 / 2**20]
    results = {}
    for mode in ('counts', 'boolean', 'bitset', 'interval'):
        env = {**common.capacity_fractions_env(caps), 'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer',
               'AF_TARGET_ENUMERATION': 'events', 'AF_CAPACITY_MEMBERSHIP': mode,
               'AF_LATENCY_SCALES': 'GlobalBuffer:32,256'}
        result, _ = common.search(common.build(case, max(caps), common.RU), env,
                                  {'AF_VARIABLE_RESOURCES': 'GlobalBuffer', 'AF_CAPACITY_MEMBERSHIP': mode})
        results[mode] = result.data
        for cap in caps:
            fits = common.rows_for_capacity(result.data, cap, max(caps))
            for factor in (1., 32., 256.):
                latency = common.LATENCY if factor == 1 else scaled_latency2col('GlobalBuffer', factor)
                assert common.check_pick(case, cap, common.best_row(fits, latency),
                                         latency_col=latency, gb_latency_scale=factor)['ok']
    for cap in caps:
        projections = []
        for mode, data in results.items():
            fits = common.rows_for_capacity(data, cap, max(caps))
            cols = sorted(c for c in data.select_dtypes(include=['number', 'bool'])
                          if col_used_in_pareto(c) and not is_membership_col(c) and not is_excluded_col(c))
            projections.append(pareto.makepareto(fits[cols]).sort_values(cols).reset_index(drop=True))
        for projected in projections[1:]:
            pd.testing.assert_frame_equal(projected, projections[0])
    # Packed and unpacked Boolean semantics agree for the complete frontier too.
    a, b = expand_membership(results['bitset']), results['boolean']
    cols = sorted(c for c in b.select_dtypes(include=['number', 'bool']) if col_used_in_pareto(c))
    pd.testing.assert_frame_equal(a[cols].sort_values(cols).reset_index(drop=True),
                                  b[cols].sort_values(cols).reset_index(drop=True))
    c = expand_membership(results['interval'])
    pd.testing.assert_frame_equal(c[cols].sort_values(cols).reset_index(drop=True),
                                  b[cols].sort_values(cols).reset_index(drop=True))
