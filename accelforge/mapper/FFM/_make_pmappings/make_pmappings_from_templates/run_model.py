from functools import lru_cache
import math

from sympy import Symbol
import accelforge.frontend.arch as arch
from accelforge.frontend.mapping import TensorHolder
from accelforge.mapper.FFM._make_pmappings.pmapper_job import Job
from accelforge.model._looptree.reuse import symbolic
from accelforge.model._looptree.reuse.symbolic import (
    analyze_reuse_and_add_reservations_to_mapping,
)
from accelforge.model._looptree.energy import (
    compute_energy_from_actions,
    gather_actions,
)
from accelforge.model._looptree.latency.memory import component_latency
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import (
    nameloop2col,
    tensor2col,
    firstlatency2col,
    action2col,
    energy2col,
)
from accelforge.mapper.FFM._pareto_df.df_convention import scaled_latency2col
from accelforge.frontend.mapper.metrics import Metrics
import sympy
from numbers import Number
from accelforge.util._sympy.broadcast_max import Max
from accelforge.mapper.FFM._pareto_df import exact_resources as exact


@lru_cache(maxsize=512)
def _maximum_latency(latencies: tuple):
    # SymPy expressions are immutable. Identical component costs occur across
    # templates; rebuilding their Max repeats expensive ordering proofs.
    return Max(*latencies) if latencies else 0


