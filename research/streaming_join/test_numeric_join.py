"""Check the opt-in integer-indexed column program against FFM's Pandas rule."""
import unittest
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from accelforge.mapper.FFM._join_pmappings.numeric_join import compile_column_program, apply_numpy_program
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import add_to_col


class NumericJoinTests(unittest.TestCase):
    def compare(self, data, operations):
        expected = data.copy(deep=True)
        actual = data.copy(deep=True)
        for target, source in operations:
            add_to_col(expected, target, source)
        self.assertTrue(apply_numpy_program(actual, compile_column_program(operations)))
        assert_frame_equal(expected, actual, check_dtype=True, check_exact=True)

    def test_mixed_types_and_new_columns(self):
        data = pd.DataFrame({'a':np.array([1,2,3],dtype=np.int32),
                             'b':np.array([0.25,0.5,1],dtype=np.float32),
                             'c':np.array([4,5,6],dtype=np.int32)})
        self.compare(data, [('a','b'),('b','c'),('new','a'),('a','new')])

    def test_large_integer_exactness(self):
        data = pd.DataFrame({'a':np.array([2**53+3,2**53+7],dtype=np.int64),
                             'b':np.array([3,5],dtype=np.int64)})
        self.compare(data, [('a','b'),('new','a')])

    def test_missing_and_nan_values(self):
        data = pd.DataFrame({'a':np.array([1.0,np.nan]),'b':np.array([2.0,4.0])})
        self.compare(data, [('a','b'),('new','a')])

    def test_unsupported_dtype_falls_back_without_mutation(self):
        data = pd.DataFrame({'a':['one','two'], 'b':['x','y']})
        before = data.copy(deep=True)
        self.assertFalse(apply_numpy_program(data, compile_column_program([('a','b')])))
        assert_frame_equal(data,before)

    def test_missing_source_fails_without_mutation(self):
        data = pd.DataFrame({'a':[1,2]})
        before = data.copy(deep=True)
        with self.assertRaisesRegex(ValueError, 'missing source'):
            apply_numpy_program(data, compile_column_program([('a','missing')]))
        assert_frame_equal(data,before)


if __name__ == '__main__':
    unittest.main()
