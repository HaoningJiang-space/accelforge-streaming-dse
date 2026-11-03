"""A model result is not itself a capacity-feasibility certificate."""
from types import SimpleNamespace

import pandas as pd
import pytest

import common


@pytest.mark.parametrize('reservation', [1.01, float('inf'), float('nan'), -.01])
def test_strict_evaluation_rejects_invalid_resource_usage(monkeypatch, reservation):
    spec = SimpleNamespace(model=SimpleNamespace(metrics=None), mapping=None)
    data = pd.DataFrame({'Total<SEP>energy': [1.], 'Total<SEP>latency': [2.],
                         'reservation<SEP>LocalBuffer<SEP>0<SEP>right': [reservation]})
    monkeypatch.setattr(common, 'build', lambda *args: spec)
    monkeypatch.setattr(common, 'evaluate_mapping', lambda _: SimpleNamespace(data=data))
    with pytest.raises(ValueError, match='reservation|Reservation'):
        common.strict_evaluate(common.DEFAULT_CASE, 1., object())


def test_strict_evaluation_accepts_exact_capacity(monkeypatch):
    spec = SimpleNamespace(model=SimpleNamespace(metrics=None), mapping=None)
    data = pd.DataFrame({'Total<SEP>energy': [1.], 'Total<SEP>latency': [2.],
                         common.GB: [1.]})
    monkeypatch.setattr(common, 'build', lambda *args: spec)
    monkeypatch.setattr(common, 'evaluate_mapping', lambda _: SimpleNamespace(data=data))
    assert common.strict_evaluate(common.DEFAULT_CASE, 1., object())['reservations'][common.GB] == 1.


def test_real_single_einsum_pick_cannot_pass_at_one_byte():
    # A single Einsum bypasses pairwise joins (and their capacity filtering).
    # It can therefore return costs and an overflowing Reservation as one row.
    common.af.set_n_parallel_jobs(1)
    case = common.Case('matmuls', 'nvdla', (1, 4, 8))
    result, _ = common.search(common.build(case, .125, common.EL))
    row = common.best_row(result.data)
    assert common.check_pick(case, .125, row)['ok']
    record = common.check_pick(case, 2**-20, row)
    assert not record['ok']
    assert 'GlobalBuffer' in record['error']
