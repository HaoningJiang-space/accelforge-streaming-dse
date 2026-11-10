"""Post-freeze regression controls, separate from the frozen 4,000 points."""
from math import inf
import unittest

from .check_two_contraction_interfaces import graph_of
from .graph.analysis import traffic_at
from .graph.curve import curve
from .two_contraction_response import group_response, solve_response, reachable_tiles


def reference(shape, capacity, p=False, q=False, entry='solve'):
    resident = {'W0','W1'} | ({'x'} if p else set()) | ({'z'} if q else set())
    points = curve(graph_of(shape),external=resident,scalar_leaf='v2',entry=entry,partitions='enumerate')
    return traffic_at(capacity,points)-(shape[0]*(not p)+shape[2]*(not q))


class TwoContractionInterfaceTests(unittest.TestCase):
    def test_root_partition_cannot_be_used_as_group_response(self):
        self.assertEqual(solve_response(8,2,8,3),0)
        self.assertEqual(group_response(8,2,8,3),24)
        self.assertEqual(reference((8,2,8),3,entry='group'),24)

    def test_empty_group_and_v2_scalar_redirect(self):
        self.assertEqual(group_response(6,1,5,30),inf)
        self.assertEqual(solve_response(6,1,5,2),0)
        self.assertEqual(reference((6,1,5),30,entry='group'),inf)
        self.assertEqual(group_response(1,1,1,2),0)
        self.assertEqual(reference((1,1,1),2,entry='group'),0)
        self.assertEqual(group_response(6,1,5,1,True,True),0)

    def test_both_one_sided_interfaces_can_need_materialization(self):
        # The second example is a post-freeze branch-coverage control, not
        # another point counted in the prospective 4,000 comparisons.
        for shape,C,p,q,expected in (((1,6,4),2,True,False,30),
                                    ((6,7,3),4,False,True,28)):
            with self.subTest(shape=shape):
                self.assertEqual(solve_response(*shape,C,p,q),expected)
                self.assertEqual(reference(shape,C,p,q),expected)
        self.assertEqual(group_response(6,7,3,4,False,True),36)

    def test_inner_materialization_and_tile_domain(self):
        self.assertEqual(group_response(2,15,7,2),204)
        self.assertEqual(reference((2,15,7),2,entry='group'),204)
        self.assertEqual(reachable_tiles(18,'halving'),(1,2,9,18))
        self.assertEqual(reachable_tiles(18,'divisors'),(1,2,3,6,9,18))


if __name__ == '__main__':
    unittest.main()
