"""Resumable reference-order Join kernel, extracted without numeric changes.

Public start/advance/finalize isolate working copies. The original full-Join
wrapper uses the same owned kernel without copying at every transition.
"""
from copy import deepcopy
from .partial_state import PartialState, snapshot, resume


def _contract(context):
    return dict(spec=context._spec, skip_invalid=context.skip_invalid,
                combine_reservations=context.combine_reservations,
                lookahead_filter=context.lookahead_filter and context.skip_invalid,
                _pmapping_row_filter_function=context.row_filter,
                _terminal_branch_observer=context.terminal_observer)

def _start_owned(pmapping_groups, context):
    from .join_pmappings import (Metrics, PmappingGroup, PmappingsOneEinsum,
        JoiningTimer, get_memories_to_track, col2nameloop, _with_compatibility,
        parallel, logger)
    import os, time, itertools
    context.check_environment()
    contract = _contract(context)
    spec = contract['spec']
    skip_invalid = contract['skip_invalid']
    combine_reservations = contract['combine_reservations']
    lookahead_filter = contract['lookahead_filter']
    _pmapping_row_filter_function = contract['_pmapping_row_filter_function']
    _terminal_branch_observer = contract['_terminal_branch_observer']
    metrics = spec.mapper.ffm.metrics

    drop_valid_reservations = not (Metrics.RESOURCE_USAGE & metrics)
    ignored_resources = set()

    if _pmapping_row_filter_function is not None:
        n = sum(len(s.mappings.data) for sg in pmapping_groups.values() for s in sg)
        pmapping_groups = {
            e: [
                PmappingGroup(
                    s.compatibility,
                    s.mappings.filter_rows(_pmapping_row_filter_function),
                )
                for s in pmapping_groups[e]
            ]
            for e in pmapping_groups
        }
        new_n = sum(len(s.mappings.data) for sg in pmapping_groups.values() for s in sg)
        print(f"Filtered {n} -> {new_n} ({new_n / n:.2%} kept) pmappings")

    if drop_valid_reservations:
        pmapping_groups, ignored_resources = get_memories_to_track(pmapping_groups)
    elif variable_resources := os.environ.get("AF_VARIABLE_RESOURCES"):
        protected = frozenset(x.strip() for x in variable_resources.split(",") if x.strip())
        present = {
            name_nloops[0]
            for groups in pmapping_groups.values()
            for group in groups
            for col in group.mappings.data.columns
            if (name_nloops := col2nameloop(col)) is not None
        }
        if not protected or not protected.issubset(present):
            raise ValueError(f"Unknown or empty variable resources: {sorted(protected - present)}")
        pmapping_groups, ignored_resources = get_memories_to_track(
            pmapping_groups, protected_resources=protected, capacity_proof_only=True
        )

    mixable_ranks = spec.workload._get_ranks_that_share_indexing_rank_variables()

    aliased_tensors = spec.workload.get_tensor_copies()

    n_mappings = {}
    runtime = {}
    nbuckets = []

    n_evaluations = 0

    pmapping_groups = list(pmapping_groups.items())

    if not skip_invalid:
        lookahead_filter = False

    for einsum_name, s in pmapping_groups:
        if not s:
            raise ValueError(f"No pmappings for {einsum_name}")

    timer = JoiningTimer()

    pmgroups = [PmappingsOneEinsum(*s) for s in pmapping_groups]

    if not pmgroups:
        raise ValueError("No pmappings to join")

    # ======================================================================
    # Initial consolidate and group all PmappingGroups
    # ======================================================================
    n_mappings["Post Intra-Layer"] = 0
    for i, einsum_pmappings in enumerate(pmgroups):
        cur_tensors = einsum_pmappings.tensor_names
        right_tensors = set.union(set(), *[s.tensor_names for s in pmgroups[i + 1 :]])
        # First Einsum: Remove dead tensors and left consolidate. This is because the
        # first Einsum will have the first pmappigns that are joined from the left
        if i == 0:
            if cur_tensors - right_tensors:
                PmappingGroup.remove_dead_tensors(
                    einsum_pmappings.pmapping_groups, right_tensors
                )
                for s in einsum_pmappings.pmapping_groups:
                    s.compatibility = s.compatibility.clear_dead_tensors(right_tensors)
            einsum_pmappings.pmapping_groups = PmappingGroup.left_consolidate(
                einsum_pmappings.pmapping_groups,
                right_tensors,
                parallelize=False,  # We're not pareto pruning, so parallelization doesn't help.
                pbar=f"Inital consolidate {einsum_pmappings.einsum_name} ({i+1}/{len(pmgroups)})",
            )
            continue

        # All other Einsums: Will be joined from the right. Remove dead tensors, right
        # consolidate, combine, group.
        t0 = time.time()
        left_tensors = set.union(set(), *[s.tensor_names for s in pmgroups[:i]])
        live_tensors = right_tensors
        shared_tensors = left_tensors & einsum_pmappings.tensor_names

        if cur_tensors - (right_tensors | left_tensors):
            PmappingGroup.remove_dead_tensors(
                einsum_pmappings.pmapping_groups, right_tensors | left_tensors
            )
            for s in einsum_pmappings.pmapping_groups:
                s.compatibility = s.compatibility.clear_dead_tensors(
                    right_tensors | left_tensors
                )

        einsum_pmappings.pmapping_groups = sorted(
            einsum_pmappings.pmapping_groups,
            key=lambda x: len(x.mappings.data),
            reverse=True,
        )
        einsum_pmappings.pmapping_groups = PmappingGroup.right_consolidate(
            einsum_pmappings.pmapping_groups,
            live_tensors,
            shared_tensors,
            parallelize=False,  # We're not pareto pruning, so parallelization doesn't help.
            pbar=f"Inital consolidate {einsum_pmappings.einsum_name} ({i+1}/{len(pmgroups)})",
        )
        einsum_pmappings.pmapping_groups = PmappingGroup.combine_combineable(
            einsum_pmappings.pmapping_groups,
            left_tensors | right_tensors,
            combine_reservations=combine_reservations,
            pbar_postfix=f" for {einsum_pmappings.einsum_name} ({i+1}/{len(pmgroups)})",
        )
        n_mappings["Post Intra-Layer"] += sum(
            len(s.mappings.data) for s in einsum_pmappings.pmapping_groups
        )
        einsum_pmappings.pmapping_groups = PmappingGroup.group(
            einsum_pmappings.pmapping_groups, left_tensors
        )
        einsum, prev_einsum = einsum_pmappings.einsum_name, pmgroups[i - 1].einsum_name
        runtime[f"{prev_einsum} → {einsum}"] = time.time() - t0
        t0 = time.time()
    timer.print_time(f"Initial consolidate and group")

    n_iterations = 1
    total_iterations = len(pmgroups)
    holder = pmgroups.pop(0)
    left, left_einsum, left_tensors = holder.pmapping_groups, holder.einsum_name, holder.tensor_names
    partial_mapping_size = 1
    return PartialState(context=context, processed=(left_einsum,),
        left=left,
        left_einsum=left_einsum,
        left_tensors=left_tensors,
        pmgroups=pmgroups,
        total_iterations=total_iterations,
        n_iterations=n_iterations,
        drop_valid_reservations=drop_valid_reservations,
        ignored_resources=ignored_resources,
        mixable_ranks=mixable_ranks,
        aliased_tensors=aliased_tensors,
        timer=timer,
        n_mappings=n_mappings,
        runtime=runtime,
        nbuckets=nbuckets,
        n_evaluations=n_evaluations,
        partial_mapping_size=partial_mapping_size)


