"""Falsify proposed cut interfaces with a fixed, prepared FFM continuation.

This is a serial observational experiment, not a substitution rule or pruner.
Only one remaining Einsum is supported. Capture the native numeric Join after
capacity/resource composition and BEFORE its Pareto call, without disabling it.
Thus a supported suffix is not confused with a suffix surviving cost pruning.
"""
import argparse
from collections import defaultdict
from contextlib import contextmanager
import hashlib
import inspect
import json
import math
from pathlib import Path
import platform
import time
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal

from accelforge.frontend.mapping import Loop, Reservation, TensorHolder
from accelforge.mapper.FFM._join_pmappings import join_engine
from accelforge.mapper.FFM._join_pmappings.join_pmappings import restore_mappings
from accelforge.mapper.FFM._join_pmappings.partial_state import (
    copy_candidate_payload, copy_partial_state,
)
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.mapper.FFM._pareto_df.df_convention import col2nameloop, is_fused_loop_col
from accelforge.mapper.FFM.generation_contract import effective_pareto_tolerance
from research.graph_coopt.ffm_adapter import generate_memo, join_memo
from research.graph_coopt.memo_state_analysis import (
    digest, encode, instantiate, node_document, resolved_compatibility,
)
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, validate_pick


LEVELS = (
    'legacy_compatibility', 'numeric_compatibility', 'observed_copy_declarations',
    'boundary_loops', 'resource_state', 'execution_contract', 'cost_state',
)
COSTS = ('Total<SEP>energy', 'Total<SEP>latency')


def row_at(frame, position):
    """Columnwise access preserves exact integer bits and source indices."""
    return {c: frame[c].iloc[position] for c in frame}


def source_ids(row, einsums):
    return tuple(int(row[f'{e}<SEP>compressed_index']) for e in einsums)


def payload(frame, row, predicate):
    return [[c, str(frame[c].dtype), encode(row[c])] for c in sorted(frame) if predicate(c)]


def is_resource(c):
    return col2nameloop(c) is not None or c.startswith('resource_capacity_bits<SEP>')


def numeric_frontier(frame):
    frame = frame.select_dtypes(include='number')
    columns = sorted(frame)
    return frame[columns].sort_values(columns).reset_index(drop=True)


def numeric_resources(row):
    """Keep checked resource bits as Python integers, including above 2**53."""
    result = {}
    for c in sorted(row):
        resource = col2nameloop(c)
        if resource is not None:
            value = row[c]
            if f'resource_capacity_bits<SEP>{resource[0]}' in row:
                if int(value) != value:
                    raise ValueError('nonintegral exact resource in completion')
                result[c] = int(value)
            else:
                result[c] = float(value)
    return result


def source_catalog(store):
    """Sources are indexed before candidate preparation; never infer copies."""
    catalog = {}
    for einsum, groups in store._source.einsum2pmappings.items():
        catalog[einsum] = {}
        for group in groups:
            for pos in range(len(group.mappings.data)):
                row = row_at(group.mappings.data, pos)
                index = int(group.mappings.data.index[pos])
                template = store._source.pmapping_objects[einsum][row[f'{einsum}<SEP>mapping']]
                catalog[einsum][index] = instantiate(template, row, einsum)
    return catalog


