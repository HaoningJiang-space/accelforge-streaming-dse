"""Keep filter ablations from silently changing the Pareto objective set."""
import json
from types import SimpleNamespace

import pytest

import unrepresentable_gain as audit


@pytest.mark.parametrize('mode', ['el', 'ru'])
def test_filter_ablation_uses_same_metrics_for_both_searches(monkeypatch, capsys, mode):
    common = audit.common
    builds, searches = [], []

    def build(case, cap, metrics):
        builds.append(metrics)
        return metrics

    def search(spec, **kwargs):
        searches.append(kwargs)
        return SimpleNamespace(data=object()), {}

    monkeypatch.setattr(common, 'build', build)
    monkeypatch.setattr(common, 'search', search)
    monkeypatch.setattr(common, 'effective_config', lambda *args, **kwargs: {})
    monkeypatch.setattr(common, 'set_jobs', lambda n: None)
    monkeypatch.setattr(common, 'shutdown_workers', lambda: None)
    monkeypatch.setattr(common, 'best_row', lambda data: object())
    monkeypatch.setattr(common, 'check_pick', lambda *args: {'ok': True, 'reevaluated': {'edp': 2.}})
    monkeypatch.setattr(audit, 'rebuilt_costs', lambda *args: [{'edp': 1., 'matches': True}])

    assert audit.main(['4,8,16', '1', '--metrics', mode]) == 0
    expected = common.RU if mode == 'ru' else common.EL
    assert builds == [expected, expected]
    assert searches == [{}, {'ablations': {'AF_ABL_ALLOW_UNREPRESENTABLE': '1'}}]
    summary = json.loads(capsys.readouterr().out.split('SUMMARY ', 1)[1])
    assert summary['conservative']['metrics'] == summary['restored']['metrics'] == mode
