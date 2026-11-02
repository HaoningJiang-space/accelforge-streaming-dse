"""Regression tests for the audit bookkeeping (no FFM search is run)."""
import math
import os
import unittest

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


class CheckPickTest(unittest.TestCase):
    def test_non_finite_reported_cost_is_rejected(self):
        row = pd.Series({'Total<SEP>energy': math.inf, 'Total<SEP>latency': 1.0,
                         'Total<SEP>mapping': lambda: None})
        r = common.check_pick((1, 1, 1), 1.0, row)
        self.assertFalse(r['ok'])
        self.assertIn('finite', r['error'])


class ClearSwitchesTest(unittest.TestCase):
    def test_every_af_variable_is_cleared(self):
        for k in ('AF_NUMERIC_JOIN', 'AF_INCREMENTAL_PARETO', 'AF_PARTITIONED_FRONTIER', 'AF_NEW'):
            os.environ[k] = '1'
        os.environ['UNRELATED'] = '1'
        common.clear_switches()
        self.assertFalse([k for k in os.environ if k.startswith('AF_')])
        self.assertEqual(os.environ.pop('UNRELATED'), '1')


if __name__ == '__main__':
    unittest.main()