def interfaces(state, group, position, catalog, live_tensors):
    """Nested diagnostic projections. NONE proves future substitutability.

    Source declarations are observations, not an independently verified physical
    copy/lifetime oracle. Include unit loops and ALL Compatibility fields at L1.
    Provenance IDs are excluded from interface keys; the continuation is fixed.
    """
    frame, pdf = group.mappings.data, group.mappings
    row = row_at(frame, position)
    # Erase arbitrary symbolic column labels, as native grouping does; otherwise
    # unrelated source names would artificially prevent cross-group comparisons.
    doc = {'legacy_key': encode(group.compatibility.clear_symbolic_tile_patterns()._get_hash_tuple())}
    documents = {LEVELS[0]: dict(doc)}
    # Replace symbolic bound labels with actual cut-row values.
    doc['numeric_compatibility'] = resolved_compatibility(group.compatibility, row, state.left_einsum)
    documents[LEVELS[1]] = dict(doc)
    declarations, boundary_loops = [], []
    for e, index in zip(state.processed, source_ids(row, state.processed)):
        mapping = catalog[e][index]
        relevant = [i for i, n in enumerate(mapping.nodes)
                    if set(n.tensors if isinstance(n, TensorHolder) else
                           n.purposes if isinstance(n, Reservation) else ()) & live_tensors]
        last = max(relevant, default=-1)
        declarations.extend([str(e), i, node_document(mapping.nodes[i])] for i in relevant)
        boundary_loops.extend([str(e), i, node_document(n)] for i, n in enumerate(mapping.nodes)
                              if isinstance(n, Loop) and (i < last or n._fused))
    doc['tensor_ledger'] = resolved_compatibility(group.tensors, row, state.left_einsum)
    doc['observed_copy_declarations'] = declarations
    documents[LEVELS[2]] = dict(doc)
    doc['source_boundary_loops'] = boundary_loops
    doc['current_loop_values'] = payload(frame, row, is_fused_loop_col)
    documents[LEVELS[3]] = dict(doc)
    doc['resource_columns'] = payload(frame, row, is_resource)
    doc['tensor_sizes'] = payload(frame, row, lambda c: c.startswith('tensor<SEP>'))
    documents[LEVELS[4]] = dict(doc)
    context = state.context
    # Unlike RegionEnumerator, this Join state has no prefix-Pareto history list.
    # Preserve its actual release/level state and the upstream policy provenance.
    doc['execution'] = encode(dict(
        processed=state.processed, remaining=state.remaining,
        left_tensors=state.left_tensors, live_tensors=live_tensors,
        ignored_resources=state.ignored_resources, mixable_ranks=state.mixable_ranks,
        aliases=state.aliased_tensors, drop_valid_reservations=state.drop_valid_reservations,
        free_cursor=pdf._prev_free_to_loop_index,
        left_levels=pdf.left_reservations, right_levels=pdf.right_reservations,
        parallelize_pareto=pdf._parallelize_pareto,
        switches=context.switches, tolerance=context.pareto_tolerance,
        generation_contracts=context.generation_contracts,
        skip_invalid=context.skip_invalid, combine_reservations=context.combine_reservations,
        lookahead_filter=context.lookahead_filter,
    ))
    documents[LEVELS[5]] = dict(doc)
    doc['nonprovenance_row_payload'] = payload(
        frame, row, lambda c: not c.endswith('<SEP>compressed_index'))
    documents[LEVELS[6]] = dict(doc)
    return {k: digest(v) for k, v in documents.items()}, documents


class CompletionObserver:
    """Research-only read hook; calls the unmodified Pareto on every input.

    Scope is serial, non-streaming, callback-free, one-step continuation only.
    Fail if the numeric merge implementation no longer has exactly one terminal
    Pareto call. Do not silently interpret a changed pipeline as feasibility.
    """
    def __init__(self, processed, suffix):
        self.processed, self.suffix = tuple(processed), suffix
        self.frames, self.calls = [], []
        self._active = None

    @contextmanager
    def installed(self):
        merge, pareto = PmappingDataframe.merge_next, PmappingDataframe.make_pareto
        pandas_merge = pd.merge
        signature = inspect.signature(merge)

        def counted(left, right, *args, **kwargs):
            if self._active is not None:
                raise AssertionError('nested/streaming merge is outside this audit')
            bound = signature.bind(left, right, *args, **kwargs)
            compatibility = bound.arguments['compatibility_right']
            modes = {}
            for p in range(len(right.data)):
                row = row_at(right.data, p)
                index = source_ids(row, (self.suffix,))[0]
                mode = digest(resolved_compatibility(compatibility, row, self.suffix))
                modes[index] = mode
            pair_plan = left._matching_pair_plan(
                right, bound.arguments['compatibility_left'], compatibility)
            call = dict(left_rows=len(left.data), right_rows=len(right.data),
                        left_source_tuples=[list(source_ids(row_at(left.data, p), self.processed))
                                            for p in range(len(left.data))],
                        matched_pairs=None if pair_plan is None else
                        sum(len(a) * len(b) for a, b in pair_plan),
                        materialized_pair_rows=0, pandas_merge_calls=0,
                        pre_pareto_rows=0, post_pareto_rows=0, pareto_calls=0)
            self.calls.append(call)
            self._active = (call, modes)
            try:
                result = merge(left, right, *args, **kwargs)
                call['post_pareto_rows'] = len(result.data)
                if call['pareto_calls'] != 1:
                    raise AssertionError('expected one post-capacity Pareto per numeric merge')
                if call['pandas_merge_calls'] != 1:
                    raise AssertionError('expected one pair-materializing Pandas merge')
                return result
            finally:
                self._active = None

        def observed(pdf, *args, **kwargs):
            if self._active is not None:
                call, modes = self._active
                call['pareto_calls'] += 1
                call['pre_pareto_rows'] += len(pdf.data)
                captured = pdf.data.copy(deep=True)
                # Metadata is external: never add an observation column to FFM.
                self.frames.append((captured, dict(modes)))
            return pareto(pdf, *args, **kwargs)

        def materialized(*args, **kwargs):
            frame = pandas_merge(*args, **kwargs)
            if self._active is not None:
                call, _ = self._active
                call['pandas_merge_calls'] += 1
                call['materialized_pair_rows'] += len(frame)
            return frame

        with patch.object(PmappingDataframe, 'merge_next', counted), \
             patch.object(PmappingDataframe, 'make_pareto', observed), \
             patch.object(pd, 'merge', materialized):
            yield self

    def completions(self):
        result = []
        for frame, modes in self.frames:
            for p in range(len(frame)):
                row = row_at(frame, p)
                suffix = source_ids(row, (self.suffix,))[0]
                result.append(dict(
                    prefix=list(source_ids(row, self.processed)), suffix=suffix,
                    binding=modes[suffix],
                    energy=float(row[COSTS[0]]), latency=float(row[COSTS[1]]),
                    resources=numeric_resources(row),
                    units={c: int(row[c]) for c in sorted(frame)
                           if c.startswith('resource_capacity_bits<SEP>')},
                ))
        return result


