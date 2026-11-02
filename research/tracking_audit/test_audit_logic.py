"""Regression tests for the audit bookkeeping (no FFM search is run)."""
import math
import os
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import common


def rec(edp, ok=True):
    return {'edp': edp, 'ok': ok}


class SummarizeQualityTest(unittest.TestCase):
    caps = [0.25, 0.5]

    def summarize(self, history):
        return common.summarize_quality(history, list(history), self.caps)

    def test_early_failure_is_not_hidden_by_later_success(self):
        history = {'var': {0.25: [rec(1.0, ok=False), rec(1.0), rec(1.0)], 0.5: [rec(1.0)] * 3}}
        quality, any_invalid, _ = self.summarize(history)
        self.assertTrue(any_invalid)
        self.assertEqual(quality['0.25']['invalid'], ['var'])

    def test_inconsistent_repeats_are_flagged(self):
        history = {'var': {0.25: [rec(1.0), rec(1.1)], 0.5: [rec(1.0), rec(1.0)]}}
        quality, any_invalid, consistent = self.summarize(history)
        self.assertFalse(any_invalid)
        self.assertFalse(consistent)
        self.assertFalse(quality['0.25']['consistent_across_repeats']['var'])

    def test_valid_pick_at_smaller_capacity_bounds_larger_capacity(self):
        history = {'a': {0.25: [rec(1.0)], 0.5: [rec(2.0)]}, 'b': {0.25: [rec(3.0)], 0.5: [rec(1.0)]}}
        quality, _, _ = self.summarize(history)
        self.assertEqual(quality['0.5']['best_valid_edp'], 1.0)
        self.assertEqual(quality['0.5']['suboptimal'], ['a'])
        self.assertEqual(quality['0.25']['suboptimal'], ['b'])

    def test_checker_error_is_not_a_valid_reference(self):
        bad = dict(rec(0.1), min_usage_shortfall_error='checker failed')
        history = {'var': {0.25: [bad], 0.5: [rec(1.0)]}}
        quality, invalid, _ = self.summarize(history)
        self.assertTrue(invalid)
        self.assertIsNone(quality['0.25']['best_valid_edp'])
        self.assertEqual(quality['0.5']['best_valid_edp'], 1.0)


class TrueEdpTest(unittest.TestCase):
    caps = [0.25]

    def test_reported_drift_with_equal_reevaluated_cost_is_consistent(self):
        a = dict(rec(1.0), reevaluated={'edp': 1.0})
        b = dict(rec(1.0 - 7e-8), reevaluated={'edp': 1.0})
        quality, invalid, consistent = common.summarize_quality({'v': {0.25: [a, b]}}, ['v'], self.caps)
        self.assertFalse(invalid)
        self.assertTrue(consistent)
        self.assertEqual(quality['0.25']['edp']['v'], 1.0)
        self.assertEqual(quality['0.25']['reported_edp']['v'], 1.0 - 7e-8)

    def test_reevaluated_cost_decides_suboptimality(self):
        good = dict(rec(2.0), reevaluated={'edp': 1.0})
        bad = dict(rec(1.0), reevaluated={'edp': 2.0})
        quality, _, _ = common.summarize_quality({'a': {0.25: [good]}, 'b': {0.25: [bad]}},
                                                 ['a', 'b'], self.caps)
        self.assertEqual(quality['0.25']['best_valid_edp'], 1.0)
        self.assertEqual(quality['0.25']['suboptimal'], ['b'])


class BestRowTest(unittest.TestCase):
    def test_float32_product_does_not_overflow(self):
        data = pd.DataFrame({'Total<SEP>energy': np.array([1e20, 2e20], dtype=np.float32),
                             'Total<SEP>latency': np.array([2e20, .5e20], dtype=np.float32),
                             'source': ['bad', 'best']})
        self.assertEqual(common.best_row(data)['source'], 'best')

    def test_duplicate_index_still_returns_one_row(self):
        data = pd.DataFrame({'Total<SEP>energy': [2., 1.], 'Total<SEP>latency': [1., 1.]},
                            index=[0, 0])
        self.assertIsInstance(common.best_row(data), pd.Series)
        self.assertEqual(common.best_row(data)['Total<SEP>energy'], 1.)

    def test_invalid_candidate_is_not_silently_ignored(self):
        data = pd.DataFrame({'Total<SEP>energy': [math.nan, 1.], 'Total<SEP>latency': [1., 1.]})
        with self.assertRaises(ValueError):
            common.best_row(data)


