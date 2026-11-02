import unittest
import numpy as np
import pandas as pd
from accelforge.mapper.FFM._join_pmappings.capacity_breakpoints import build_capacity_breakpoints

R = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'
E = 'Total<SEP>energy'
T = 'Total<SEP>latency'

class BreakpointTests(unittest.TestCase):
    def test_random_queries_match_full_scan(self):
        rng = np.random.default_rng(83)
        data = pd.DataFrame({R:rng.integers(0,100,size=1000)/100, E:rng.uniform(1,20,1000), T:rng.uniform(1,10,1000)})
        points = build_capacity_breakpoints(data, R, 8*1024*1024)
        self.assertLessEqual(len(points.edps), len(data))
        for capacity in range(0, 8*1024*1024+1, 32768):
            result = points.query(capacity)
            candidates = data[data[R] <= capacity/(8*1024*1024)]
            if candidates.empty:
                self.assertIsNone(result)
            else:
                self.assertEqual(result[0], float((candidates[E]*candidates[T]).min()))
                self.assertLessEqual(data.iloc[result[1]][R], capacity/(8*1024*1024))

    def test_exact_boundaries_and_equal_requirements(self):
        data = pd.DataFrame({R:[.25,.25,.375], E:[4.,3.,2.], T:[1.,1.,1.]})
        points = build_capacity_breakpoints(data, R, 8*1024*1024)
        self.assertIsNone(points.query(2097151))
        self.assertEqual(points.query(2097152)[0], 3.)
        self.assertEqual(points.query(3145727)[0], 3.)
        self.assertEqual(points.query(3145728)[0], 2.)

    def test_float32_capacity_comparison_matches_pandas(self):
        r = np.float32(.1)
        data = pd.DataFrame({R:np.array([r], dtype=np.float32), E:[1.], T:[1.]})
        points = build_capacity_breakpoints(data, R, 1)
        for capacity in (float(r)-1e-10, float(r), float(r)+1e-10):
            self.assertEqual(points.query(capacity) is not None, bool((data[R] <= capacity).iloc[0]))

    def test_invalid_values_rejected(self):
        with self.assertRaises(ValueError):
            build_capacity_breakpoints(pd.DataFrame({R:[0],E:[float('nan')],T:[1]}), R, 1)

if __name__ == '__main__': unittest.main()
