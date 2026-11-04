from collections import defaultdict
from copy import copy
import itertools
import logging
import os
import time
from fractions import Fraction
from typing import Callable

from accelforge._accelerated_imports import pd
from accelforge.frontend.spec import Spec
from accelforge.frontend.mapping import Mapping
from accelforge.frontend.mapper.metrics import Metrics
from accelforge.frontend.workload import EinsumName
from accelforge.mapper.FFM.mappings import Mappings
from accelforge.mapper.FFM.pmappings import MultiEinsumPmappings
from accelforge.mapper.FFM._join_pmappings.compress_pmappings import (
    compress_einsum2pmappings,
    decompress_pmappings,
)
from accelforge.mapper.FFM._make_pmappings.make_pmappings import (
    get_rank_variable_bounds_for_all_einsums,
)
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import (
    row2pmappings,
)
from accelforge.mapper.FFM._pareto_df.df_convention import MAPPING_COLUMN
from accelforge.mapper.FFM._join_pmappings.pmapping_group import (
    PmappingGroup,
    Compatibility,
)
from accelforge.mapper.FFM._pareto_df.df_convention import col2nameloop
from accelforge.util import parallel, delayed
from accelforge.mapper.FFM._pareto_df import exact_resources as exact


logger = logging.getLogger(__name__)


def _with_compatibility(group, compatibility):
    """Use the selected loop permutation for numeric matching as well as grouping.

    Loop symbols still name their original dataframe columns; permuting the
    compatibility changes which columns must match, not their values. Preserve
    the group's full tensor bookkeeping (including tensors no longer in its
    live compatibility) and avoid mutating a group shared by other Join tasks.
    """
    result = copy(group)
    result.compatibility = compatibility
    result.tensors = dict(group.tensors)
    result.tensors.update((t.name, t) for t in compatibility.tensors)
    return result


class JoiningTimer:
    def __init__(self):
        self.prev_time = time.time()
        self.total_time = defaultdict(int)

    def print_time(self, what: str):
        t = time.time() - self.prev_time
        logger.info(f"{what}: {t:.2f} seconds")
        self.total_time[what] += t
        self.prev_time = time.time()

    def log_total_time(self):
        logger.info(f"\n======== Total time ========")
        for k, v in self.total_time.items():
            logger.info(f"{k}: {v:.2f} seconds")
        total = sum(self.total_time.values())
        if total > 60:
            logger.info(f"\nTotal: {total:.2f} seconds ({total/60:.2f} minutes)")
        else:
            logger.info(f"\nTotal: {total:.2f} seconds")
        logger.info(f"============================\n")


def clean_compress_and_join_pmappings(
    pmappings: MultiEinsumPmappings,
    require_all_einsums: bool = True,
    _pmapping_row_filter_function: Callable[[pd.Series], bool] | None = None,
    _terminal_branch_observer: Callable | None = None,
) -> Mappings:
    einsum2pmappings = pmappings.einsum2pmappings
    if not require_all_einsums:
        einsum2pmappings = {
            k: v
            for k, v in pmappings.einsum2pmappings.items()
            if k in pmappings.einsums_with_pmappings_generated
        }
    _check_einsum2pmappings_not_empty(einsum2pmappings, pmappings)

    compressed, decompress_data = compress_einsum2pmappings(einsum2pmappings)
    joined = join_pmappings(
        compressed,
        pmappings.spec,
        _pmapping_row_filter_function=_pmapping_row_filter_function,
        _terminal_branch_observer=_terminal_branch_observer,
    )
    return restore_mappings(pmappings, joined, decompress_data, tuple(einsum2pmappings))