class CheckPickTest(unittest.TestCase):
    def test_non_finite_reported_cost_is_rejected(self):
        row = pd.Series({'Total<SEP>energy': math.inf, 'Total<SEP>latency': 1.0,
                         'Total<SEP>mapping': lambda: None})
        r = common.check_pick(common.DEFAULT_CASE, 1.0, row)
        self.assertFalse(r['ok'])
        self.assertIn('finite', r['error'])

    def test_checker_exception_invalidates_pick(self):
        row = pd.Series({'Total<SEP>energy': 1., 'Total<SEP>latency': 1.,
                         'Total<SEP>mapping': lambda: object()})
        with patch.object(common, 'strict_evaluate', return_value=dict(energy=1., latency=1., edp=1.)), \
             patch.object(common, 'spatial_usage_shortfalls', side_effect=KeyError('bounds')):
            result = common.check_pick(common.DEFAULT_CASE, 1.0, row)
        self.assertFalse(result['ok'])
        self.assertIn('KeyError', result['min_usage_shortfall_error'])

    def test_shortfall_is_distinguished_from_checker_failure(self):
        row = pd.Series({'Total<SEP>energy': 1., 'Total<SEP>latency': 1.,
                         'Total<SEP>mapping': lambda: object()})
        with patch.object(common, 'strict_evaluate', return_value=dict(energy=1., latency=1., edp=1.)), \
             patch.object(common, 'spatial_usage_shortfalls', return_value=[{'usage': .5}]):
            result = common.check_pick(common.DEFAULT_CASE, 1.0, row)
        self.assertTrue(result['ok'])  # FFM permits best attainable usage as a fallback.
        self.assertTrue(result['min_usage_shortfall'])

    def test_reported_edp_is_computed_after_promotion(self):
        value = np.float32(1e20)
        row = pd.Series({'Total<SEP>energy': value, 'Total<SEP>latency': value,
                         'Total<SEP>mapping': lambda: object()})
        cost = float(value)
        with patch.object(common, 'strict_evaluate', return_value=dict(energy=cost, latency=cost, edp=cost*cost)), \
             patch.object(common, 'spatial_usage_shortfalls', return_value=[]):
            result = common.check_pick(common.DEFAULT_CASE, 1.0, row)
        self.assertTrue(result['ok'])
        self.assertEqual(result['edp'], cost * cost)


class SpatialUsageTest(unittest.TestCase):
    def test_usage_scale_matches_model_objective(self):
        spec = common.build(common.DEFAULT_CASE, 1, common.EL)
        # One of four instances with scale four satisfies min_usage=1.
        spec.arch.find('LocalBuffer').spatial[0].usage_scale = 4
        mapping = common.af.Mapping(nodes=[common.Compute(einsum='FFG', component='MAC')])
        with patch.object(common, 'build', return_value=spec):
            shortfalls = common.spatial_usage_shortfalls(common.DEFAULT_CASE, mapping)
        self.assertFalse(any(r['component'] == 'LocalBuffer' for r in shortfalls))

    def test_absent_spatial_loop_uses_one_instance(self):
        mapping = common.af.Mapping(nodes=[common.Compute(einsum='FFG', component='MAC')])
        shortfalls = common.spatial_usage_shortfalls(common.DEFAULT_CASE, mapping)
        local = [r for r in shortfalls if r['component'] == 'LocalBuffer']
        self.assertEqual(len(local), 1)
        self.assertEqual(local[0]['usage'], .25)

    def test_other_compute_branches_are_not_checked(self):
        mapping = common.af.Mapping(nodes=[common.Compute(einsum='FFG', component='ScalarUnit')])
        shortfalls = common.spatial_usage_shortfalls(common.DEFAULT_CASE, mapping)
        self.assertFalse(any(r['component'] == 'ArrayFanout' for r in shortfalls))

    def test_unknown_loop_is_not_silently_skipped(self):
        mapping = common.af.Mapping(nodes=[
            common.Spatial(rank_variable='missing', tile_shape=1, component='LocalBuffer', name='Z'),
            common.Compute(einsum='FFG', component='MAC'),
        ])
        with self.assertRaises(ValueError):
            common.spatial_usage_shortfalls(common.DEFAULT_CASE, mapping)


class ClearSwitchesTest(unittest.TestCase):
    def test_every_af_variable_is_cleared(self):
        for k in ('AF_NUMERIC_JOIN', 'AF_INCREMENTAL_PARETO', 'AF_PARTITIONED_FRONTIER', 'AF_NEW'):
            os.environ[k] = '1'
        os.environ['UNRELATED'] = '1'
        common.clear_switches()
        self.assertFalse([k for k in os.environ if k.startswith('AF_')])
        self.assertEqual(os.environ.pop('UNRELATED'), '1')


class EffectiveConfigTest(unittest.TestCase):
    def test_configuration_uses_selected_case(self):
        case = common.Case('matmuls', 'nvdla', (2, 16, 32))
        spec = common.build(case, 1, common.EL)
        spec.mapper.ffm.max_pmapping_templates_per_einsum = 7
        with patch.object(common, 'build', return_value=spec) as build:
            config = common.effective_config(case)
        build.assert_called_once_with(case, 1, common.EL)
        self.assertEqual(config['max_pmapping_templates_per_einsum'], '7')


if __name__ == '__main__':
    unittest.main()