def _advance_owned(state):
    from .join_pmappings import (Metrics, PmappingGroup, PmappingsOneEinsum,
        JoiningTimer, get_memories_to_track, col2nameloop, _with_compatibility,
        parallel, logger)
    import os, time, itertools
    state.context.check_environment()
    context = state.context
    contract = _contract(context)
    spec = contract['spec']
    skip_invalid = contract['skip_invalid']
    combine_reservations = contract['combine_reservations']
    lookahead_filter = contract['lookahead_filter']
    _pmapping_row_filter_function = contract['_pmapping_row_filter_function']
    _terminal_branch_observer = contract['_terminal_branch_observer']
    left = state.left
    left_einsum = state.left_einsum
    left_tensors = state.left_tensors
    pmgroups = state.pmgroups
    total_iterations = state.total_iterations
    n_iterations = state.n_iterations
    drop_valid_reservations = state.drop_valid_reservations
    ignored_resources = state.ignored_resources
    mixable_ranks = state.mixable_ranks
    aliased_tensors = state.aliased_tensors
    timer = state.timer
    n_mappings = state.n_mappings
    runtime = state.runtime
    nbuckets = state.nbuckets
    n_evaluations = state.n_evaluations
    partial_mapping_size = state.partial_mapping_size
    t0 = time.time()
    # ======================================================================
    # Check that data dependencies are satisfied.
    # ======================================================================
    for s in pmgroups:
        output_tensors = spec.workload.einsums[s.einsum_name].output_tensor_names
        shared_fail = left_tensors & output_tensors
        if shared_fail:
            raise ValueError(
                f"Einsum {left_einsum} uses tensors {sorted(shared_fail)} that "
                f"are outputs of Einsum {s.einsum_name}, which is later in the "
                f"joining order."
            )

    # ======================================================================
    # Grab new Einsum from the right. Record logging data and find still
    # tensors that will be live after this Einsum.
    # ======================================================================
    nbuckets.append(len(left))
    # nmappings.append(sum(len(s.mappings.data) for s in left))
    holder = pmgroups.pop(0)
    n_iterations += 1
    right, right_einsum, right_tensors = holder.pmapping_groups, holder.einsum_name, holder.tensor_names
    logger.info(f"Einsum {right_einsum} ({n_iterations}/{total_iterations})")

    partial_mapping_size += 1

    live_tensors = set.union(set(), *[s.tensor_names for s in pmgroups])
    shared_tensors = set(left_tensors) & set(right_tensors)
    live_tensors_with_right = live_tensors | right_tensors

    # ======================================================================
    # Clean up the previously-combined PmappingGroups. Consolidate, combine, group
    # them into buckets.
    # ======================================================================
    # print_time(f"Consolidating")

    left = PmappingGroup.combine_combineable(
        left,
        live_tensors | right_tensors,
        combine_reservations=combine_reservations,
    )

    # print_time(f"Combining")
    # Group left and right into buckets
    left = PmappingGroup.group(left, right_tensors)
    # print_time("Grouping")

    # ======================================================================
    # Remove dead tensors from left and right. This happens after grouping because
    # we only reserve space for shared tensors after they're dead (alive is handled
    # by the normal reservation system). This is in case the tensor lifetime extends
    # beyond the Einsums for which it is used.
    # ======================================================================
    PmappingGroup.remove_dead_tensors(
        [s for lr in [left, right] for v in lr.values() for s, _ in v], live_tensors
    )

    DO_PRINT = False
    DELAY = True
    # ======================================================================
    # Merge the left and right buckets.
    # ======================================================================
    combined: list[PmappingGroup] = []
    cur_nmappings = 0
    combined_ids: set[tuple[int, int, tuple[tuple[int, int], ...]]] = set()

    for k in left:
        found = False
        if DO_PRINT:
            print(f"Left key {k}")
        for (a, perm_a), (b, perm_b) in itertools.product(
            left[k], right.get(k, [])
        ):
            a: PmappingGroup
            b: PmappingGroup
            perm_a: list[int]
            perm_b: list[int]
            key_check = (
                id(a),
                id(b),
                tuple((pa, pb) for pa, pb in zip(perm_a, perm_b)),
            )
            if key_check in combined_ids:
                continue
            combined_ids.add(key_check)
            found = True

            compatibility_a = a.compatibility.permute(perm_a)
            compatibility_b = b.compatibility.permute(perm_b)
            try:
                compatibility_joined = compatibility_a.merge_next(
                    compatibility_b,
                    live_tensors,
                    mixable_ranks,
                )
                if DO_PRINT:
                    print(
                        f"\t{a.compatibility}        <-->        {b.compatibility}"
                    )
            except ValueError as e:  # Incompatible!
                # if DO_PRINT:
                #     print(f"\tIncompatible: {e}")
                continue

            if _terminal_branch_observer is not None and total_iterations == 2 and not pmgroups:
                # Read-only opt-in research hook. This does not discard a
                # group, alter an incumbent, or expose mutable frames.
                from accelforge.mapper.FFM._join_pmappings.branch_summary import BranchSummary
                try:
                    pair_plan = a.mappings._matching_pair_plan(b.mappings, compatibility_a, compatibility_b)
                    matched_pairs = (sum(len(left)*len(right) for left,right in pair_plan)
                                     if pair_plan is not None else None)
                except (KeyError, TypeError, ValueError):
                    matched_pairs = None
                summary = BranchSummary.from_frames(
                    a.mappings.data, b.mappings.data,
                    compatibility_a.tensor_names & compatibility_b.tensor_names,
                    matched_pairs=matched_pairs,
                )
                _terminal_branch_observer(summary)

            t0 = time.time()

            combined.append(
                _with_compatibility(a, compatibility_a).merge_next(
                    _with_compatibility(b, compatibility_b),
                    live_tensors,
                    live_tensors_with_right,
                    aliased_tensors,
                    compatibility_joined=compatibility_joined,
                    drop_valid_reservations=drop_valid_reservations,
                    delay=DELAY,
                    _pmapping_row_filter_function=_pmapping_row_filter_function,
                    ignored_resources=ignored_resources,
                )
            )
            t1 = time.time()
            # print(f'Took {t1 - t0:.2f} seconds to generate {len(combined[-1].mappings.data)} mappings')

            if not DELAY:
                cur_nmappings += len(a.mappings.data) * len(b.mappings.data)
            if DO_PRINT:
                # s = f"\t-->\n\t{combined[-1].compatibility}"
                # s += f"({len(a.mappings.data)})x({len(b.mappings.data)})"
                # print(s)
                pass
        if DO_PRINT and not found:
            for a, _ in left[k]:
                print(f"\tNo match for {a.compatibility}")

    if DO_PRINT:
        for k in right:
            if k not in left:
                for b, _ in right[k]:
                    print(f"\tREVERSE: No match for {b.compatibility} using {k}")

    # print_time("Bucket merging")
    def raise_no_match_error():
        estr = f"No match found for any group.\n"
        estr += f"Left compatibility:\n\t" + "\n\t".join(
            str(c) for c in left.keys()
        )
        estr += f"\nRight compatibility:\n\t" + "\n\t".join(
            str(c) for c in right.keys()
        )
        raise ValueError(estr)

    def no_match_lookahead_error(
        combined: list[PmappingGroup],
        next_keys: set[tuple[int, int, tuple[tuple[int, int], ...]]],
    ):
        estr = f"No match found for any group. Left and right joined successfully, "
        estr += f"but will not be compatible with following Einsums.\n"
        estr += f"Left compatibility:\n\t" + "\n\t".join(
            str(s.compatibility) for g in left.values() for s, _ in g
        )
        estr += f"\nRight compatibility:\n\t" + "\n\t".join(
            str(s.compatibility) for g in right.values() for s, _ in g
        )
        estr += f"\nCombined compatibility:\n\t" + "\n\t".join(
            str(s.compatibility) for s in combined
        )
        estr += f"\nFollowing Einsum compatibility:\n\t" + "\n\t".join(
            str(c) for c in next_keys
        )
        raise ValueError(estr)

    # ======================================================================
    # Look ahead to the next Einsum and see if any of our groups will not
    # be able to merge with it. If so, we can drop them immediately.
    # ======================================================================
    if lookahead_filter:
        cur_tensors = left_tensors | right_tensors
        for next_pmapping_groups in pmgroups:
            next_right_tensors = next_pmapping_groups.tensor_names
            if not next_right_tensors & cur_tensors:
                continue
            prev_combined = combined
            combined = PmappingGroup.group(combined, next_right_tensors)
            next_keys = {
                c.clear_dead_tensors(
                    cur_tensors
                ).clear_tile_patterns_and_reservation_indices()
                for c in next_pmapping_groups.pmapping_groups
            }
            for k in list(combined):
                k_cleared = k.clear_dead_tensors(
                    next_right_tensors
                ).clear_tile_patterns_and_reservation_indices()
                if k_cleared not in next_keys:
                    if DO_PRINT:
                        for b, _ in combined[k]:
                            print(
                                f"\tLOOKAHEAD to {next_pmapping_groups.einsum_name}: No match for {b.compatibility}"
                            )
                    del combined[k]
            if not combined:
                PmappingGroup.group(prev_combined, next_right_tensors)
                no_match_lookahead_error(prev_combined, next_keys)

            combined = list(itertools.chain.from_iterable(combined.values()))
            combined = [c[0] for c in combined]
            # Remove duplicates
            id2combined = {id(c): c for c in combined}
            combined = list(id2combined.values())
            # print(
            #     f"Removed {prev_len - len(combined)}/{prev_len} ({len(combined)/prev_len*100:.2f}% remaining)"
            # )
            # print_time("Removing mappings that can't be combined later")

    if not combined:
        raise_no_match_error()

    # ======================================================================
    # If we delayed the mapping merging, do it now.
    # ======================================================================
    if DELAY:
        mappings = parallel(
            [c.mappings for c in combined],
            pbar=f"Joining pmappings for {left_einsum} <--> {right_einsum} ({n_iterations}/{total_iterations})",
            return_as="generator",
        )
        for c, mapping in zip(combined, mappings):
            c.mappings = mapping
            cur_nmappings += c.n_pre_prune_mappings
    timer.print_time("Pmapping merging")

    if not any(len(s.mappings.data) for s in combined):
        raise ValueError(f"No mappings found for {left_einsum} <--> {right_einsum}")

    prev_nmappings = cur_nmappings
    if not skip_invalid:
        left_nmappings = sum(len(s.mappings.data) for k in left.values() for s in k)
        right_nmappings = sum(
            len(s.mappings.data) for k in right.values() for s in k
        )
        cur_nmappings = left_nmappings * right_nmappings
    n_mappings[f"{left_einsum} → {right_einsum}"] = cur_nmappings
    n_evaluations += cur_nmappings
    runtime[f"{left_einsum} → {right_einsum}"] += (time.time() - t0) * (
        cur_nmappings / prev_nmappings
    )
    # print(
    #     f'Scaled runtime by {cur_nmappings / prev_nmappings}. Runtime: {runtime[f"{prev_einsum} → {einsum}"]:.2f}'
    # )

    # ======================================================================
    # Print statements
    # ======================================================================
    logger.info(
        f"\tCombining {sum(len(s) for s in left.values())}({len(left)}) x {sum(len(s) for s in right.values())}({len(right)}) -> {len(combined)}"
    )

    nmappings = sum(len(s.mappings.data) for s in combined)
    for_einsum_text = f"for Einsum {right_einsum}"
    logger.info(f"\tNumber of groups {for_einsum_text}: {len(combined)}")
    # for c in combined:
    #     print(f"\t\t{c.compatibility}")
    logger.info(f"\tNumber of mappings {for_einsum_text}: {nmappings}")
    logger.info(
        f"\tMappings per group {for_einsum_text}: {nmappings / len(combined)}"
    )
    logger.info(
        f"\tLargest left: {max(len(s2.mappings.data) for s in left.values() for s2, _ in s)}"
    )
    logger.info(
        f"\tLargest right: {max(len(s2.mappings.data) for s in right.values() for s2, _ in s)}"
    )

    # ======================================================================
    # Update left for the next iteration.
    # =================================================================
    left = combined
    left_einsum = right_einsum
    left_tensors |= right_tensors


    state.left = left
    state.left_einsum = left_einsum
    state.left_tensors = left_tensors
    state.pmgroups = pmgroups
    state.total_iterations = total_iterations
    state.n_iterations = n_iterations
    state.drop_valid_reservations = drop_valid_reservations
    state.ignored_resources = ignored_resources
    state.mixable_ranks = mixable_ranks
    state.aliased_tensors = aliased_tensors
    state.timer = timer
    state.n_mappings = n_mappings
    state.runtime = runtime
    state.nbuckets = nbuckets
    state.n_evaluations = n_evaluations
    state.partial_mapping_size = partial_mapping_size
    state.processed += (right_einsum,)
    state.joins_completed += 1
    return state


