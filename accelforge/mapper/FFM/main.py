from copy import deepcopy
import inspect
import os
from typing import Callable
import joblib
import logging

from accelforge import arch
from accelforge import Spec
from accelforge.mapper.FFM.pmappings import MultiEinsumPmappings
from accelforge.mapper.FFM.mappings import Mappings
import accelforge.mapper.FFM._make_pmappings.make_pmappings as pmapper
from accelforge.frontend.workload import EinsumName
from accelforge.mapper.FFM._join_pmappings.join_pmappings import (
    clean_compress_and_join_pmappings,
)
from accelforge.mapper.FFM._join_pmappings.join_pmappings import (
    _check_einsum2pmappings_not_empty,
)
from accelforge._accelerated_imports import pd
from accelforge.mapper.FFM._pareto_df import pareto as pareto_module
from accelforge.mapper.FFM.generation_contract import GenerationContract


logger = logging.getLogger(__name__)

# Invalidate candidates produced before the shared formula-goal cache fix.
# Bump when generation semantics change outside the cached wrapper's source.
_GENERATION_CACHE_VERSION = 3  # Persist generation provenance in new cache entries.

# These options affect the generated candidate set, not only Join execution.
# Keep this list in sync with new generation switches in _make_pmappings.
_GENERATION_ENV_VARS = (
    "AF_ENUMERATION_PREFIX_BYTES",  # Also separates cached work statistics.
    "AF_ENUMERATION_PARETO_BYTES",
    "AF_TARGET_ENUMERATION",
    "AF_CAPACITY_MEMBERSHIP",
    "AF_RESOURCE_UNITS",
    "AF_GENERATION_CAPACITY_BITS",
    "AF_LATENCY_SCALES",
    "AF_GENERATION_CAPACITY_FRACTIONS",
    "AF_GENERATION_VARIABLE_RESOURCES",
    "AF_ABL_ALLOW_UNREPRESENTABLE",
    "AF_ABL_SKIP_BIG_ENOUGH",
    "AF_ABL_SKIP_PMAPPING_ONLY",
    "AF_ABL_BIG_ENOUGH_UNTRACK_ONLY",
)


def map_workload_to_arch(
    spec: Spec,
    einsum_names: list[EinsumName] | None = None,
    can_combine_multiple_runs: bool = False,
    cache_dir: str | None = None,
    print_number_of_pmappings: bool = True,
    _pmapping_row_filter_function: Callable[[pd.Series], bool] | None = None,
) -> Mappings:
    """
    Maps a workload to an architecture using the AccelForge Fast and Fusiest Mapper
    (FFM).

    Parameters
    ----------
    spec:
        The Spec to map.
    einsum_names:
        The einsum names to map. If None, all einsums will be mapped.
    can_combine_multiple_runs:
        If True, allows combining multiple make_pmappings runs (e.g.
        ``pmappings = make_pmappings(*args_a) | make_pmappings(*args_b)``).
        Set to False for faster execution.
    cache_dir:
        The directory to cache pmappings in. If None, no caching will be done.
    print_number_of_pmappings:
        Whether to print the number of pmappings for each einsum.
    _pmapping_row_filter_function:
        A function that takes in a row of the pmapping dataframe and returns True if the
        row should be included in the final mappings, and False otherwise. If None, all
        rows will be included.
    """
    from accelforge.model.main import evaluate_mapping

    pmappings = make_pmappings(
        spec,
        einsum_names=einsum_names,
        can_combine_multiple_runs=can_combine_multiple_runs,
        cache_dir=cache_dir,
        print_number_of_pmappings=print_number_of_pmappings,
    )

    mappings = join_pmappings(
        pmappings,
        require_all_einsums=False,
        _pmapping_row_filter_function=_pmapping_row_filter_function,
    )

    from accelforge.frontend.mapper.metrics import Metrics
    from accelforge.mapper.FFM._pareto_df.capacity_membership import is_membership_col, is_excluded_col
    membership_columns = [c for c in mappings.data if is_membership_col(c) or is_excluded_col(c)]
    new_mapping_data = []
    for i in range(len(mappings.data)):
        local_spec = deepcopy(spec)
        local_spec.model.metrics = local_spec.mapper.ffm.info_metrics
        if membership_columns:
            local_spec.model.metrics |= Metrics.RESOURCE_USAGE
        local_spec.mapping = mappings.data.iloc[i]["Total<SEP>mapping"]()
        # BUG: Mapping._from_pmappings create mappings that cannot be evaluated!
        this_mapping = evaluate_mapping(
            local_spec,
            flattened_arches=mappings.flattened_arches,
            evaluated_specs=mappings.evaluated_specs,
        )
        if len(this_mapping.data) != 1:
            raise ValueError('mapping re-evaluation must return exactly one source-associated row')
        data = this_mapping.data.copy()
        # Membership describes the source search policy, not the re-evaluated
        # physical mapping. Carry it positionally without a mixed-dtype Series
        # conversion (which can lose the top bits of a uint64 word).
        for column in membership_columns:
            data[column] = mappings.data[column].iloc[i:i+1].to_numpy(copy=True)
        new_mapping_data.append(data)

    if new_mapping_data:
        mappings.data = pd.concat(new_mapping_data, ignore_index=True)

    return mappings


