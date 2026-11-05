"""Restricted, demand-conditioned elimination of prepared producer choices.

Research only: one terminal Join, fixed architecture/prepared consumer group,
RU/E/L, zero tolerance, native Reservation transfer and operator order. Native
preparation is performed once, then coordinate or resource-effect dominance is
tested within equal required fields. No target optimum or completion
oracle supplies the removal witnesses. This is not full FAQ/InsideOut.
"""
from collections import defaultdict
from contextlib import contextmanager
import functools
import inspect
import os
from unittest.mock import patch

import numpy as np

from accelforge.mapper.FFM._join_pmappings.partial_state import _copy_with_frames
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.mapper.FFM._pareto_df.df_convention import col2nameloop, is_fused_loop_col
from accelforge.mapper.FFM._pareto_df import exact_resources
from accelforge.mapper.FFM.generation_contract import effective_pareto_tolerance
from .resource_effect import compile_effects, covered, UnsupportedEffect


COSTS = ('Total<SEP>energy', 'Total<SEP>latency')


def strict_addition_guard(p, q, consumer_max):
    """Sufficient strictness after any native f32/f64 nonnegative addition.

    For supported normal finite operands, each rounded sum has error bounded
    by eps32*(2*M); a gap above 8*eps32*M exceeds both errors combined. This
    deliberately rejects many valid ties/small improvements to preserve sources.
    No local EDP multiplication or rounded comparison tolerance is used.
    """
    bound = max(p, q, consumer_max)
    return q - p > 8 * np.finfo(np.float32).eps * bound


def candidate_mask(left, right, plan, max_rows=512, mode='effect'):
    """Return a mask and explicit witnesses; unknown inputs retain every row."""
    frame = left.data
    keep = np.ones(len(frame), dtype=bool)
    if mode not in ('coordinates', 'live_coordinates', 'effect'):
        raise ValueError('unknown elimination mode')
    report = dict(mode=mode, rows_before=len(frame), rows_after=len(frame), status='retained', witnesses=[],
                  suffix_completion_oracle_used=False, target_optimum_used=False)

    def unknown(reason):
        return keep, dict(report, status='unknown', reason=reason)

    if len(frame) > max_rows:
        return unknown('producer_row_budget')
    if not len(frame) or not len(right.data) or plan['make_empty_result']:
        return keep, dict(report, reason='empty_or_constant_mismatch')
    switches = {k: v for k, v in os.environ.items() if k.startswith('AF_')}
    if effective_pareto_tolerance() != 0 or switches:
        return unknown('nonreference_search_contract')
    if set(c for c in frame if c.startswith('Total<SEP>')) != set(COSTS):
        return unknown('unsupported_objectives')
    if set(c for c in right.data if c.startswith('Total<SEP>')) != set(COSTS):
        return unknown('unsupported_consumer_objectives')
    if not any(exact_resources.is_capacity_column(c) for c in frame):
        return unknown('exact_bit_resource_metadata_required')
    # A reduction must not hide a native units/range error by removing its row.
    # Capacity stamps also ensure this bucket belongs to one architecture.
    try:
        exact_resources.check_units([frame, right.data])
        exact_resources.validate_reservations(frame)
        exact_resources.validate_reservations(right.data)
    except exact_resources.ExactResourceError:
        return unknown('invalid_exact_resource_contract')
    if plan['shared_to_free'] or plan['live_to_alloc']:
        return unknown('reservation_adjustment_not_compiled')
    tensor_columns = {c for c in frame if c.startswith('tensor<SEP>')}
    requirements = (set(plan['left_match']) | (tensor_columns if mode == 'coordinates' else set()) |
                    (set(plan['remaining_symbols']) & set(frame)))
    if any(not isinstance(c, str) or c not in frame for c in requirements):
        return unknown('unsupported_match_requirement')
    requirements = sorted(requirements)
    # Every original field is accounted for. Provenance is never a comparison
    # dimension; dead fused-loop columns are dropped by this terminal Join.
    resources = sorted(c for c in frame if col2nameloop(c) is not None)
    if not resources:
        return unknown('missing_tracked_resource_state')
    known = set(COSTS) | set(resources) | set(requirements) | tensor_columns
    known.update(c for c in frame if exact_resources.is_capacity_column(c) or
                 c.endswith('<SEP>compressed_index') or is_fused_loop_col(c))
    if set(frame) - known:
        return unknown('unclassified_producer_columns')
    values = {}
    for c in [*COSTS, *resources]:
        v = frame[c].to_numpy()
        if v.dtype.kind not in 'ifu' or not np.isfinite(v).all() or (v < 0).any():
            return unknown('invalid_numeric_coordinates')
        values[c] = v
    maxima = {}
    info = np.finfo(np.float32)
    for c in COSTS:
        a, b = frame[c].to_numpy(), right.data[c].to_numpy()
        if a.dtype not in (np.dtype('float32'), np.dtype('float64')) or b.dtype not in (np.dtype('float32'), np.dtype('float64')):
            return unknown('unsupported_cost_dtype')
        if not np.isfinite(b).all() or (b < 0).any():
            return unknown('invalid_consumer_cost')
        combined = np.concatenate((a, b))
        positive = combined[combined > 0]
        if (len(positive) and positive.min() < info.tiny) or combined.max() >= info.max / 4:
            return unknown('cost_rounding_domain')
        maxima[c] = float(b.max())
    profiles = None
    if mode == 'effect':
        try:
            variables, profiles = compile_effects(left, right, plan)
        except UnsupportedEffect as exc:
            return unknown(str(exc))
        report['consumer_resource_variables'] = variables
    groups = defaultdict(list)
    try:
        for i in range(len(frame)):
            key = tuple(frame[c].iloc[i] for c in requirements)
            if any(value != value for value in key):
                return unknown('null_requirement')
            groups[key].append(i)
    except (TypeError, ValueError):
        return unknown('unsupported_requirement_values')
    report['requirement_columns'] = requirements
    report['comparison_columns'] = [*COSTS, *resources]
    report['dropped_dead_tensor_columns'] = sorted(tensor_columns - set(requirements))
    report['requirement_groups'] = len(groups)
    source_cols = sorted(c for c in frame if c.endswith('<SEP>compressed_index'))
    for rows in groups.values():
        # Witness must remain; strict cost dominance precludes cycles.
        for q in rows:
            if not keep[q]:
                continue
            for p in rows:
                if p == q or not keep[p]:
                    continue
                if not all(values[c][p] <= values[c][q] for c in COSTS):
                    continue
                if profiles is None:
                    if not all(values[c][p] <= values[c][q] for c in resources):
                        continue
                elif profiles[p].keys() != profiles[q].keys() or not all(
                        covered(profiles[p][c], profiles[q][c]) for c in profiles[p]):
                    continue
                if not any(strict_addition_guard(float(values[c][p]), float(values[c][q]), maxima[c]) for c in COSTS):
                    continue
                keep[q] = False
                report['witnesses'].append(dict(
                    kept_position=p, removed_position=q,
                    kept_sources={c: int(frame[c].iloc[p]) for c in source_cols},
                    removed_sources={c: int(frame[c].iloc[q]) for c in source_cols},
                    kept_coordinates={c: float(values[c][p]) for c in values},
                    removed_coordinates={c: float(values[c][q]) for c in values}))
                if profiles is not None:
                    report['witnesses'][-1].update(kept_effect=profiles[p], removed_effect=profiles[q])
                break
    # A later improvement may eliminate an earlier witness. Redirect it to a
    # surviving transitive witness; all requirements/schema and inequalities agree.
    parent = {w['removed_position']: w['kept_position'] for w in report['witnesses']}
    for w in report['witnesses']:
        p = w['kept_position']
        while p in parent:
            p = parent[p]
        w['final_kept_position'] = p
        w['final_kept_sources'] = {c: int(frame[c].iloc[p]) for c in source_cols}
        w['final_kept_coordinates'] = {c: float(values[c][p]) for c in values}
    report.update(rows_after=int(keep.sum()), status='reduced' if not keep.all() else 'retained')
    return keep, report


