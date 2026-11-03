"""Grid queries must keep only one capacity slice live during pre-warming."""
from types import SimpleNamespace
import weakref

import pandas as pd
import pytest

import grid_audit


def args(*extra):
    return grid_audit.parse_args(['2,4,8', '1,2', '1,2', '--workload', 'matmuls',
                                 '--arch', 'nvdla', *extra])


def test_warmup_does_not_collect_every_query_frame(monkeypatch):
    live = []
    peak = [0]
    calls = []

    def variant(*a):
        calls.append(a[0])
        if len(calls) > 1:
            # Only inspect the pre-warming stage; avoid synthetic timed runs.
            raise RuntimeError('warmup finished')
        for i in range(12):
            data = pd.DataFrame({'value': [i]})
            live.append(weakref.ref(data))
            peak[0] = max(peak[0], sum(r() is not None for r in live))
            yield (i, 1), data, 'latency', {}
            del data

    monkeypatch.setattr(grid_audit, 'run_variant', variant)
    with pytest.raises(RuntimeError, match='warmup finished'):
        grid_audit.run(args())
    assert peak[0] <= 2
    assert all(r() is None for r in live)


def test_capacity_slice_is_reused_across_factors(monkeypatch):
    gb = grid_audit.common.GB
    member = {grid_audit.common.capacity_excluded2col('GlobalBuffer', f): [0, 0] for f in (.5, 1.)}
    source = pd.DataFrame({gb: [.25, .75], 'Total<SEP>energy': [1., 2.], **member})
    searches = []

    def search(*a):
        searches.append(a)
        return SimpleNamespace(data=source), {'make_s': 1.}

    monkeypatch.setattr(grid_audit.common, 'build', lambda *a: object())
    monkeypatch.setattr(grid_audit.common, 'search', search)
    points = list(grid_audit.run_variant('shared', args().case, [1., 2.], [1., 2.]))
    assert len(searches) == 1
    assert [p[0] for p in points] == [(1., 1.), (1., 2.), (2., 1.), (2., 2.)]
    assert points[0][1] is points[1][1]
    assert points[2][1] is points[3][1]
    assert [len(p[1]) for p in points] == [1, 1, 2, 2]


def test_main_records_selected_case_and_cleans_up(monkeypatch):
    cases = []
    cleaned = []
    monkeypatch.setattr(grid_audit.common, 'effective_config',
                        lambda case=None, **kw: cases.append(case) or {})
    monkeypatch.setattr(grid_audit.common, 'set_jobs', lambda _: None)
    monkeypatch.setattr(grid_audit.common, 'shutdown_workers', lambda: cleaned.append(True))
    monkeypatch.setattr(grid_audit.common, 'peak_rss_gb', lambda: {})
    monkeypatch.setattr(grid_audit, 'run', lambda _: ({}, 0))
    assert grid_audit.main(['2,4,8', '1,2', '1,2', '--workload', 'matmuls', '--arch', 'nvdla']) == 0
    assert cases == [args().case]
    assert cleaned == [True]


def test_grid_does_not_transfer_picks_between_non_nested_capacity_mapspaces(monkeypatch):
    def variant(_variant, _case, caps, factors):
        for cap in caps:
            for factor in factors:
                yield ((cap, factor), pd.DataFrame({'Total<SEP>energy': [cap],
                                                    grid_audit.common.LATENCY: [factor]}),
                       grid_audit.common.LATENCY, {})

    monkeypatch.setattr(grid_audit, 'run_variant', variant)
    monkeypatch.setattr(grid_audit.common, 'check_pick', lambda _case, cap, _row, **kw: {
        'ok': True, 'edp': cap * kw['gb_latency_scale'], 'min_usage_shortfall': [],
    })
    summary, status = grid_audit.run(args('--no-warmup'))
    assert status == 0
    assert summary['all_picks_best_known']
