import unittest
import numpy as np
import pandas as pd
from accelforge.mapper.FFM._pareto_df.df_convention import max_to_col

class ColumnPrecisionTests(unittest.TestCase):
    def test_mixed_max_preserves_float64(self):
        source = np.array([1/3 + 1e-10, 0.2], dtype=np.float64)
        target = np.array([1/3, 0.4], dtype=np.float32)
        df = pd.DataFrame({'target':target, 'source':source})
        expected = np.maximum(target.astype(np.float64), source)
        max_to_col(df, 'target', 'source')
        self.assertEqual(df['target'].dtype, np.dtype('float64'))
        np.testing.assert_array_equal(df['target'].to_numpy(), expected)

    def test_same_float32_stays_float32(self):
        df = pd.DataFrame({'target':np.array([1,4],dtype=np.float32),
                           'source':np.array([2,3],dtype=np.float32)})
        max_to_col(df, 'target', 'source')
        self.assertEqual(df['target'].dtype, np.dtype('float32'))
        np.testing.assert_array_equal(df['target'].to_numpy(),[2,4])

if __name__ == '__main__': unittest.main()
