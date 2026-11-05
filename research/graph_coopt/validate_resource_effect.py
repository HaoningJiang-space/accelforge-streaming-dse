"""Independent native-row check of the resource shadow, never a prune oracle."""
from contextlib import contextmanager
import functools
import inspect
from unittest.mock import patch

from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from .resource_effect import compile_effects, evaluate, UnsupportedEffect


class NativeTransferCheck:
    def __init__(self):
        self.checked_rows = 0
        self.checked_coordinates = 0
        self.unknown = []
        self.active = None

    @contextmanager
    def installed(self):
        merge, pareto = PmappingDataframe.merge_next, PmappingDataframe.make_pareto
        signature = inspect.signature(merge)

        @functools.wraps(merge)
        def wrapped(pdf, right, *args, **kwargs):
            bound = signature.bind(pdf, right, *args, **kwargs)
            bound.apply_defaults()
            v = bound.arguments
            if v['next_shared_loop_index'] != -1 or v['duplicated_aliased_tensors'] or v['_prepared_join_plan'] is not None or v['drop_valid_reservations']:
                self.unknown.append('unsupported_transfer_scope')
                return merge(pdf, right, *args, **kwargs)
            plan = pdf._prepare_join_plan(right, v['shared_loop_index'], v['live_tensors'],
                v['still_live_reservations'], v['compatibility_left'], v['compatibility_right'], v['compatibility_joined'])
            bound.arguments['_prepared_join_plan'] = plan
            try:
                variables, profiles = compile_effects(pdf, right, plan)
                left_cols = sorted(c for c in pdf.data if c.endswith('<SEP>compressed_index'))
                right_cols = sorted(c for c in right.data if c.endswith('<SEP>compressed_index'))
                ids = lambda f, cols, i: tuple(int(f[c].iloc[i]) for c in cols)
                lhs = {ids(pdf.data, left_cols, i): profile for i, profile in enumerate(profiles)}
                rhs = {ids(right.data, right_cols, i): tuple(int(right.data[c].iloc[i]) for c in variables)
                       for i in range(len(right.data))}
                if not left_cols or not right_cols or len(lhs) != len(pdf.data) or len(rhs) != len(right.data):
                    raise UnsupportedEffect('ambiguous_source_lineage')
                self.active = (left_cols, right_cols, lhs, rhs)
            except UnsupportedEffect as exc:
                self.unknown.append(str(exc))
            try:
                return merge(*bound.args, **bound.kwargs)
            finally:
                self.active = None

        def checked(pdf, *args, **kwargs):
            if self.active is not None:
                left_cols, right_cols, lhs, rhs = self.active
                for i in range(len(pdf.data)):
                    left_id = tuple(int(pdf.data[c].iloc[i]) for c in left_cols)
                    right_id = tuple(int(pdf.data[c].iloc[i]) for c in right_cols)
                    for column, expression in lhs[left_id].items():
                        expected = evaluate(expression, rhs[right_id])
                        if expected != pdf.data[column].iloc[i]:
                            raise AssertionError(f'native resource effect mismatch: {column}: {expected} != {pdf.data[column].iloc[i]}')
                        self.checked_coordinates += 1
                    self.checked_rows += 1
            return pareto(pdf, *args, **kwargs)

        with patch.object(PmappingDataframe, 'merge_next', wrapped), patch.object(PmappingDataframe, 'make_pareto', checked):
            yield self
