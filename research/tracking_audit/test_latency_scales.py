"""AF_LATENCY_SCALES parsing and bandwidth-scenario quality accounting (no search)."""
from types import SimpleNamespace

import pytest

import common
from accelforge.frontend.mapper.metrics import Metrics
from accelforge.mapper.FFM._make_pmappings.make_pmappings import _latency_scales_from_env
from accelforge.mapper.FFM._pareto_df.df_convention import is_objective_col, scaled_latency2col

EL = Metrics.ENERGY | Metrics.LATENCY


def jobs(leak_power=0):
    arch = [SimpleNamespace(name='MainMemory', leak_power=0),
            SimpleNamespace(name='GlobalBuffer', leak_power=leak_power)]
    return {'E': [SimpleNamespace(flattened_arch=arch)]}


def parse(monkeypatch, value, metrics=EL, leak_power=0):
    monkeypatch.setenv('AF_LATENCY_SCALES', value)
    return _latency_scales_from_env(jobs(leak_power), metrics)


def test_unset_means_no_scenarios(monkeypatch):
    monkeypatch.delenv('AF_LATENCY_SCALES', raising=False)
    assert _latency_scales_from_env(jobs(), EL) == ()


def test_factors_are_parsed_in_order(monkeypatch):
    assert parse(monkeypatch, 'GlobalBuffer:0.5, 2') == (('GlobalBuffer', 0.5), ('GlobalBuffer', 2.0))


@pytest.mark.parametrize('value', ['GlobalBuffer', 'GlobalBuffer:', 'GlobalBuffer:x', 'GlobalBuffer:0',
                                   'GlobalBuffer:-1', 'GlobalBuffer:inf', 'GlobalBuffer:1,1', 'Nope:2'])
def test_bad_values_are_rejected(monkeypatch, value):
    with pytest.raises(ValueError):
        parse(monkeypatch, value)


def test_requires_latency_metric(monkeypatch):
    with pytest.raises(ValueError, match='LATENCY'):
        parse(monkeypatch, 'GlobalBuffer:2', metrics=Metrics.ENERGY)


@pytest.mark.parametrize('leak_power', [1e-3, 'unknown'])
def test_leak_power_is_rejected(monkeypatch, leak_power):
    with pytest.raises(ValueError, match='leak power'):
        parse(monkeypatch, 'GlobalBuffer:2', leak_power=leak_power)


def test_scaled_latency_column_is_a_summed_objective():
    assert is_objective_col(scaled_latency2col('GlobalBuffer', 0.5))


def test_bandwidth_scenarios_are_not_monotone():
    rec = lambda edp: {'ok': True, 'edp': edp, 'reevaluated': {'edp': edp}}
    history = {'indep': {0.5: [rec(1.0)], 2.0: [rec(3.0)]},
               'shared': {0.5: [rec(1.0)], 2.0: [rec(3.0)]}}
    quality, invalid, _ = common.summarize_quality(history, ['indep', 'shared'], [0.5, 2.0], monotone=False)
    assert not invalid
    assert quality['2.0']['best_valid_edp'] == 3.0  # not bounded by the 0.5 scenario
    assert quality['2.0']['suboptimal'] == []
