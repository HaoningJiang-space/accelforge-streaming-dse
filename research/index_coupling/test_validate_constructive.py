"""Regression checks for scoring intervals and contract rejection, not timings."""
import unittest
from .validate_constructive import score

class ScoreTest(unittest.TestCase):
    def test_union_detects_loss_between_reference_knots(self):
        r=score([[3,100],[10,50]],[[3,110],[5,80],[10,50]])
        self.assertEqual(r['integer_budgets'],8)
        self.assertEqual(r['integer_counts']['worse'],2)
        self.assertEqual(r['integer_counts']['better'],5)
        self.assertEqual(r['integer_counts']['equal'],1)
        self.assertAlmostEqual(r['worst_traffic_excess'],.1)
        self.assertEqual(r['integer_counts']['within5'],6)
    def test_uncovered_and_plateau_tail(self):
        r=score([[2,20],[4,10]],[[3,20],[7,10]])
        self.assertEqual(r['integer_counts']['uncovered'],1)
        self.assertEqual(r['integer_counts']['equal'],1)
        self.assertEqual(r['integer_counts']['worse'],1)
        self.assertEqual(r['worst_traffic_excess'],1)
        self.assertEqual(r['inverse'],[[10,4,7],[20,2,3]])
    def test_tie_and_shared_compilation(self):
        r=score([[3,10],[6,5]],[[3,10],[6,5]])
        self.assertEqual(r['integer_counts']['equal'],4)
        self.assertEqual(r['worst_traffic_excess'],0)

if __name__=='__main__': unittest.main()
