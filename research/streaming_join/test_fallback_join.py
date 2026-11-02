"""Check a mid-stream fallback preserves the frontier, counts and lifecycle."""
import copy
import gc
import os
import pickle
import unittest
import weakref
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import accelforge as af
from accelforge.mapper.FFM._join_pmappings.boundary_frontier import BoundaryFrontier
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.mapper.FFM._pareto_df.df_convention import col_used_in_joining

af.set_n_parallel_jobs(1)

class FallbackJoinTest(unittest.TestCase):
    def test_fallback_after_first_chunk(self):
        capture = os.environ.get('CAPTURE_FILE', Path(__file__).parent / 'fixtures/real_join_large_tag1.pkl')
        with open(capture, 'rb') as f:
            inputs = pickle.load(f)
        def run():
            left, right, args, kwargs = copy.deepcopy(inputs)
            return left.merge_next(right,*args,**kwargs)
        with patch.dict(os.environ, {'AF_STREAMING_JOIN_PAIRS':'1024', 'AF_PARTITIONED_FRONTIER':'0'}):
            baseline = run()
        state = {'calls':0, 'released':False, 'ref':None}
        original_add, original_concat = BoundaryFrontier.add, PmappingDataframe.concat
        def add(store, data):
            state['calls'] += 1
            if state['calls'] == 2:
                state['ref'] = weakref.ref(store)
                return False
            return original_add(store, data)
        def concat(*args, **kwargs):
            if state['ref'] is not None:
                gc.collect()
                state['released'] = state['ref']() is None
            return original_concat(*args, **kwargs)
        with patch.dict(os.environ, {'AF_STREAMING_JOIN_PAIRS':'1024', 'AF_PARTITIONED_FRONTIER':'1'}), \
             patch.object(BoundaryFrontier,'add',add), patch.object(PmappingDataframe,'concat',staticmethod(concat)):
            result = run()
        self.assertEqual(state['calls'],2)
        self.assertTrue(state['released'])
        cols = sorted(c for c in baseline.data.columns if col_used_in_joining(c))
        a = baseline.data[cols].sort_values(cols).reset_index(drop=True)
        b = result.data[cols].sort_values(cols).reset_index(drop=True)
        pd.testing.assert_frame_equal(a,b,check_dtype=False,check_exact=False,rtol=1e-12,atol=1e-20)
        self.assertAlmostEqual(baseline.n_total_pmappings,result.n_total_pmappings)
        self.assertAlmostEqual(baseline.n_valid_pmappings,result.n_valid_pmappings)

if __name__ == '__main__': unittest.main()
