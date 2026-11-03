"""Candidate-cache identity must include every generation-affecting switch."""
import importlib
import os

import pytest

mapper = importlib.import_module('accelforge.mapper.FFM.main')


@pytest.mark.parametrize('switch,value', [
    ('AF_ENUMERATION_PREFIX_BYTES', '8388608'),
    ('AF_ENUMERATION_PARETO_BYTES', '8388608'),
    ('AF_LATENCY_SCALES', 'GlobalBuffer:2'),
    ('AF_GENERATION_CAPACITY_FRACTIONS', 'GlobalBuffer:0.5,1.0'),
    ('AF_GENERATION_VARIABLE_RESOURCES', 'GlobalBuffer'),
    ('AF_ABL_ALLOW_UNREPRESENTABLE', '1'),
    ('AF_ABL_SKIP_BIG_ENOUGH', 'GlobalBuffer'),
    ('AF_ABL_SKIP_PMAPPING_ONLY', 'GlobalBuffer'),
    ('AF_ABL_BIG_ENOUGH_UNTRACK_ONLY', 'GlobalBuffer'),
])
def test_generation_switch_changes_cache_key(monkeypatch, tmp_path, switch, value):
    monkeypatch.delenv(switch, raising=False)
    calls = []

    def generate(spec, einsum_names=None, can_combine_multiple_runs=False):
        calls.append(os.environ.get(switch))
        return {'scenario': os.environ.get(switch)}

    monkeypatch.setattr(mapper, '_make_pmappings', generate)
    kwargs = dict(spec='fixed-spec', cache_dir=str(tmp_path), print_number_of_pmappings=False)
    assert mapper.make_pmappings(**kwargs) == {'scenario': None}
    assert mapper.make_pmappings(**kwargs) == {'scenario': None}
    assert calls == [None]
    monkeypatch.setenv(switch, value)
    assert mapper.make_pmappings(**kwargs) == {'scenario': value}
    assert mapper.make_pmappings(**kwargs) == {'scenario': value}
    assert calls == [None, value]
    monkeypatch.delenv(switch)
    assert mapper.make_pmappings(**kwargs) == {'scenario': None}
    assert calls == [None, value]


def test_exact_search_cannot_reuse_an_approximate_frontier(monkeypatch, tmp_path):
    calls = []

    def generate(spec, einsum_names=None, can_combine_multiple_runs=False):
        calls.append(mapper.pareto_module.TOLERANCE)
        return calls[-1]

    monkeypatch.setattr(mapper, '_make_pmappings', generate)
    kwargs = dict(spec='fixed-spec', cache_dir=str(tmp_path), print_number_of_pmappings=False)
    monkeypatch.setattr(mapper.pareto_module, 'TOLERANCE', .1)
    assert mapper.make_pmappings(**kwargs) == .1
    monkeypatch.setattr(mapper.pareto_module, 'TOLERANCE', 0.)
    assert mapper.make_pmappings(**kwargs) == 0.
    assert mapper.make_pmappings(**kwargs) == 0.
    assert calls == [.1, 0.]


def test_generation_semantics_version_invalidates_old_candidates(monkeypatch, tmp_path):
    calls = []

    def generate(spec, einsum_names=None, can_combine_multiple_runs=False):
        calls.append(mapper._GENERATION_CACHE_VERSION)
        return calls[-1]

    monkeypatch.setattr(mapper, '_make_pmappings', generate)
    kwargs = dict(spec='fixed-spec', cache_dir=str(tmp_path), print_number_of_pmappings=False)
    monkeypatch.setattr(mapper, '_GENERATION_CACHE_VERSION', 0)
    assert mapper.make_pmappings(**kwargs) == 0
    monkeypatch.setattr(mapper, '_GENERATION_CACHE_VERSION', 1)
    assert mapper.make_pmappings(**kwargs) == 1
    assert mapper.make_pmappings(**kwargs) == 1
    assert calls == [0, 1]
