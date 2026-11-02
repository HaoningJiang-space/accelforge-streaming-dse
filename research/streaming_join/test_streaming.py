"""Regression tests for key counting on a trusted real FFM join capture."""
import copy
import inspect
import os
import pickle
import sys
import unittest


def no_children(event, args):
    if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
        raise RuntimeError('Child processes disabled: ' + event)


sys.addaudithook(no_children)
import accelforge as af
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.mapper.FFM._pareto_df import pareto


af.set_n_parallel_jobs(1)
with open(os.environ['CAPTURE_FILE'], 'rb') as f:
    LEFT, RIGHT, ARGS, KWARGS = pickle.load(f)
BOUND = inspect.signature(PmappingDataframe.merge_next).bind(LEFT, RIGHT, *ARGS, **KWARGS)
BOUND.apply_defaults()
CL, CR = BOUND.arguments['compatibility_left'], BOUND.arguments['compatibility_right']
LEFT_KEY = 'fused_loop<SEP>FFU<SEP>initial<SEP>C<SEP>1'
RIGHT_KEY = 'fused_loop<SEP>FFH<SEP>initial<SEP>C<SEP>1'


class KeyCountTests(unittest.TestCase):
    def test_real_cardinality(self):
        self.assertEqual(LEFT._matching_pair_count(RIGHT, CL, CR, 65536), 19730)
        self.assertGreater(LEFT._matching_pair_count(RIGHT, CL, CR, 100), 100)

    def test_different_dtype_falls_back(self):
        r = copy.deepcopy(RIGHT)
        r._data[RIGHT_KEY] = r._data[RIGHT_KEY].astype(str)
        self.assertIsNone(LEFT._matching_pair_count(r, CL, CR, 65536))

    def test_null_key_falls_back(self):
        l, r = copy.deepcopy((LEFT, RIGHT))
        l._data[LEFT_KEY] = l._data[LEFT_KEY].astype(float)
        r._data[RIGHT_KEY] = r._data[RIGHT_KEY].astype(float)
        l._data.loc[l._data.index[0], LEFT_KEY] = float('nan')
        self.assertIsNone(l._matching_pair_count(r, CL, CR, 65536))

    def test_no_match_is_empty(self):
        l, r, args, kwargs = copy.deepcopy((LEFT, RIGHT, ARGS, KWARGS))
        r._data[RIGHT_KEY] = r._data[RIGHT_KEY] + 1000000
        self.assertEqual(l._matching_pair_count(r, CL, CR, 65536), 0)
        previous = os.environ.get('AF_STREAMING_JOIN_PAIRS')
        os.environ['AF_STREAMING_JOIN_PAIRS'] = '65536'
        try:
            result = l.merge_next(r, *args, **kwargs)
            self.assertEqual(len(result.data), 0)
        finally:
            if previous is None:
                os.environ.pop('AF_STREAMING_JOIN_PAIRS', None)
            else:
                os.environ['AF_STREAMING_JOIN_PAIRS'] = previous

    def test_approximate_pareto_rejected(self):
        previous_env = os.environ.get('AF_STREAMING_JOIN_PAIRS')
        previous_tolerance = pareto.TOLERANCE
        os.environ['AF_STREAMING_JOIN_PAIRS'] = '65536'
        pareto.TOLERANCE = 0.01
        try:
            with self.assertRaisesRegex(ValueError, 'zero Pareto tolerance'):
                LEFT.merge_next(RIGHT, *ARGS, **KWARGS)
        finally:
            pareto.TOLERANCE = previous_tolerance
            if previous_env is None:
                os.environ.pop('AF_STREAMING_JOIN_PAIRS', None)
            else:
                os.environ['AF_STREAMING_JOIN_PAIRS'] = previous_env


if __name__ == '__main__':
    unittest.main()
