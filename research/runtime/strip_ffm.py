"""Use the native FFM Pareto join for compatible materialized strip segments."""

import pandas as pd

from accelforge.mapper.FFM._join_pmappings.compatibility import Compatibility
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.util import fzs


MATERIALIZED = Compatibility(fzs())
E, T = "Total<SEP>energy", "Total<SEP>latency"


def join(left, right):
    if not left or not right:
        return []

    def frame(entries, key):
        rows = [{E: e, T: t, key: i} for i, ((e, t), _) in enumerate(entries)]
        return PmappingDataframe(pd.DataFrame(rows), len(rows), len(rows), skip_pareto=True)

    # Both sides are already legal to run on the same physical hardware.
    # The strip cut has drained to DRAM; there is no live SRAM to merge.
    merged = frame(left, "prefix_id").merge_next(
        frame(right, "segment_id"), shared_loop_index=0, next_shared_loop_index=0,
        live_tensors=set(), still_live_reservations=set(), duplicated_aliased_tensors=set(),
        compatibility_left=MATERIALIZED, compatibility_right=MATERIALIZED,
        compatibility_joined=MATERIALIZED, ignored_resources=set(),
    )
    columns = [E, T, "prefix_id", "segment_id"]
    return [((int(e), int(t)), left[i][1] + (right[j][1],))
            for e, t, i, j in merged.data[columns].itertuples(index=False, name=None)]
