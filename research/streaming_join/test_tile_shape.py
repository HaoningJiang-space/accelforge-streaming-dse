import unittest
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import choose_tile_shape

class TileShapeTests(unittest.TestCase):
    def test_skinny_and_wide(self):
        self.assertEqual(choose_tile_shape(1215, 1, 1024), (1024,1))
        self.assertEqual(choose_tile_shape(1, 1215, 1024), (1,1024))

    def test_budget_and_exact_pair_coverage(self):
        for left in range(1, 27):
            for right in range(1, 23):
                for budget in (1,2,3,7,16,31,64,127,1024):
                    a,b = choose_tile_shape(left,right,budget)
                    self.assertTrue(1 <= a <= left and 1 <= b <= right and a*b <= budget)
                    visited = [(i,j) for il in range(0,left,a) for jr in range(0,right,b)
                               for i in range(il,min(il+a,left)) for j in range(jr,min(jr+b,right))]
                    self.assertEqual(len(visited), left*right)
                    self.assertEqual(len(set(visited)), left*right)

    def test_invalid(self):
        for args in ((0,1,2),(1,0,2),(1,2,0)):
            with self.assertRaises(ValueError): choose_tile_shape(*args)

if __name__ == '__main__': unittest.main()
