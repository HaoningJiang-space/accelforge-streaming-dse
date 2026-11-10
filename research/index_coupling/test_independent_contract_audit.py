"""Controls for the independent schedule and external-mapping audits."""
import unittest

from .audit_chain_schedule import zero_schedule, state_of, compulsory
from .audit_mapping_interface import FIELDS, canonical_request, template_ledger
from .check_chain_threshold import chain_bound
from .graph.curve import curve
from .graph.model import Graph
from .graph.stacks import ffn_stack


class IndependentContractTests(unittest.TestCase):
    def test_single_contraction_whole_side_bound(self):
        graph = Graph({'I':2,'J':3}, [('E',{'x':('I',),'W':('I','J'),'y':('J',)})])
        result = zero_schedule(graph, {'W'})
        self.assertEqual(result['capacity'], 3)
        self.assertEqual(result['replay']['traffic'], 11)

    def test_cell_release_separates_schedule_from_grammar(self):
        graph = ffn_stack(1,m=1)
        resident = {'W1_0','W2_0'}
        self.assertEqual(zero_schedule(graph,resident)['capacity'], 3)
        self.assertEqual(curve(graph,external=resident,scalar_leaf='v2')[-1],
                         (4,compulsory(graph,resident)))

    def test_interior_streamed_weight_requires_fifth_cell(self):
        graph = ffn_stack(2,m=1)
        weights = {'W1_0','W2_0','W1_1','W2_1'}
        self.assertEqual(zero_schedule(graph,weights-{'W2_0'})['capacity'], 5)
        self.assertEqual(zero_schedule(graph,weights-{'W1_0','W2_1'})['capacity'], 4)

    def test_cardinality_does_not_prove_dense_incidence(self):
        graph = Graph({'M':1,'I':2}, [('E',{'X':('M','I'),'W':('I',),'Y':('M','I')})])
        self.assertEqual(chain_bound(graph,state_of(graph,set())), 4)
        self.assertEqual(zero_schedule(graph,set())['capacity'], 3)

    def test_named_mapping_is_serialized_in_backend_order(self):
        values = dict(zip(reversed(FIELDS), reversed((16,32,8,8,16,8))))
        result = canonical_request((64,128,32),values)['64_128_32']
        self.assertEqual(tuple(result), FIELDS)
        self.assertEqual(tuple(result.values()), (16,32,8,8,16,8))

    def test_pilot_rejects_incomplete_or_invalid_geometry(self):
        good = dict(zip(FIELDS,(16,32,8,8,16,8)))
        for changes in ({'TILE_M':0},{'TILE_N':30},{'SUB_TILE_M':32},{'TILE_K':True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                canonical_request((64,128,32),dict(good,**changes))
        with self.assertRaises(ValueError):
            canonical_request((64,128,32),{k:good[k] for k in FIELDS[:3]})

    def test_template_useful_bytes_are_not_unique_tensor_bytes(self):
        ledger = template_ledger((2,2,2),(1,1,1),element_bytes=1)
        self.assertEqual(ledger['mac_count'],8)
        self.assertEqual(ledger['useful_bytes'],20)
        self.assertEqual(ledger['logical_buffer_bytes'],3)
        self.assertEqual(ledger['source_dma_operations'],20)
        self.assertEqual(ledger['partial_sum_dram_writes'],0)


if __name__ == '__main__':
    unittest.main()
