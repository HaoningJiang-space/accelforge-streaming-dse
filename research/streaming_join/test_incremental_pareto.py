"""Compare bounded cross-frontier merge with the tag's Pareto implementation."""
import unittest
import numpy as np
import pandas as pd
import sympy
from accelforge.mapper.FFM._join_pmappings.incremental_pareto import cross_frontier_frame
from accelforge.mapper.FFM._pareto_df.pareto import makepareto

KEY = 'fused_loop<SEP>Op<SEP>initial<SEP>C<SEP>1'
E = 'Total<SEP>energy'
T = 'Total<SEP>latency'
R = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'


def relevant(data):
    cols = [c for c in (KEY, E, T, R) if c in data.columns]
    return data[cols].sort_values(cols).reset_index(drop=True)


class IncrementalTests(unittest.TestCase):
    def check(self, a, b):
        left, right = makepareto(a), makepareto(b)
        got = cross_frontier_frame(left, right, tile_size=3)
        self.assertIsNotNone(got)
        ref = makepareto(pd.concat([left, right], ignore_index=True))
        pd.testing.assert_frame_equal(relevant(got), relevant(ref), check_dtype=False)

    def test_random_frontier_pairs(self):
        rng = np.random.default_rng(28)
        for _ in range(100):
            x = rng.integers(0, 12, size=(70, 4))
            df = pd.DataFrame(x, columns=[KEY, E, T, R])
            self.check(df.iloc[:35], df.iloc[35:])

    def test_cross_dominance_and_equal_provenance(self):
        a = pd.DataFrame([(1,1,5,1,'old'),(2,3,3,3,'old2')], columns=[KEY,E,T,R,'id'])
        b = pd.DataFrame([(1,1,5,1,'duplicate'),(2,2,2,2,'new')], columns=a.columns)
        self.check(a,b)
        out = cross_frontier_frame(makepareto(a), makepareto(b))
        self.assertEqual(set(out['id']), {'old', 'new'})

    def test_no_diffs(self):
        a = pd.DataFrame([(1.,5.),(2.,2.)], columns=[E,T])
        b = pd.DataFrame([(1.,4.),(3.,1.)], columns=[E,T])
        self.check(a,b)

    def test_unsupported_schema_and_nan_fallback(self):
        a = pd.DataFrame({E:[1.]})
        self.assertIsNone(cross_frontier_frame(a, pd.DataFrame({T:[2.]})))
        self.assertIsNone(cross_frontier_frame(a, pd.DataFrame({E:[float('nan')]})))

    def test_sympy_integer_boundaries(self):
        a = pd.DataFrame({KEY: pd.Series([sympy.Integer(1), sympy.Integer(2)], dtype=object),
                          E:[1., 3.], T:[5., 3.]})
        b = pd.DataFrame({KEY: pd.Series([sympy.Integer(1), sympy.Integer(2)], dtype=object),
                          E:[1., 2.], T:[4., 2.]})
        self.check(a, b)

    def test_mixed_high_integers_use_fallback(self):
        a = pd.DataFrame({E:[1.0], R:np.array([2**53+1], dtype=np.int64)})
        b = pd.DataFrame({E:[2.0], R:np.array([2**53], dtype=np.int64)})
        self.assertIsNone(cross_frontier_frame(a, b))

    def test_no_comparison_columns(self):
        a = pd.DataFrame({'id':['old']})
        b = pd.DataFrame({'id':['new']})
        self.assertEqual(cross_frontier_frame(a,b)['id'].tolist(), ['old'])


if __name__ == '__main__':
    unittest.main()
