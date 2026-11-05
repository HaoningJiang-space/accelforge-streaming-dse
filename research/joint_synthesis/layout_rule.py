"""Restricted free-SRAM-layout replacement; no general trait substitutability."""
from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutWitness:
    original_prefix: object
    replacement_prefix: object
    consumer: object
    removed_enforcers: tuple


def matching_sram_prefix(prefix,consumer,available_prefixes):
    """Find an actual admissible retained identity replacement, or keep the pair.

    Both endpoints must be SRAM. The target interface must actually exist in
    the request domain; an externally fixed producer layout cannot be changed.
    The current cost model has no layout-sensitive SRAM behavior. Its free-layout
    theorem ensures such a prefix exists; the numerical check also certifies
    the concrete retained witness after local pruning.
    """
    source,target=prefix.plan.delivered,consumer.plan.required
    if source.location!=target.location or source.location!='sram' or source==target:
        return None
    return next((p for p in available_prefixes.get(target,())
        if p.plan.op==prefix.plan.op and p.plan.required==prefix.plan.required
        and all(a<=b for a,b in zip(p.vector,prefix.vector))),None)