def _finalize_owned(state):
    from .join_pmappings import (Metrics, PmappingGroup, PmappingsOneEinsum,
        JoiningTimer, get_memories_to_track, col2nameloop, _with_compatibility,
        parallel, logger)
    import os, time, itertools
    state.context.check_environment()
    left, timer = state.left, state.timer
    # ======================================================================
    # Final consolidate and group
    # ======================================================================
    t0 = time.time()
    left = PmappingGroup.left_consolidate(left, None, pbar="Final consolidate")
    s_final = PmappingGroup.combine_combineable(left, set())
    assert len(s_final) == 1
    mappings = s_final[0].mappings

    timer.log_total_time()
    # if evaluations_tracker is not None and "Total_latency" in data.columns and "Total_energy" in data.columns:
    #     edp = data["Total_latency"] * data["Total_energy"]
    #     edp_min = edp.min()
    #     evaluations_tracker.add_evaluation(n_evaluations, edp_min)
    #     evaluations_tracker.n_mappings.update(n_mappings)
    #     evaluations_tracker.runtime.update(runtime)

    return mappings



def start(pmapping_groups, context):
    return _start_owned(deepcopy(pmapping_groups), context)


def advance(state, next_einsum=None, context=None):
    if context is not None:
        context.require_same(state.context)
    state.context.check_environment()
    if not state.remaining:
        raise ValueError('no remaining Einsum to advance')
    if next_einsum is not None and next_einsum != state.remaining[0]:
        raise ValueError('reference-order Join must advance the next Einsum')
    return _advance_owned(deepcopy(state))


def finalize(state, context=None):
    if context is not None:
        context.require_same(state.context)
    if state.remaining:
        raise ValueError('cannot finalize before all Einsums are joined')
    return _finalize_owned(deepcopy(state))