class TerminalBucketElimination:
    """Install only around a single final advance, never default FFM execution."""
    def __init__(self, max_rows=512, mode='effect'):
        self.max_rows, self.mode, self.records = max_rows, mode, []

    @contextmanager
    def installed(self):
        original = PmappingDataframe.merge_next
        signature = inspect.signature(original)

        @functools.wraps(original)
        def eliminate(pdf, right, *args, **kwargs):
            bound = signature.bind(pdf, right, *args, **kwargs)
            bound.apply_defaults()
            v = bound.arguments
            # Never move row callbacks, membership, streaming or a prior plan.
            # The scope is enforced rather than silently extending the theorem.
            if v['next_shared_loop_index'] != -1 or v['_pmapping_row_filter_function'] is not None or v['_prepared_join_plan'] is not None:
                self.records.append(dict(status='unknown', reason='nonterminal_or_custom_join', rows_before=len(pdf.data), rows_after=len(pdf.data)))
                return original(pdf, right, *args, **kwargs)
            if any(k.startswith('AF_') for k in os.environ) or effective_pareto_tolerance() != 0:
                self.records.append(dict(status='unknown', reason='nonreference_search_contract', rows_before=len(pdf.data), rows_after=len(pdf.data)))
                return original(pdf, right, *args, **kwargs)
            if v['duplicated_aliased_tensors'] or v['drop_valid_reservations']:
                self.records.append(dict(status='unknown', reason='aliases_or_untracked_resources', rows_before=len(pdf.data), rows_after=len(pdf.data)))
                return original(pdf, right, *args, **kwargs)
            plan = pdf._prepare_join_plan(right, v['shared_loop_index'], v['live_tensors'],
                                          v['still_live_reservations'], v['compatibility_left'],
                                          v['compatibility_right'], v['compatibility_joined'])
            mask, report = candidate_mask(pdf, right, plan, self.max_rows, self.mode)
            self.records.append(report)
            working = pdf
            if not mask.all():
                working = _copy_with_frames(pdf, [pdf.data])
                working._data = working.data.iloc[np.flatnonzero(mask)].copy(deep=True)
            bound.arguments['self'] = working
            bound.arguments['_prepared_join_plan'] = plan
            return original(*bound.args, **bound.kwargs)

        with patch.object(PmappingDataframe, 'merge_next', eliminate):
            yield self
