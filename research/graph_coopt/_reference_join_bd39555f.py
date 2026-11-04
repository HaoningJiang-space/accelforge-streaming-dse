"""Frozen Join controller from bd39555f; test-only differential reference.
Source function SHA256: 9979ba2c4907a218f2bd7fb70c7545355b2b9816ff23aa7740a3ac904204731b
Numeric/group helpers intentionally remain shared; their logic is not refactored.
"""
from accelforge.mapper.FFM._join_pmappings.join_pmappings import *
from accelforge.mapper.FFM._join_pmappings.join_pmappings import _with_compatibility

def reference_join_pmappings(
    pmapping_groups: dict[str, list[PmappingGroup]],
    spec: Spec,
    # Optimality-maintaining optimizations.
    skip_invalid: bool = True,
    combine_reservations: bool = True,
    lookahead_filter: bool = True,
    metrics: Metrics = None,
    _pmapping_row_filter_function: Callable[[pd.Series], bool] | None = None,
    _terminal_branch_observer: Callable | None = None,
):
    """
    CONTRACT FOR MAPPINGS GETTING TO THIS POINT:

    - Reservations at a level include reservations at all levels above it.
    - If one Einsum uses an aliased tensor more than once, then only one
      reservation is made for it. If overlapping lifetimes cause the aliases to
      be alive at the same time, then it is handled here.
    - Memory names should be sorted with higher memory names representing
      memories lower in the hierarchy. e.g., memory 0 is the largest,
      memory 1 the next largest, and memory N is the smallest.
    """

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

    n_iterations = 0
    total_iterations = len(pmgroups)

    def grab_einsum_pmappings() -> (
        tuple[dict[Compatibility, list[PmappingGroup]], str, set[str]]
    ):
        nonlocal n_iterations
        n_iterations += 1
        holder = pmgroups.pop(0)
        return holder.pmapping_groups, holder.einsum_name, holder.tensor_names

    if pmgroups:
        left, left_einsum, left_tensors = grab_einsum_pmappings()

    partial_mapping_size = 1
    while pmgroups:
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
        right, right_einsum, right_tensors = grab_einsum_pmappings()
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