def restore_mappings(pmappings, joined, decompress_data, einsum_names):
    """Shared source/decompression path for full and resumed Join results."""
    einsum2pmappings = {name: pmappings.einsum2pmappings[name] for name in einsum_names}
    joined = decompress_pmappings(joined, decompress_data)

    for einsum_name in einsum2pmappings:
        col = f"{einsum_name}<SEP>{MAPPING_COLUMN}"
        joined.data[col] = joined.data[col].apply(
            lambda x: pmappings.pmapping_objects[einsum_name][x]
        )
    joined._data = joined.data.fillna(0).reset_index(drop=True)

    rank_variable_bounds = get_rank_variable_bounds_for_all_einsums(pmappings.spec)
    einsum_names = list(einsum2pmappings.keys())
    joined.data[f"Total<SEP>{MAPPING_COLUMN}"] = [
        MappingFromRow(r, rank_variable_bounds, einsum_names)
        for _, r in joined.data.iterrows()
    ]
    # Fill nans with 0. We might get missing columns for some mapping entries if there
    # are energy entries for some pmappings but not others (e.g., one pmapping accesses
    # DRAM while another doesn't.)
    return Mappings(
        pmappings.spec,
        list(
            x
            for x in list(einsum2pmappings.keys())
            if x in pmappings.einsums_with_pmappings_generated
        ),
        exact.public_frame(joined.data),
        total_mappings=joined.n_total_pmappings,
        valid_mappings=joined.n_valid_pmappings,
        flattened_arches=pmappings.flattened_arches,
        evaluated_specs=pmappings.evaluated_specs,
    )


class PmappingsOneEinsum:
    def __init__(self, einsum_name: str, pm_group_list: list[PmappingGroup]):
        self.einsum_name: str = einsum_name
        self.pmapping_groups: list[PmappingGroup] = pm_group_list
        self.tensor_names: set[str] = set(pm_group_list[0].tensor_names)

    def __getitem__(self, i):
        return self.pmapping_groups[i]


def make_full_equivalent_rank_variables(pairwise_equivalent_rank_variables):
    full_equivalent_rank_variables = {
        k: set(v) for k, v in pairwise_equivalent_rank_variables.items()
    }
    changed = True
    while changed:
        changed = False
        for r in full_equivalent_rank_variables:
            for r2 in list(full_equivalent_rank_variables[r]):
                for r3 in list(full_equivalent_rank_variables[r2]):
                    if r3 in full_equivalent_rank_variables[r]:
                        continue
                    changed = True
                    full_equivalent_rank_variables[r].add(r3)
    return full_equivalent_rank_variables


def get_memories_to_track(
    pmapping_groups: dict[str, list[PmappingGroup]],
    protected_resources: frozenset[str] = frozenset(),
    capacity_proof_only: bool = False,
) -> tuple[dict[str, list[PmappingGroup]], set[str], set[str]]:

    always_below = set()
    for _, einsum_pmapping_groups in pmapping_groups.items():
        for s in einsum_pmapping_groups:
            for col in s.mappings.data.columns:
                name_nloops = col2nameloop(col)
                if name_nloops is not None:
                    always_below.add(col2nameloop(col)[0])

    total_sizes = {}
    ignored_resources = set()

    for _, einsum_pmapping_groups in pmapping_groups.items():
        max_sizes = {}
        for s in einsum_pmapping_groups:
            n_fused_loops = s.compatibility.n_loops
            for col in s.mappings.data.columns:
                name_nloops = col2nameloop(col)
                if name_nloops is None:
                    continue

                name, nloops = name_nloops
                if name in always_below and nloops < n_fused_loops:
                    always_below.remove(name)
                # Check each of the compatibility's tensors
                for tensor in s.compatibility.tensors:
                    if tensor.resource_name in always_below:
                        always_below.remove(tensor.resource_name)
                size = s.mappings.data[col].max()
                if exact.capacity_column(name) in s.mappings.data:
                    bound = exact.capacity(s.mappings.data,name)
                    size = Fraction(exact.integer_bits(size),bound) if bound else (0 if size == 0 else float('inf'))
                max_sizes[name] = max(max_sizes.get(name, 0), size)

                # nloops < 0 means that the reservation will live through all Einsums
                if nloops < 0:
                    ignored_resources.add(name)

        for name, size in max_sizes.items():
            total_sizes[name] = total_sizes.get(name, 0) + size

    # Protected resources remain objectives even when capacity is ample. In
    # selective mode only remove a fixed resource when the sum of per-Einsum
    # maxima proves it cannot overflow, including across simultaneous lifetimes.
    ignore = set(t for t, s in total_sizes.items() if s <= 1)
    if not capacity_proof_only:
        ignore |= always_below
    ignore -= protected_resources

    if not ignore:
        return pmapping_groups, ignore

    def remove_unneeded_columns(s: PmappingGroup):
        data = s.mappings.data
        keep_cols = []
        for col in data.columns:
            name_nloops = col2nameloop(col)
            if name_nloops is None or name_nloops[0] not in ignore:
                keep_cols.append(col)
        run_pareto = len(keep_cols) < len(data.columns)
        return PmappingGroup(
            s.compatibility,
            s.mappings.update(data=data[keep_cols], skip_pareto=not run_pareto),
        )

    for a in sorted(always_below & ignore):
        print(f"Not tracking {a} because it is never reserved for multiple pmappings.")
    for t, s in sorted(total_sizes.items(), key=lambda x: x[1], reverse=True):
        if s <= 1 and t in ignore:
            print(
                f"Not tracking {t} because its size is enough for the sum of all "
                f"reservations ({s * 100:.2f}% of the total)"
            )
            break

    new_pmapping_groups = {}
    for einsum_name, einsum_pmapping_groups in pmapping_groups.items():
        new_pmapping_groups[einsum_name] = list(
            parallel(
                [delayed(remove_unneeded_columns)(s) for s in einsum_pmapping_groups],
                pbar=f"Removing unneeded reservations for {einsum_name}",
                return_as="generator",
            )
        )
    return new_pmapping_groups, ignore