def isolate_row(state, group_index, position):
    """Keep real execution metadata; never rebuild via PDF.update/copy."""
    isolated = copy_partial_state(state)
    group = isolated.left[group_index]
    group.mappings._data = group.mappings.data.iloc[[position]].copy(deep=True)
    isolated.left = [group]
    return isolated


def response_equal(a, b, subtract_prefix=False):
    """Compare per-binding capacity/cost responses, independent of source order.

    E/T use relative 1e-6 (same acceptance as reconstruction); resource bits and
    capacity units are exact. Do not infer difference from rounding in E subtraction.
    """
    def grouped(record):
        groups = defaultdict(list)
        for c in record['completions']:
            groups[(c['suffix'], c['binding'])].append(c)
        return groups
    ga, gb = grouped(a), grouped(b)
    if ga.keys() != gb.keys():
        return False
    def equal(x, y):
        if x['resources'] != y['resources'] or x['units'] != y['units']:
            return False
        for name in ('energy', 'latency'):
            u, v = x[name], y[name]
            if subtract_prefix:
                u -= a['prefix_cost'][name]
                v -= b['prefix_cost'][name]
            # Scale by complete cost as subtraction may cancel most bits.
            if abs(u - v) > 1e-6 * max(abs(x[name]), abs(y[name]), 1e-300):
                return False
        return True
    # Compare sets, not multiset occurrence counts from equivalent permutations.
    return all(all(any(equal(x, y) for y in gb[k]) for x in ga[k]) and
               all(any(equal(x, y) for x in ga[k]) for y in gb[k]) for k in ga)


def finite_dominates(a, b):
    """Observed completion dominance only; NEVER licenses a search deletion."""
    if not b['completions']:
        return False
    strict = False
    for y in b['completions']:
        matches = []
        for x in a['completions']:
            if (x['suffix'], x['binding'], x['units']) != (y['suffix'], y['binding'], y['units']):
                continue
            if x['resources'].keys() != y['resources'].keys():
                continue
            columns = sorted(x['resources'])
            vx = [x['energy'], x['latency'], *[x['resources'][c] for c in columns]]
            vy = [y['energy'], y['latency'], *[y['resources'][c] for c in columns]]
            if all(u <= v for u, v in zip(vx, vy)):
                matches.append(any(u < v for u, v in zip(vx, vy)))
        if not matches:
            return False
        strict |= any(matches)
    return strict


def immediate_dominates(a, b):
    """Plain row comparison, without assuming different interfaces substitute."""
    if a['cut_resources'].keys() != b['cut_resources'].keys():
        return False
    columns = sorted(a['cut_resources'])
    av = [*[a['prefix_cost'][c] for c in ('energy', 'latency')],
          *[a['cut_resources'][c] for c in columns]]
    bv = [*[b['prefix_cost'][c] for c in ('energy', 'latency')],
          *[b['cut_resources'][c] for c in columns]]
    return all(x <= y for x, y in zip(av, bv)) and any(x < y for x, y in zip(av, bv))


