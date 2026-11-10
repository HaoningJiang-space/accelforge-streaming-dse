"""P21f implementation checks: no solver calls on new held-out residuals."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve, tile_sizes
from research.index_coupling.graph.model import Graph, residual
from research.index_coupling.run_p21f import cases, prepare
from research.index_coupling.score_p21f import compare, plateau_prediction, score, validate
from research.index_coupling.simulate_nest import simulate


class TileDomainTests(unittest.TestCase):
    def test_domains_and_default_compatibility(self):
        for n in range(1, 65):
            b, historical = n // 2, []
            while b:
                if n % b == 0:
                    historical.append(b)
                b //= 2
            self.assertEqual(tile_sizes(n), tuple(historical))
            self.assertEqual(tile_sizes(n, 'divisors'), tuple(b for b in range(n - 1, 0, -1) if n % b == 0))
            self.assertLessEqual(set(historical), set(tile_sizes(n, 'divisors')))
        self.assertEqual(tile_sizes(12), (6, 3, 1))
        self.assertEqual(tile_sizes(10), tile_sizes(10, 'divisors'))
        for n in (1, 2, 4, 8, 16, 32):
            self.assertEqual(tile_sizes(n), tile_sizes(n, 'divisors'))
        with self.assertRaises(ValueError):
            curve(residual(2, 2, 2, 2), tile_domain='unsupported')

    def test_seen_residual_archives_and_execution(self):
        for reads_x in (False, True):
            graph = residual(2, 2, 2, 2, reads_x)
            path = Path(__file__).parent / 'results/p21' / f'case_{int(reads_x):02d}.json'
            expected = json.loads(path.read_text())['result']['interfaces'][0]['curves']['unrestricted']
            for domain in ('halving', 'divisors'):
                for mode in ('enumerate', 'dp'):
                    points = curve(graph, tile_domain=domain, partitions=mode, witness=True)
                    self.assertEqual([list(p[:2]) for p in points], expected)
                    for c, q, w in points:
                        actual = simulate(graph, w)
                        self.assertTrue(actual['valid'])
                        self.assertEqual((actual['peak'], actual['traffic']), (c, q))

    def test_nonpower_single_matmul_divisors_dp_and_replay(self):
        # Synthetic single operators cannot expose any P21f residual outcome.
        for k in (6, 10, 12):
            graph = Graph(dict(I=2, K=k, L=2), [('E', {
                'A': ('I', 'K'), 'B': ('K', 'L'), 'C': ('I', 'L')})])
            historical = curve(graph)
            points = curve(graph, tile_domain='divisors', partitions='dp', witness=True)
            self.assertEqual(tuple(p[:2] for p in points), curve(graph, tile_domain='divisors'))
            for c in {p[0] for p in historical + points}:
                self.assertLessEqual(traffic_at(c, points), traffic_at(c, historical))
            for c, q, w in points:
                actual = simulate(graph, w)
                self.assertTrue(actual['valid'])
                self.assertEqual((actual['peak'], actual['traffic']), (c, q))


class FreezeAndScoreTests(unittest.TestCase):
    def test_prepare_has_no_search_and_fixed_denominators(self):
        with patch('research.index_coupling.run_p21f.curve', side_effect=AssertionError('no search')):
            manifest = prepare()
        self.assertEqual(manifest['jobs'], 140)
        self.assertEqual(sum(c['held_out'] for c in manifest['cases']), 48)
        self.assertEqual(len({tuple(c['shape']) for c in cases() if c['held_out']}), 24)
        self.assertEqual(manifest['novelty_audit']['overlap'], [])
        for c in cases():
            _, k, l = c['shape']
            if c['cohort'] == 'between':
                self.assertTrue(k < l < 2 * k)
            elif c['cohort'] == 'above':
                self.assertGreater(l, 2 * k)
            else:
                self.assertLess(l, k)

    def test_comparison_infeasibility_and_tail(self):
        f, t = [[3, 30], [7, 10]], [[4, 30], [9, 10]]
        result = compare(f, t)
        self.assertEqual(result['intervals'], [dict(lo=3, hi=3, relation='higher'),
                                              dict(lo=7, hi=8, relation='higher')])
        self.assertEqual(result['unequal_capacities'], 3)
        self.assertFalse(compare(f, f)['higher'])
        self.assertTrue(compare(t, f)['lower'])
        tail = compare(f, [[3, 30], [7, 11]])
        self.assertIsNone(tail['intervals'][-1]['hi'])
        self.assertIsNone(tail['unequal_capacities'])
        self.assertFalse(tail['same_min_traffic'])

    def test_primary_predictions_cannot_exchange_floors(self):
        for spec in cases()[:32]:
            equal = compare([[3, 30], [7, 10]], [[3, 30], [7, 10]])
            larger = compare([[3, 30], [7, 10]], [[3, 30], [9, 10]])
            expected_larger = spec['reads_x'] or spec['cohort'] == 'above'
            self.assertEqual(plateau_prediction(spec, equal), not expected_larger)
            self.assertEqual(plateau_prediction(spec, larger), expected_larger)
            larger['same_min_traffic'] = False
            self.assertFalse(plateau_prediction(spec, larger))

    def test_missing_records_do_not_pass(self):
        with tempfile.TemporaryDirectory() as directory, patch(
                'research.index_coupling.score_p21f.sha', return_value='test'):
            s = score(directory, prepare())['summary']
        self.assertEqual(s['plateau_verdict'], 'incomplete_or_invalid')
        self.assertEqual(s['primary_valid'], 0)
        self.assertEqual(s['expected_records'], 140)
        self.assertTrue(all(x['passed'] == 0 and x['total'] == 8 for x in s['primary_strata'].values()))

    def test_record_identity_and_replay_cannot_be_skipped(self):
        spec, manifest = cases()[0], prepare()
        record = dict(**spec, arm='free', tile_domain='halving', experiment='P21f',
                      manifest_sha256='test', source_sha256=manifest['source_sha256'],
                      wall_limit_seconds=1800, address_space_limit_gib=8, hash_seed='0',
                      source_revision='test', points=[[3, 10]], witnesses=[[3, 10, []]],
                      replays=[dict(capacity=3, traffic=10, exact=True,
                                    actual=dict(valid=True, peak=3, traffic=10))])
        with patch('research.index_coupling.score_p21f.sha', return_value='test'):
            validate(record, spec, 'free', 'halving', manifest)
            for changes in ({'case': 1}, {'tile_domain': 'divisors'}, {'replays': []},
                            {'points': [[3, 10], [4, 11]]}, {'manifest_sha256': 'wrong'}):
                invalid = deepcopy(record)
                invalid.update(changes)
                with self.assertRaises(ValueError):
                    validate(invalid, spec, 'free', 'halving', manifest)
            invalid = deepcopy(record)
            invalid['replays'][0]['actual']['traffic'] = 11
            with self.assertRaises(ValueError):
                validate(invalid, spec, 'free', 'halving', manifest)

    def test_complete_pass_failure_and_unfinished_coverage(self):
        def fabricated(_directory, spec, arm, domain, manifest):
            larger = spec['reads_x'] or spec['cohort'] == 'above'
            primary = spec['cohort'] in ('between', 'above')
            end = 9 if primary and larger and arm == 'tied' else 7
            middle_q = 25 if primary and arm == 'tied' else 20
            return dict(source_revision='same', points=[[3, 30], [5, middle_q], [end, 10]]), None

        def bad_and_missing(directory, spec, arm, domain, manifest):
            if spec['case'] == 1:
                return None, 'timeout'
            r, error = fabricated(directory, spec, arm, domain, manifest)
            if spec['case'] == 0 and arm == 'tied':
                r['points'][-1][0] = 9  # independent/between must have equal plateaus
            return r, error

        with patch('research.index_coupling.score_p21f.sha', return_value='test'):
            with patch('research.index_coupling.score_p21f.load', side_effect=fabricated):
                s = score('unused', prepare())['summary']
            self.assertEqual(s['plateau_verdict'], 'pass')
            self.assertEqual(s['existence']['verdict'], 'pass')
            self.assertEqual(s['complete_records'], 140)
            self.assertTrue(s['tile_diagnostic_valid'])
            with patch('research.index_coupling.score_p21f.load', side_effect=bad_and_missing):
                s = score('unused', prepare())['summary']
            self.assertEqual(s['plateau_verdict'], 'fail')
            self.assertEqual(s['primary_valid'], 31)
            self.assertEqual(s['primary_strata']['independent_between']['passed'], 7)


if __name__ == '__main__':
    unittest.main()
