from itertools import product
import random

import pytest

from research.joint_budget.family_support import propagate


def test_hardware_support_must_not_be_mixed_across_operators():
    catalogs = {(0, 'a'): {'a'}, (0, 'b'): set(),
                (1, 'a'): set(), (1, 'b'): {'b'}}
    interfaces = {(0, 'a', 'a', 'b'): None, (1, 'b', 'b', 'a'): None}
    _, report = propagate(catalogs, (('a', 'b'),), interfaces)
    assert report['surviving_hardware'] == []
    assert len(report['removed']) == 2


def test_isolated_mandatory_operator_still_needs_the_same_hardware():
    catalogs = {(0, 'a'): {'a'}, (0, 'b'): {'b'}, (0, 'isolated'): set()}
    interfaces = {(0, 'a', 'a', 'b'): None, (0, 'b', 'b', 'a'): None}
    _, report = propagate(catalogs, (('a', 'b'),), interfaces)
    assert report['surviving_hardware'] == []
    assert report['removed_hardware'] == [0]


def test_fixpoint_removes_backward_chain_but_preserves_every_complete_witness():
    catalogs = {(0, op): {'keep', 'dead'} for op in ('a', 'b', 'c')}
    edges = (('a', 'b'), ('b', 'c'))
    interfaces = {}
    for a, b in edges:
        for source, peer in ((a, b), (b, a)):
            for family in ('keep', 'dead'):
                label = 0 if family == 'keep' else (2 if source == 'c' else 1)
                interfaces[0, source, family, peer] = frozenset({label})
    kept, report = propagate(catalogs, edges, interfaces)
    assert all(kept[0, op] == {'keep'} for op in ('a', 'b', 'c'))
    assert report['rounds'] >= 3
    for choices in product(('keep', 'dead'), repeat=3):
        assignment = dict(zip(('a', 'b', 'c'), choices))
        if all(interfaces[0, a, assignment[a], b] & interfaces[0, b, assignment[b], a]
               for a, b in edges):
            assert all(assignment[op] in kept[0, op] for op in assignment)


def test_unknown_is_wildcard_and_incomplete_catalog_is_an_error():
    catalogs = {(0, 'a'): {'a'}, (0, 'b'): {'b'}}
    interfaces = {(0, 'a', 'a', 'b'): None,
                  (0, 'b', 'b', 'a'): frozenset({1})}
    kept, report = propagate(catalogs, (('a', 'b'),), interfaces)
    assert report['removed'] == []
    assert kept[0, 'a'] == {'a'}
    with pytest.raises(ValueError, match='complete catalog'):
        propagate({(0, 'a'): {'a'}}, (('a', 'b'),), interfaces)


def test_random_cyclic_relations_never_delete_an_exhaustive_witness():
    edges = (('a', 'b'), ('b', 'c'), ('c', 'a'))
    for seed in range(40):
        rng = random.Random(seed)
        catalogs = {(h, op): frozenset(range(3)) for h in range(2) for op in 'abc'}
        interfaces = {}
        for h in range(2):
            for a, b in edges:
                for source, peer in ((a, b), (b, a)):
                    for family in range(3):
                        interfaces[h, source, family, peer] = (None if rng.random() < .1
                            else frozenset(k for k in range(3) if rng.random() < .4))
        kept, report = propagate(catalogs, edges, interfaces)
        for h in range(2):
            for values in product(range(3), repeat=3):
                assignment = dict(zip('abc', values))
                valid = True
                for a, b in edges:
                    left = interfaces[h, a, assignment[a], b]
                    right = interfaces[h, b, assignment[b], a]
                    if left is not None and right is not None and not left & right:
                        valid = False
                if valid:
                    assert h in report['surviving_hardware']
                    assert all(assignment[op] in kept[h, op] for op in 'abc')
