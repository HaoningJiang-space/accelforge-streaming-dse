"""Optional serial phase instrumentation; never enabled in ordinary searches.

Inclusive times nest. Exclusive times subtract instrumented children, so they
can be added. An exclusive remainder may contain uninstrumented helpers; it is
not automatically time spent in the function's own Python statements.
"""
from collections import defaultdict
from functools import wraps
import importlib
import time


class GenerationPhases:
    def __init__(self, common):
        tiles = importlib.import_module(
            'accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')
        model = importlib.import_module(
            'accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.run_model')
        pmapper = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings')
        self.targets = [
            (common, 'make_pmappings', 'generation'),
            (common, 'join_pmappings', 'join'),
            (pmapper, 'get_jobs', 'template_generation'),
            (tiles, '_make_tile_shapes', 'template_evaluation'),
            (tiles, 'run_model', 'symbolic_model'),
            (model, 'analyze_reuse_and_add_reservations_to_mapping', 'reuse_analysis'),
            (model, 'component_latency', 'latency_model'),
            (model, '_maximum_latency', 'latency_maximum'),
            (model, 'compute_energy_from_actions', 'energy_model'),
            (model, 'gather_actions', 'gather_actions'),
            (tiles.Objective, '__init__', 'objective_preparation'),
            (tiles, 'get_tile_shape_choices_for_targets', 'target_dispatch'),
            (tiles, 'get_tile_shape_choices', 'target_enumeration'),
            (tiles, '_expand_symbol_choices', 'prefix_expansion'),
            (tiles, 'partition_formula', 'formula_goals'),
            (tiles, 'get_padded_choices', 'constraint_padding'),
            (tiles, 'coalesce_symbols', 'coalesce_goals'),
            (tiles, 'makepareto_numpy', 'enumeration_pareto'),
            (tiles, 'compile_dict', 'output_compilation'),
            (tiles, '_calculate_iterations_and_rank_columns', 'iteration_columns'),
        ]
        self.stats = defaultdict(lambda: dict(calls=0, inclusive_s=0., exclusive_s=0.))
        self._stack = []
        self._restore = []

    def _wrap(self, function, phase):
        @wraps(function)
        def measured(*args, **kwargs):
            frame = [time.perf_counter(), 0.]
            self._stack.append(frame)
            try:
                return function(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - frame[0]
                self._stack.pop()
                stat = self.stats[phase]
                stat['calls'] += 1
                stat['inclusive_s'] += elapsed
                stat['exclusive_s'] += elapsed - frame[1]
                if self._stack:
                    self._stack[-1][1] += elapsed
        return measured

    def __enter__(self):
        self.stats.clear()
        try:
            for owner, name, phase in self.targets:
                original = getattr(owner, name)
                self._restore.append((owner, name, original))
                setattr(owner, name, self._wrap(original, phase))
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc):
        for owner, name, original in reversed(self._restore):
            setattr(owner, name, original)
        self._restore.clear()

    def snapshot(self):
        return {k: dict(v) for k, v in self.stats.items()}
