"""Check the selective-resource proof and protection logic."""
import importlib
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import pandas as pd
import accelforge as af

mod = importlib.import_module('accelforge.mapper.FFM._join_pmappings.join_pmappings')
af.set_n_parallel_jobs(1)


class FakeMappings:
    def __init__(self, data):
        self.data = data

    def update(self, *, data, skip_pareto):
        return FakeMappings(data)


class FakeGroup:
    def __init__(self, compatibility, mappings):
        self.compatibility = compatibility
        self.mappings = mappings


class ResourcePolicyTests(unittest.TestCase):
    def test_protect_variable_and_only_remove_proven_fixed_resource(self):
        gb = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'
        local = 'reservation<SEP>LocalBuffer<SEP>0<SEP>right'
        register = 'reservation<SEP>Register<SEP>0<SEP>right'
        compat = SimpleNamespace(n_loops=0, tensors=[])
        groups = {
            'A': [FakeGroup(compat, FakeMappings(pd.DataFrame({gb:[0.1], local:[0.3], register:[0.6]})))],
            'B': [FakeGroup(compat, FakeMappings(pd.DataFrame({gb:[0.2], local:[0.4], register:[0.7]})))],
        }
        with patch.object(mod, 'PmappingGroup', FakeGroup):
            result, removed = mod.get_memories_to_track(
                groups, protected_resources=frozenset({'GlobalBuffer'}), capacity_proof_only=True)
        self.assertEqual(removed, {'LocalBuffer'})
        for group_list in result.values():
            for group in group_list:
                self.assertIn(gb, group.mappings.data)
                self.assertIn(register, group.mappings.data)
                self.assertNotIn(local, group.mappings.data)


if __name__ == '__main__':
    unittest.main()