def join_pmappings(
    pmapping_groups: dict[str, list[PmappingGroup]],
    spec: Spec,
    skip_invalid: bool = True,
    combine_reservations: bool = True,
    lookahead_filter: bool = True,
    metrics: Metrics = None,
    _pmapping_row_filter_function: Callable[[pd.Series], bool] | None = None,
    _terminal_branch_observer: Callable | None = None,
):
    """Run the original reference-order kernel to completion on owned inputs.

    As before, this low-level entry point may mutate its group inputs. The
    resumable public engine isolates input and state copies instead.
    """
    from .join_context import JoinContext
    from .join_engine import _start_owned, _advance_owned, _finalize_owned
    context = JoinContext.from_spec(spec, skip_invalid=skip_invalid,
        combine_reservations=combine_reservations, lookahead_filter=lookahead_filter,
        row_filter=_pmapping_row_filter_function, terminal_observer=_terminal_branch_observer)
    state = _start_owned(pmapping_groups, context)
    while state.remaining:
        state = _advance_owned(state)
    return _finalize_owned(state)


def _check_einsum2pmappings_not_empty(einsum2pmappings, pmappings):
    for einsum_name, einsum_pmappings in einsum2pmappings.items():
        total = sum(len(p.mappings.data) for p in einsum_pmappings)
        n_compatibilities = len(einsum_pmappings)
        logger.info(
            f"Einsum {einsum_name} has {total} pmappings with {n_compatibilities} compatibilities"
        )
        if total == 0:
            if einsum_name in pmappings.einsums_with_pmappings_generated:
                raise ValueError(
                    f"Einsum {einsum_name} has no pmappings. This likely means that "
                    f"no pmappings satisfied constraints for the Einsum. Please check "
                    f"the stats outputs from the MultiEinsumPmappings object returned "
                    f"by `af.mapper.FFM.make_pmappings(spec)`."
                )

            raise ValueError(
                f"Einsum {einsum_name} has no pmappings generated. It looks like you "
                "may have used `make_pmappings` with `einsum_names` set. You may set "
                "`require_all_einsums=False` to ignore this error and map only the "
                "Einsums that have pmappings."
            )


class MappingFromRow:
    def __init__(
        self,
        row: pd.Series,
        rank_variable_bounds: dict[str, dict[str, int]],
        einsum_names: list[EinsumName] | None = None,
    ):
        self.row = row
        self.rank_variable_bounds = rank_variable_bounds
        self.einsum_names = einsum_names

    def __call__(self) -> Mapping:
        return Mapping._from_pmappings(
            row2pmappings(self.row, self.einsum_names, self.rank_variable_bounds),
            rank_variable_bounds=self.rank_variable_bounds,
        )

    def _repr_svg_(self) -> str:
        return self.render()

    def render(self) -> str:
        return self().render()
