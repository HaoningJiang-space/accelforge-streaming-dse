"""Regression for element-count versus bit-capacity in FFM's memory bound."""
import importlib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from accelforge.frontend.mapper.metrics import Metrics

mod = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings')


class FakeMemory:
    def __init__(self, scale):
        self.name = 'GlobalBuffer'
        self.size = 100  # bits
        self.bits_per_value_scale = {'T': scale}


class FakeHolder:
    component = 'GlobalBuffer'
    persistent = False
    _backing = True


class CapacityBoundTests(unittest.TestCase):
    def calculate(self, bits, scale=1):
        memory = FakeMemory(scale)
        access = SimpleNamespace(bits_per_value=bits, persistent=False)
        einsum = SimpleNamespace(tensor_names={'T'}, tensor_accesses={'T': access}, n_instances=1)
        workload = SimpleNamespace(einsums={'E': einsum}, n_instances=1,
                                   einsums_with_tensor=lambda name: [einsum])
        spec = SimpleNamespace(workload=workload)
        job = SimpleNamespace(flattened_arch=[memory], spec=SimpleNamespace(arch=SimpleNamespace(find=lambda name: memory)),
                              mapping=SimpleNamespace(nodes=[FakeHolder()]))
        with patch.object(mod.arch, 'Memory', FakeMemory), patch.object(mod, 'TensorHolder', FakeHolder), \
             patch.object(mod, 'get_per_tensor_size', return_value={'T': 20}):
            return mod.get_memories_to_track(spec, {'E':[job]}, Metrics.ENERGY, False)

    def test_eight_bit_tensor_does_not_fit(self):
        tracked, _, ignored = self.calculate(bits=8)
        self.assertIn('GlobalBuffer', tracked)
        self.assertNotIn('GlobalBuffer', ignored)

    def test_one_bit_tensor_fits(self):
        tracked, _, ignored = self.calculate(bits=1)
        self.assertNotIn('GlobalBuffer', tracked)
        self.assertIn('GlobalBuffer', ignored)

    def test_memory_bit_scale_applies(self):
        tracked, _, ignored = self.calculate(bits=4, scale=2)
        self.assertIn('GlobalBuffer', tracked)
        self.assertNotIn('GlobalBuffer', ignored)


if __name__ == '__main__':
    unittest.main()