def run_model(
    job: Job,
) -> tuple[list[Symbol], dict[str, float], dict[str, float], dict[str, float]]:
    pmapping = job.mapping
    spec = job.spec
    metrics = job.metrics
    is_copy_op = job.is_copy_operation
    workload = spec.workload

    df = {}

    reuse = analyze_reuse_and_add_reservations_to_mapping(job)

    latency = component_latency(reuse, job.flattened_arch, pmapping, spec)
    try:
        overall_latency = _maximum_latency(tuple(latency.values()))
    except Exception as e:
        for k, v in latency.items():
            if not isinstance(v, (Number, sympy.Symbol, sympy.Expr)):
                raise ValueError(
                    f"Invalid type for latency: {k}: {type(v)} {str(v).strip()}"
                )

        raise ValueError(
            f"Error calculating latency for {job.einsum_name}. Could not calculate "
            f"a symbolic max of the following latencies:\n\t"
            + "\n\t".join(
                [f"{k}: {type(v)} {str(v).strip()}" for k, v in latency.items()]
            )
        )
    memory_to_size = {}
    component_to_non_power_gated_porp = {}
    usage_df = {}

    non_power_gated_instances = 1
    for node in job.flattened_arch:
        if isinstance(node, arch.TensorHolder):
            if isinstance(node, arch.Memory):
                memory_to_size[node.name] = node.size

        # If there's no loops that use this spatial fanout, then the model won't output
        # any usage. We still want to reserve at least one spatial instance in this
        # case.
        used_fanout = reuse.fanout.get((node.name, job.einsum_name), {})
        for s in node.spatial:
            usage = used_fanout.get(s.name, 1) / s.fanout
            scaled_usage = usage * s.usage_scale
            usage_df[f"usage<SEP>spatial<SEP>{node.name}<SEP>{s.name}"] = scaled_usage
            non_power_gated_instances *= usage
        component_to_non_power_gated_porp[node.name] = non_power_gated_instances

    job.resource_capacities = {name:exact.capacity_bits(size) for name,size in memory_to_size.items()
                               if exact.enabled() and math.isfinite(size)}
    for name,size in job.resource_capacities.items():
        df[exact.capacity_column(name)] = size

    actions = gather_actions(reuse, None, use_name=True)
    energy = compute_energy_from_actions(
        spec, actions, overall_latency, component_to_non_power_gated_porp
    )
    if symbolic.PRINT_FORMULAS:
        for k, v in energy.items():
            print(f"{k}: {v}")

    fusable_tensors = workload.tensor_names_used_in_multiple_einsums
    tensor_to_backing = {}
    for node in pmapping.nodes:
        if isinstance(node, TensorHolder):
            for tensor in node.tensors:
                if tensor not in tensor_to_backing and tensor in fusable_tensors:
                    tensor_to_backing[tensor] = node.component

    total_occupancy = {}
    compute_unit = pmapping.nodes[-1].component

    n_instances = workload.n_instances * workload.einsums[job.einsum_name].n_instances

    for buffet, stats in reuse.buffet_stats.items():
        if buffet.level == compute_unit:
            continue

        occupancy = stats.max_occupancy

        if occupancy == 0:
            continue
        if stats.persistent:
            occupancy *= n_instances

        for tensor, backing in tensor_to_backing.items():
            if (is_copy_op or buffet.tensor == tensor) and buffet.level == backing:
                df[tensor2col(tensor)] = (occupancy if buffet.level in job.resource_capacities
                                        else occupancy / memory_to_size[buffet.level])

        total_occupancy.setdefault(buffet.level, {}).setdefault(stats.n_loops_above, 0)
        total_occupancy[buffet.level][stats.n_loops_above] += occupancy

    for memory, occupancies in total_occupancy.items():
        if memory not in job.memories_track_all:
            continue
        running_total = 0
        # Reservations are prefixes of lifetime depth, including persistent data
        # at depth -1. Set iteration can visit inner depths first and undercount
        # the innermost reservation used for capacity checks.
        for n_loop in sorted(occupancies):
            running_total += occupancies[n_loop]
            df[nameloop2col(memory, n_loop)] = (
                running_total if memory in job.resource_capacities else running_total / memory_to_size[memory]
            )

    if metrics & Metrics.ACTIONS:
        detailed_actions = gather_actions(reuse, None, verbose=True, use_name=True)
        for key, count in detailed_actions.items():
            df[action2col(key)] = count.total * n_instances
        detailed_energy = compute_energy_from_actions(
            spec, detailed_actions, overall_latency, component_to_non_power_gated_porp
        )
        for key, energy_val in detailed_energy.items():
            df[energy2col(key)] = energy_val * n_instances
        for component, cur_latency in latency.items():
            df[f"latency<SEP>{component}"] = cur_latency * n_instances

    if metrics & Metrics.LATENCY:
        df["Total<SEP>latency"] = overall_latency * n_instances
        # One objective per latency scenario (research switch AF_LATENCY_SCALES). A
        # component's action latencies are scaled before re-evaluating its formula;
        # total_latency may contain fixed overheads and need not scale linearly.
        # The Einsum latency is the max over components. Columns are summed across
        # Einsums in the join like Total<SEP>latency, so the best mapping of every scenario
        # stays on the Pareto front. Energy must not depend on latency (checked in
        # make_pmappings: no leak power).
        for component, factor in job.latency_scales:
            scaled = component_latency(
                reuse, job.flattened_arch, pmapping, spec,
                action_latency_scales={component: factor},
            )
            df[scaled_latency2col(component, factor)] = (
                _maximum_latency(tuple(scaled.values())) * n_instances
            )
        # df[f"latency<SEP>compute"] = comp_latency * n_instances
        # For first latency, we'll follow the convention of treating compute
        # as a component, similarly to memory (see below).
        for compute_level, stats in reuse.compute_stats.items():  # FIRST LATENCY
            for idx, max_first_latency in stats.max_first_latency.items():
                df[firstlatency2col(compute_level.level, idx)] = (
                    max_first_latency * n_instances
                )

    if metrics & Metrics.ENERGY:
        df["Total<SEP>energy"] = sum(energy.values()) * n_instances

    per_memory_usage_df = {}
    for memory, occupancies in total_occupancy.items():
        if job.ignored_resources is not None and memory not in job.ignored_resources:
            key = f"usage<SEP>memory<SEP>{memory}"
            per_memory_usage_df[key] = (
                sum(occupancies.values()) if memory in job.resource_capacities
                else sum(occupancies.values()) / memory_to_size[memory]
            )

    return (
        reuse.symbols,
        df,
        per_memory_usage_df,
        usage_df,
        reuse.tensor2mapping,
    )