def make_pmappings(
    spec: Spec,
    einsum_names: list[EinsumName] | None = None,
    can_combine_multiple_runs: bool = False,
    cache_dir: str | None = None,
    print_number_of_pmappings: bool = True,
) -> MultiEinsumPmappings:
    """
    Creates pmappings for a spec. Pmappings must be joined together using
    `join_pmappings` to create a full mapping.

    Parameters
    ----------
    spec:
        The Spec to generate pmappings for.
    einsum_names:
        The einsum names to generate pmappings for. If None, all einsums will be
        included.
    can_combine_multiple_runs:
        If True, allows combining multiple make_pmappings runs (e.g.
        ``pmappings = make_pmappings(*args_a) | make_pmappings(*args_b)``).
        Set to False for faster execution.
    cache_dir:
        The directory to cache pmappings in. If None, no caching will be done.
    print_number_of_pmappings:
        Whether to print the number of pmappings for each einsum.

    Returns:
        A MultiEinsumPmappings object.
    """
    kwargs = dict(
        spec=spec,
        einsum_names=einsum_names,
        can_combine_multiple_runs=can_combine_multiple_runs,
    )
    assert len(kwargs) == len(inspect.signature(_make_pmappings).parameters)

    if cache_dir is None:
        result = _make_pmappings(**kwargs)
    else:

        @joblib.Memory(location=os.path.join(cache_dir), compress=True).cache
        def _make_pmappings_cached(generation_options, **kwargs) -> MultiEinsumPmappings:
            # Explicit cache-key input: generation reads these options outside Spec.
            return _make_pmappings(**kwargs)

        generation_options = {
            name: os.environ.get(name) for name in _GENERATION_ENV_VARS
        }
        generation_options["pareto_tolerance"] = pareto_module.TOLERANCE
        generation_options["generation_cache_version"] = _GENERATION_CACHE_VERSION
        result = _make_pmappings_cached(generation_options, **kwargs)

    if print_number_of_pmappings:
        print(result.n_pmapping_string())

    return result


def join_pmappings(
    pmappings: MultiEinsumPmappings,
    require_all_einsums: bool = True,
    _pmapping_row_filter_function: Callable[[pd.Series], bool] | None = None,
    _terminal_branch_observer: Callable | None = None,
) -> Mappings:
    """
    Joins pmappings into a full mappings for the entire workload. Pmappings can
    be generated using `make_pmappings`.

    Parameters
    ----------
    pmappings:
        The pmappings to join.
    require_all_einsums:
        If True, all einsums in the workload must have pmappings. If False, only
        einsums that have pmappings will be included in the final mappings.
    _pmapping_row_filter_function:
        A function that takes in a row of the pmapping dataframe and returns
        True if the row should be included in the final mappings, and False
        otherwise. If None, all rows will be included.

    Returns
    -------
    Mappings
        A Mappings object containing all valid, optimal mappings for the workload.
    """
    return clean_compress_and_join_pmappings(
        pmappings, require_all_einsums, _pmapping_row_filter_function,
        _terminal_branch_observer,
    )


def _make_pmappings(
    spec: Spec,
    einsum_names: list[EinsumName] | None = None,
    can_combine_multiple_runs: bool = False,
) -> MultiEinsumPmappings:
    generation_contract = GenerationContract.capture(spec.mapper.ffm.metrics)
    if einsum_names is None:
        einsum_names = [e.name for e in spec.workload.einsums]

    pmapping_groups, pmapping_objects, einsum2jobs = pmapper.make_pmappings(
        spec,
        metrics=spec.mapper.ffm.metrics,
        einsum_names=einsum_names,
        can_combine_multiple_runs=can_combine_multiple_runs,
    )

    flattened_arches = {}
    evaluated_specs = {}
    for einsum_name, jobs in einsum2jobs.items():
        for job in jobs:
            compute_name = job.flattened_arch[-1].name
            flattened_arches[(einsum_name, compute_name)] = job.flattened_arch
            evaluated_specs[einsum_name] = job.spec

    m = MultiEinsumPmappings(
        spec,
        pmapping_groups,
        pmapping_objects,
        einsum2jobs,
        can_combine_multiple_runs=can_combine_multiple_runs,
        einsums_with_pmappings_generated=set(
            einsum_names if einsum_names else spec.workload.einsum_names
        ),
        flattened_arches=flattened_arches,
        evaluated_specs=evaluated_specs,
        generation_contracts=(generation_contract,),
    )

    return m