def summarize(records):
    summaries = {}
    for level in LEVELS:
        groups = defaultdict(list)
        for r in records:
            groups[r['interfaces'][level]].append(r)
        pairs = [(a, b) for rows in groups.values() for i, a in enumerate(rows) for b in rows[i + 1:]]
        support_bad = [(a, b) for a, b in pairs if a['supported_suffixes'] != b['supported_suffixes']]
        mode_bad = [(a, b) for a, b in pairs if a['supported_bindings'] != b['supported_bindings']]
        response_bad = [(a, b) for a, b in pairs if not response_equal(a, b)]
        incremental_bad = [(a, b) for a, b in pairs if not response_equal(a, b, True)]
        dominations = [(a['id'], b['id']) for a, b in pairs for a, b in ((a, b), (b, a))
                       if finite_dominates(a, b)]
        by_id = {r['id']: r for r in records}
        reached_targets = {b for a, b in dominations if by_id[b]['reached_native_numeric_join']}
        extra_pairs = [(a, b) for a, b in dominations
                       if by_id[b]['reached_native_numeric_join'] and
                       not immediate_dominates(by_id[a], by_id[b])]
        witnesses = []
        for kind, bad in (('supported_suffix_set', support_bad), ('supported_binding_set', mode_bad),
                          ('complete_cost_resource_response', response_bad),
                          ('incremental_cost_resource_response', incremental_bad)):
            if bad:
                a, b = bad[0]
                witnesses.append(dict(kind=kind, a=a['id'], b=b['id'],
                                      suffixes_a_only=sorted(set(a['supported_suffixes']) - set(b['supported_suffixes'])),
                                      suffixes_b_only=sorted(set(b['supported_suffixes']) - set(a['supported_suffixes']))))
        summaries[level] = dict(
            groups=len(groups), singleton_groups=sum(len(g) == 1 for g in groups.values()),
            max_group_rows=max(map(len, groups.values()), default=0), same_key_pairs=len(pairs),
            cross_original_ffm_group_pairs=sum(a['group'] != b['group'] for a, b in pairs),
            both_completable_pairs=sum(bool(a['completions']) and bool(b['completions']) for a, b in pairs),
            suffix_set_counterexample_pairs=len(support_bad),
            binding_set_counterexample_pairs=len(mode_bad),
            cost_resource_counterexample_pairs=len(response_bad),
            incremental_response_counterexample_pairs=len(incremental_bad),
            finite_observed_dominance_pairs=len(dominations),
            finite_dominated_targets_reaching_native_join=len(reached_targets),
            finite_dominated_targets_already_absent_before_native_join=len(
                {b for _, b in dominations} - reached_targets),
            finite_dominance_pairs_beyond_immediate_row_comparison=len(extra_pairs),
            finite_dominance_beyond_immediate_examples=extra_pairs[:5],
            dominance_examples=dominations[:5], witnesses=witnesses,
            universal_sufficiency_proven=False, actual_rows_pruned=0,
        )
    return summaries


def work(observer):
    return dict(numeric_group_merges=len(observer.calls),
                materialized_pair_rows=sum(c['materialized_pair_rows'] for c in observer.calls),
                matched_pairs_known=sum(c['matched_pairs'] or 0 for c in observer.calls),
                matched_pair_count_unknown_calls=sum(c['matched_pairs'] is None for c in observer.calls),
                capacity_checked_row_occurrences=sum(c['pre_pareto_rows'] for c in observer.calls),
                post_local_pareto_row_occurrences=sum(c['post_pareto_rows'] for c in observer.calls))


