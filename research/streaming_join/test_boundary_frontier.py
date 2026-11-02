import unittest
import numpy as np
import pandas as pd
from accelforge.mapper.FFM._join_pmappings.boundary_frontier import BoundaryFrontier
from accelforge.mapper.FFM._pareto_df.pareto import makepareto

K = 'fused_loop<SEP>Op<SEP>initial<SEP>C<SEP>1'
E = 'Total<SEP>energy'
T = 'Total<SEP>latency'
R = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'

class BoundaryTests(unittest.TestCase):
    def test_random_chunks_match_full_pareto(self):
        rng = np.random.default_rng(231)
        for trial in range(15):
            data = pd.DataFrame(rng.integers(0,20,(300,4)), columns=[K,E,T,R])
            store = BoundaryFrontier()
            for indices in np.array_split(np.arange(len(data)), 9):
                self.assertTrue(store.add(makepareto(data.iloc[indices])))
            got = store.finish().sort_values([K,E,T,R]).reset_index(drop=True)
            ref = makepareto(data).sort_values([K,E,T,R]).reset_index(drop=True)
            pd.testing.assert_frame_equal(got,ref,check_dtype=False)

    def test_new_groups_do_not_scan_old(self):
        stats = {}
        store = BoundaryFrontier(stats)
        self.assertTrue(store.add(pd.DataFrame({K:[1],E:[1.],T:[2.]})))
        self.assertTrue(store.add(pd.DataFrame({K:[2],E:[1.],T:[2.]})))
        self.assertEqual(stats.get('old_rows_scanned', 0), 0)
        self.assertEqual(len(store.finish()),2)

    def test_unsupported_schema_falls_back_without_mutation(self):
        store = BoundaryFrontier()
        self.assertTrue(store.add(pd.DataFrame({K:[1],E:[1.],T:[2.]})))
        before = store.finish()
        self.assertFalse(store.add(pd.DataFrame({K:[1],E:[1.]})))
        pd.testing.assert_frame_equal(before,store.finish())

if __name__ == '__main__': unittest.main()
