"""Adversarial checks for native scope/entry semantics, not search speed."""
from dataclasses import replace
import json
from pathlib import Path
import unittest

from research.index_coupling.graph.model import Graph
from research.index_coupling.simulate_nest import simulate
from .boundary import RegionComposer, workload
from .hierarchy import ContractError, Plan, analyze, decode, encode, tuples


ARCHIVE = Path(__file__).parent / 'results/d1/results/fork_join_tiny.json'


def key_plan():
    saved = json.loads(ARCHIVE.read_text())['arms']['native_all_orders']
    witness = saved['witnesses'][saved['frontier'].index([5, 32])]['notes']
    graph, _ = workload('fork_join', (2, 2, 2, 2))
    return graph, decode(graph, witness), tuples(witness)


def changed(plan, predicate, transform):
    if predicate(plan):
        return transform(plan)
    return replace(plan, children=tuple(changed(c, predicate, transform) for c in plan.children))


class HierarchyTests(unittest.TestCase):
    def test_nested_scope_roundtrip_and_independent_execution(self):
        graph, plan, notes = key_plan()
        self.assertEqual(encode(plan), notes)
        checked = analyze(graph, plan)
        actual = simulate(graph, encode(plan), scalar_leaf='v2')
        self.assertEqual((checked['peak'], checked['traffic']), (5, 32))
        self.assertEqual((actual['peak'], actual['traffic']), (5, 32))
        self.assertTrue(actual['valid'])
        scopes = {(c['rank'], tuple(c['operators'])) for c in checked['calls'] if c['kind'] == 'loop'}
        self.assertTrue({('I', graph.ops), ('L', ('E0', 'E1', 'Join')),
                         ('K', ('E0', 'E1'))} <= scopes)

    def test_omitted_inner_scope_is_not_a_closed_group(self):
        graph, plan, _ = key_plan()
        bad = changed(plan, lambda n: n.kind == 'loop' and n.rank == 'L',
                      lambda n: replace(n.children[0], entry='group'))
        with self.assertRaisesRegex(ContractError, 'group must loop'):
            analyze(graph, bad)

    def test_retention_for_a_later_reader_cannot_disappear(self):
        graph, plan, _ = key_plan()
        bad = changed(plan, lambda n: n.kind == 'partition' and n.kept == ('X',),
                      lambda n: replace(n, kept=()))
        with self.assertRaisesRegex(ContractError, 'boundary decision'):
            analyze(graph, bad)

    def test_common_rank_does_not_allow_unfinished_intermediate(self):
        graph = Graph({'I': 2, 'K': 2}, [
            ('P', {'A': ('I','K'), 'X': ('I',)}),
            ('C', {'X': ('I',), 'B': ('I','K'), 'Y': ('I','K')})])
        bad = Plan('loop', graph.ops, 'group', rank='K', tile=1, trips=2,
                   children=(Plan('leaf', graph.ops, 'solve'),))
        with self.assertRaisesRegex(ContractError, 'unfinished internal reduction'):
            analyze(graph, bad, entry='group')

    def test_tile_domain_is_part_of_the_contract(self):
        graph = Graph({'I': 6}, [('E', {'A': ('I',), 'Y': ('I',)})])
        groups = ('groups', (graph.ops,), 'kept', (), 'via DRAM', ())
        notes = (groups, ('loop', graph.ops, 'I', 'tile 2 x3', 'kept', (), 'refetched', ()),
                 groups, ('loop', graph.ops, 'I', 'tile 1 x2', 'kept', (), 'refetched', ()))
        plan = decode(graph, notes, tile_domain='divisors')
        checked = analyze(graph, plan, tile_domain='divisors')
        actual = simulate(graph, encode(plan), scalar_leaf='v2')
        self.assertEqual((checked['peak'], checked['traffic']), (actual['peak'], actual['traffic']))
        with self.assertRaisesRegex(ContractError, 'illegal tile'):
            analyze(graph, plan, tile_domain='halving')

    def test_whole_scalar_child_cannot_repartition(self):
        graph, _ = workload('fork_join', (1, 1, 1, 1))
        points = RegionComposer(graph, verify=True).compose((graph.ops,))
        plan = decode(graph, points[0][2])
        self.assertEqual(analyze(graph, plan)['peak'], 8)
        bad = replace(plan, children=(replace(plan.children[0], kind='partition'),))
        with self.assertRaises(ContractError):
            analyze(graph, bad)

    def test_serial_order_cannot_change_inside_a_region(self):
        graph, plan, _ = key_plan()
        bad = replace(plan, ops=tuple(reversed(plan.ops)))
        with self.assertRaisesRegex(ContractError, 'scope/entry mismatch'):
            analyze(graph, bad)

    def test_numeric_entry_ownership_changes_only_paid_final_store(self):
        graph = Graph({'I': 1}, [('P', {'A': ('I',), 'X': ('I',)}),
                                  ('C', {'X': ('I',), 'Y': ('I',)})])
        notes = (('groups', (('P',), ('C',)), 'kept', (), 'via DRAM', ('X',)),)
        plan = decode(graph, notes)
        local = analyze(graph, plan)
        paid = analyze(graph, plan, owned={'X'})
        self.assertEqual(local['extra_traffic'] - paid['extra_traffic'], 1)
        self.assertEqual(local['peak'], paid['peak'])


if __name__ == '__main__':
    unittest.main()
