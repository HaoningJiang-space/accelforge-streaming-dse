"""CLI validation and cleanup contracts; no FFM searches are launched."""
from unittest.mock import patch

import pytest
import pandas as pd

import capacity_audit


@pytest.mark.parametrize('params,caps,variants,extra', [
    ('1,2', '1', 'indep', []), ('1,2,0', '1', 'indep', []), ('1,x,3', '1', 'indep', []),
    ('1,2,3', 'nan', 'indep', []), ('1,2,3', 'inf', 'indep', []),
    ('1,2,3', '0', 'indep', []), ('1,2,3', '1,1', 'indep', []),
    ('1,2,3', '1', 'indep,indep', []), ('1,2,3', '1', 'unknown', []),
    ('1,2,3', '1', 'indep', ['--workload', 'mobilenet']),  # mobilenet takes one parameter
    ('1,2,3', '1', 'indep', ['--workload', 'unknown']),
    ('1,2,3', '1', 'indep', ['--arch', 'unknown']),
])
def test_invalid_config_fails_before_search(params, caps, variants, extra):
    with pytest.raises(SystemExit) as error:
        capacity_audit.parse_args([params, caps, variants, *extra])
    assert error.value.code == 2


def test_workload_and_arch_select_the_case():
    args = capacity_audit.parse_args(['3,64,128', '0.5', 'indep', '--workload', 'matmuls',
                                      '--arch', 'nvdla'])
    assert args.case == capacity_audit.common.Case('matmuls', 'nvdla', (3, 64, 128))
    assert str(args.case) == 'matmuls(N_EINSUMS=3,M=64,KN=128)@nvdla'
    assert capacity_audit.parse_args(['4,8,16', '1', 'indep']).case.workload == 'glu'


def test_options_can_precede_or_follow_ablations():
    args = capacity_audit.parse_args([
        '1,2,3', '1,2', 'indep,var', 'AF_ABL_SKIP_BIG_ENOUGH=LocalBuffer',
        '--jobs', '8', 'AF_ABL_SKIP_PMAPPING_ONLY=Register', '--repeats', '3',
    ])
    assert args.jobs == 8
    assert args.repeats == 3
    assert args.ablations['AF_ABL_SKIP_PMAPPING_ONLY'] == 'Register'


def test_unknown_ablation_is_an_argument_error():
    with pytest.raises(SystemExit) as error:
        capacity_audit.parse_args(['1,2,3', '1', 'indep', 'AF_UNKNOWN=1'])
    assert error.value.code == 2


def test_worker_cleanup_runs_when_experiment_raises():
    with patch.object(capacity_audit.common, 'effective_config', return_value={}), \
         patch.object(capacity_audit.common, 'set_jobs'), \
         patch.object(capacity_audit.common, 'shutdown_workers') as shutdown, \
         patch.object(capacity_audit, 'run', side_effect=RuntimeError('search failed')):
        with pytest.raises(RuntimeError, match='search failed'):
            capacity_audit.main(['1,2,3', '1', 'indep'])
        shutdown.assert_called_once()


def test_missing_pick_does_not_claim_completed_usage_checks():
    args = capacity_audit.parse_args(['1,2,3', '1', 'indep', '--no-warmup'])
    with patch.object(capacity_audit.common, 'run_variant', return_value=[(1., pd.DataFrame(), {})]):
        summary, status = capacity_audit.run(args)
    assert status == 2
    assert not summary['all_picks_valid']
    assert not summary['all_min_usage_checks_completed']


def test_usage_check_error_sets_failing_exit_status():
    args = capacity_audit.parse_args(['1,2,3', '1', 'indep', '--no-warmup'])
    data = pd.DataFrame({'Total<SEP>energy': [1.], 'Total<SEP>latency': [1.]})
    record = {'ok': False, 'edp': 1., 'min_usage_shortfall_error': 'checker failed'}
    with patch.object(capacity_audit.common, 'run_variant', return_value=[(1., data, {})]), \
         patch.object(capacity_audit.common, 'check_pick', return_value=record):
        summary, status = capacity_audit.run(args)
    assert status == 2
    assert not summary['all_min_usage_checks_completed']


def test_suboptimal_variant_sets_failing_exit_status():
    args = capacity_audit.parse_args(['1,2,3', '1', 'indep,var', '--no-warmup'])
    data = pd.DataFrame({'Total<SEP>energy': [1.], 'Total<SEP>latency': [1.]})
    records = {'indep': {'ok': True, 'edp': 1., 'min_usage_shortfall': []},
               'var': {'ok': True, 'edp': 2., 'min_usage_shortfall': []}}
    current = []

    def run_variant(v, *rest):
        current.append(v)
        return [(1., data, {})]

    with patch.object(capacity_audit.common, 'run_variant', side_effect=run_variant), \
         patch.object(capacity_audit.common, 'check_pick',
                      side_effect=lambda *a: dict(records[current[-1]])):
        summary, status = capacity_audit.run(args)
    assert status == 5
    assert not summary['all_picks_best_known']
    assert summary['quality']['1.0']['suboptimal'] == ['var']