def posthoc_oracle_ablation(memo, cut, records, expected):
    """Measure a ceiling using ALREADY enumerated suffixes; not an algorithm.

    This cannot accelerate the measured search: obtaining these witnesses paid
    for all row-specific continuations first. No inference to other consumers,
    architectures, or candidate generation. Keep every deletion's witness.
    """
    by_id = {r['id']: r for r in records}
    pairs = [(a, b) for a in records for b in records if a is not b
             and a['interfaces']['boundary_loops'] == b['interfaces']['boundary_loops']
             and finite_dominates(a, b)]
    removed, protected, witnesses = set(), set(), []
    rank = lambda r: (min((c['energy'] * c['latency'] for c in r['completions']),
                         default=math.inf), r['id'])
    for a, b in sorted(pairs, key=lambda pair: (rank(pair[0]), rank(pair[1]))):
        if a['id'] in removed or b['id'] in removed or b['id'] in protected:
            continue
        protected.add(a['id'])
        removed.add(b['id'])
        witnesses.append(dict(kept=a['id'], removed=b['id']))
    experiment = dict(oracle_uses_target_suffix_results=True, usable_pruning_rule=False,
                      removed_cut_rows=len(removed), retained_witnesses=witnesses)
    if not removed:
        return experiment
    branch = copy_partial_state(cut)
    keep = defaultdict(list)
    for r in records:
        if r['id'] not in removed:
            keep[r['group']].append(r['row_position'])
    groups = []
    for gi, group in enumerate(branch.left):
        if keep[gi]:
            group.mappings._data = group.mappings.data.iloc[keep[gi]].copy(deep=True)
            groups.append(group)
    branch.left = groups
    observer = CompletionObserver(cut.processed, cut.remaining[0])
    with observer.installed():
        actual = join_memo(memo, branch)
    # Source IDs are allowed to change only as a separately reported outcome.
    # Full numeric payload includes resource units and E/T, not just best EDP.
    try:
        assert_frame_equal(numeric_frontier(expected.data), numeric_frontier(actual.data))
        equal = True
    except AssertionError:
        equal = False
    ids = lambda result: sorted(common.mapping_identity(row['Total<SEP>mapping']())
                                for _, row in result.data.iterrows())
    experiment.update(numeric_frontier_equal=equal, mapping_source_ids_equal=ids(expected) == ids(actual),
                      continuation_work=work(observer), result_rows=len(actual.data),
                      removed_rows_reaching_native_join=sum(by_id[r]['reached_native_numeric_join'] for r in removed))
    return experiment


