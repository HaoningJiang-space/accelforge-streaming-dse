"""Dropping empty target intersections must preserve all live pair semantics."""
import copy
import importlib
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from accelforge.mapper.FFM._pareto_df.capacity_membership import pack_exclusions, validate_membership
from accelforge.mapper.FFM._pareto_df.df_convention import scaled_latency2col

frame_module = importlib.import_module('accelforge.mapper.FFM._join_pmappings.pmapping_dataframe')


@pytest.mark.parametrize('streaming,numeric', [('0', '0'), ('16', '0'), ('16', '1')])
@pytest.mark.parametrize('all_dead', [False, True])
def test_early_filter_matches_late_live_frontier_and_preserves_sources(monkeypatch, streaming, numeric, all_dead):
    fixture = Path(__file__).parents[1] / 'streaming_join/fixtures/real_join_large_tag1.pkl'
    with fixture.open('rb') as handle:
        snapshot = pickle.load(handle)
    left, right, args, kwargs = copy.deepcopy(snapshot)
    left._data = left.data.iloc[:96].copy()
    for side, name in ((left, 'left_origin'), (right, 'right_origin')):
        excluded = np.ones((len(side.data), 65), dtype=bool)
        bits = (np.arange(len(side.data)) % 2) * 64
        if name == 'right_origin' and all_dead:
            bits[:] = 1
        excluded[np.arange(len(side.data)), bits] = False
        for column, values in pack_exclusions('GlobalBuffer', [(i + 1) / 65 for i in range(65)], excluded, len(side.data)).items():
            side._data[column] = values
        side._data[name] = np.arange(len(side.data))
    monkeypatch.setenv('AF_STREAMING_JOIN_PAIRS', streaming)
    monkeypatch.setenv('AF_NUMERIC_JOIN', numeric)
    monkeypatch.setenv('AF_PARTITIONED_FRONTIER', '1')
    results, counts = {}, {}
    original = frame_module.intersect_join_membership
    for mode in ('late', 'early'):
        calls = []

        def measured(data, columns, **kw):
            before = len(data)
            result = original(data, columns, **kw)
            calls.append((before, len(result)))
            return result

        with monkeypatch.context() as m:
            m.setenv('AF_MEMBERSHIP_JOIN', mode)
            m.setattr(frame_module, 'intersect_join_membership', measured)
            a, b = copy.deepcopy((left, right))
            results[mode] = a.merge_next(b, *args, **kwargs).data
        counts[mode] = calls
    ref = results['late']
    words = validate_membership(ref)
    live = (ref[list(words)].to_numpy() != 0).any(axis=1)
    ref = ref[live].reset_index(drop=True)
    pd.testing.assert_frame_equal(results['early'].reset_index(drop=True), ref)
    assert sum(a - b for a, b in counts['early']) > 0
    assert all(a == b for a, b in counts['late'])
    assert (len(ref) == 0) == all_dead
    # A callback may inspect the complete table: the early path must reject it.
    with monkeypatch.context() as m:
        m.setenv('AF_MEMBERSHIP_JOIN', 'early')
        with pytest.raises(ValueError, match='arbitrary row callbacks'):
            a, b = copy.deepcopy((left, right))
            a.merge_next(b, *args, **{**kwargs, '_pmapping_row_filter_function': lambda data: np.ones(len(data), dtype=bool)})


def test_capacity_bandwidth_counterexample_keeps_all_target_answers(monkeypatch):
    import common
    from benchmark_membership import digest, semantic_frontiers
    common.af.set_n_parallel_jobs(1)
    case, caps = common.Case('matmuls', 'nvdla', (2, 4, 8)), [64 / 2**20, 128 / 2**20]
    queries = []
    for mode in ('late', 'early'):
        env = {**common.capacity_fractions_env(caps), 'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer',
               'AF_TARGET_ENUMERATION': 'events', 'AF_CAPACITY_MEMBERSHIP': 'bitset',
               'AF_LATENCY_SCALES': 'GlobalBuffer:32,256'}
        result, _ = common.search(common.build(case, max(caps), common.RU), env,
                                  {'AF_VARIABLE_RESOURCES': 'GlobalBuffer', 'AF_MEMBERSHIP_JOIN': mode})
        _, fronts = semantic_frontiers(result.data, caps)
        queries.append(digest(fronts))
        for cap in caps:
            fits = common.rows_for_capacity(result.data, cap, max(caps))
            for scale in (1., 32., 256.):
                col = common.LATENCY if scale == 1 else scaled_latency2col('GlobalBuffer', scale)
                assert common.check_pick(case, cap, common.best_row(fits, col),
                                         latency_col=col, gb_latency_scale=scale)['ok']
    assert queries[0] == queries[1]