def audit(n, shape, capacity, validate_completions=True):
    started = time.perf_counter()
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    if effective_pareto_tolerance() != 0:
        raise ValueError('this audit requires exact, zero-tolerance Pareto')
    case = common.Case('matmuls', 'nvdla', (n, 4, 8))
    memo = generate_memo(build(case, shape, capacity, common.RU))
    store = memo._candidate_store()
    cut = memo.start()
    if n == 3:
        cut = memo.advance(cut)
    if len(cut.remaining) != 1:
        raise ValueError('the audit requires exactly one remaining Einsum')
    suffix = cut.remaining[0]
    memo.save_partial(cut)
    cut = memo.resume_partial(cut.processed)
    live = memo.dag.boundary_tensors(cut.processed)
    catalog = source_catalog(store)
    expected = join_memo(memo, cut)
    observer = CompletionObserver(cut.processed, suffix)
    with observer.installed():
        actual = join_memo(memo, cut)
    assert_frame_equal(numeric_frontier(expected.data), numeric_frontier(actual.data))
    identities = lambda r: sorted(common.mapping_identity(row['Total<SEP>mapping']())
                                 for _, row in r.data.iterrows())
    if identities(expected) != identities(actual):
        raise AssertionError('observation changed reconstructed sources')
    records, all_observed_frames, witnesses = [], [], {}
    native_reached = {tuple(ids) for call in observer.calls for ids in call['left_source_tuples']}
    with patch('accelforge.mapper.FFM._make_pmappings.make_pmappings.get_jobs',
               side_effect=AssertionError('candidate regeneration after cut')) as generation_probe:
        for gi, group in enumerate(cut.left):
            for pos in range(len(group.mappings.data)):
                keys, documents = interfaces(cut, group, pos, catalog, live)
                row = row_at(group.mappings.data, pos)
                single = isolate_row(cut, gi, pos)
                probe = CompletionObserver(cut.processed, suffix)
                error, final_sources = None, []
                try:
                    with probe.installed():
                        end = memo.advance(single)
                    finished = join_engine.finalize(end, store.context)
                    final_sources = sorted({source_ids(row_at(finished.data, p), (suffix,))[0]
                                            for p in range(len(finished.data))})
                except ValueError as exc:
                    if not str(exc).startswith(('No match found for any group.', 'No mappings found for ')):
                        raise
                    error = str(exc).splitlines()[0]
                completions = probe.completions()
                record = dict(id=f'g{gi}r{pos}', group=gi, row_position=pos,
                              prefix_sources=list(source_ids(row, cut.processed)), interfaces=keys,
                              reached_native_numeric_join=source_ids(row, cut.processed) in native_reached,
                              cut_resources=numeric_resources(row),
                              prefix_cost=dict(energy=float(row[COSTS[0]]), latency=float(row[COSTS[1]])),
                              supported_suffixes=sorted({c['suffix'] for c in completions}),
                              supported_bindings=sorted({f"{c['suffix']}:{c['binding']}" for c in completions}),
                              final_pareto_suffixes=final_sources,
                              work=work(probe), completions=completions, no_completion_error=error)
                records.append(record)
                witnesses[record['id']] = documents
                all_observed_frames.extend(frame for frame, _ in probe.frames if len(frame))
    summary = summarize(records)
    oracle = posthoc_oracle_ablation(memo, cut, records, expected)
    # Retain complete projected documents for counterexamples, not just hashes.
    wanted = {r for s in summary.values() for w in s['witnesses'] for r in (w['a'], w['b'])}
    witness_docs = {key: witnesses[key] for key in wanted}
    validations, unique_pairs, validated_responses = 0, set(), set()
    if validate_completions:
        for frame in all_observed_frames:
            for p in range(len(frame)):
                ids = source_ids(row_at(frame, p), (*cut.processed, suffix))
                r = row_at(frame, p)
                response = digest([list(ids), encode([r[c] for c in COSTS]), encode(numeric_resources(r))])
                if response in validated_responses:
                    continue
                unique_pairs.add(ids)
                validated_responses.add(response)
                pdf = PmappingDataframe(frame.iloc[[p]].copy(), 1, 1, skip_pareto=True)
                pdf.clear_fused_loop_symbols()
                source, metadata = copy_candidate_payload(store._source, store._decompress)
                restored = restore_mappings(source, pdf, metadata, tuple(source.einsum2pmappings))
                if not validate_pick(case, shape, capacity, restored.data.iloc[0])['ok']:
                    raise AssertionError('capacity-checked completion failed reconstruction')
                validations += 1
    # Snapshot/source isolation is checked after all row-specific continuations.
    restored_cut = memo.resume_partial(cut.processed)
    for a, b in zip(cut.left, restored_cut.left):
        assert_frame_equal(a.mappings.data, b.mappings.data)
        if a.tensors != b.tensors:
            raise AssertionError('continuation mutated saved cut tensor ledger')
    return dict(
        case=str(case), shape=list(shape), capacity_bytes=capacity,
        processed=list(cut.processed), remaining=list(cut.remaining), live_tensors=sorted(live),
        original_ffm_groups=len(cut.left), cut_rows=len(records),
        unique_cut_source_tuples=len({tuple(r['prefix_sources']) for r in records}),
        cut_rows_reaching_native_numeric_join=sum(r['reached_native_numeric_join'] for r in records),
        dead_cut_rows=sum(not r['supported_suffixes'] for r in records),
        original_continuation_work=work(observer), original_final_rows=len(expected.data),
        row_isolated_probe_work={key: sum(r['work'][key] for r in records) for key in work(observer)},
        observer_numeric_frontier_equal=True, observer_mapping_sources_equal=True,
        source_and_checkpoint_unchanged=True, generation_calls_after_cut=generation_probe.call_count,
        unique_completion_source_tuples_re_evaluated=len(unique_pairs),
        distinct_completion_cost_resource_responses_re_evaluated=validations,
        interface_levels=summary, records=records, witness_documents=witness_docs,
        posthoc_oracle_ablation=oracle,
        diagnostic_total_seconds=time.perf_counter() - started,
        timing_claim='Diagnostic probes include repeated continuations, signatures, copies and validation; NOT a speed benchmark.',
        coverage='All current cut rows against the same prepared one-Einsum continuation; excludes previously pruned candidates and other continuations.',
        safe_substitution_rule_established=False, actual_search_work_skipped=0,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n', type=int, choices=(2, 3), required=True)
    parser.add_argument('--shape', default='4,8')
    parser.add_argument('--capacity', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    shape = tuple(map(int, args.shape.split(',')))
    report = audit(args.n, shape, args.capacity)
    report['environment'] = dict(python=platform.python_version(), platform=platform.platform(),
                                 pandas=pd.__version__)
    paths = [Path(__file__), *[common.ROOT / 'accelforge/mapper/FFM/_join_pmappings' / name
             for name in ('join_engine.py', 'join_context.py', 'partial_state.py',
                          'pmapping_group.py', 'pmapping_dataframe.py', 'compress_pmappings.py')]]
    report['source_sha256'] = {str(p.relative_to(common.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in paths}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('records', 'witness_documents')}, indent=2))


if __name__ == '__main__':
    main()
