"""Measure safe capacity cuts on real native terminal continuation branches."""

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import functools
import inspect
import json
from pathlib import Path
from unittest.mock import patch

from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.mapper.FFM._pareto_df import exact_resources as exact
from accelforge.mapper.FFM._pareto_df.capacity_membership import membership_for_target
from accelforge.mapper.FFM._pareto_df.df_convention import nameloop2col
from accelforge.mapper.FFM.generation_contract import effective_pareto_tolerance
from research.fusion_envelope.search import problem
from research.graph_coopt.resource_effect import compile_effects, evaluate, UnsupportedEffect
from research.joint_physical.demand import search
from research.joint_physical.generator import PhysicalDomain


class CapacityAudit:
    def __init__(self, domain, max_prefix_rows=512):
        self.domain = PhysicalDomain(domain.points)
        self.max_prefix_rows = max_prefix_rows
        self.counts = Counter()
        self.unknown = Counter()
        self.witnesses = []

    def inspect(self, left, right, plan):
        nleft, nright = len(left.data), len(right.data)
        self.counts["terminal_branches"] += 1
        self.counts["terminal_prefix_row_instances"] += nleft
        if not nleft or not nright or plan["make_empty_result"]:
            return
        if nleft > self.max_prefix_rows:
            self.unknown["prefix_row_budget"] += 1
            return
        try:
            exact.check_units([left.data, right.data])
            exact.validate_reservations(left.data)
            exact.validate_reservations(right.data)
            variables, profiles = compile_effects(left, right, plan)
        except (UnsupportedEffect, exact.ExactResourceError) as error:
            self.unknown[str(error)] += 1
            return
        target = nameloop2col("GlobalBuffer", 0)
        self.counts["compiled_branches"] += 1
        self.counts["compiled_prefix_row_instances"] += nleft
        keys = []
        for frame, columns in ((left.data, plan["left_match"]), (right.data, plan["right_match"])):
            if any(not isinstance(c,str) or c not in frame for c in columns):
                self.unknown["noncolumn_join_key"] += 1
                return
            if columns and frame[columns].isna().any(axis=None):
                self.unknown["null_join_key"] += 1
                return
            keys.append(list(frame[columns].itertuples(index=False, name=None)) if columns else [()] * len(frame))
        for label, point in zip(self.domain.labels,self.domain.points):
            lmask = membership_for_target(left.data,"JointArchitectureDomain",label)
            rmask = membership_for_target(right.data,"JointArchitectureDomain",label)
            positions = defaultdict(list)
            for j, (live, key) in enumerate(zip(rmask,keys[1])):
                if live:
                    positions[key].append(j)
            # Each right coordinate is nonnegative. The max-plus response
            # has nonnegative coefficients, so evaluating it at independent
            # minima over the actual key group gives a safe lower bound.
            bounds = {key:tuple(int(v) for v in right.data.iloc[rows][list(variables)].min())
                      for key,rows in positions.items()}
            for row, (live, key, profile) in enumerate(zip(lmask,keys[0],profiles)):
                if not live:
                    continue
                self.counts["tested_prefix_hardware_instances"] += 1
                if key not in positions:
                    self.counts["equality_no_match"] += 1
                    continue
                if target not in profile:
                    continue
                minima = bounds[key]
                terms = profile[target]
                minimum_bits = evaluate(terms,minima)
                self.counts["tested_global_buffer_instances"] += 1
                if minimum_bits <= point.capacity_bytes*8:
                    continue
                self.counts["additional_capacity_no_match"] += 1
                self.counts["excluded_matching_pair_hardware_instances"] += len(positions[key])
                if len(self.witnesses) < 16:
                    self.witnesses.append(dict(prefix_row=row, capacity_bytes=point.capacity_bytes,
                        shape=[point.px,point.py], lower_bits=minimum_bits, right_columns=variables,
                        key=tuple(float(v) for v in key), column_minima=minima, max_plus_terms=terms))

    @contextmanager
    def observe(self):
        original = PmappingDataframe.merge_next
        signature = inspect.signature(original)

        @functools.wraps(original)
        def wrapped(left, right, *args, **kwargs):
            bound = signature.bind(left, right, *args, **kwargs)
            bound.apply_defaults()
            values = bound.arguments
            if values["next_shared_loop_index"] != -1:
                return original(left, right, *args, **kwargs)
            if (values["_pmapping_row_filter_function"] is not None or values["_prepared_join_plan"] is not None
                or values["duplicated_aliased_tensors"] or values["drop_valid_reservations"]
                or "GlobalBuffer" in values["ignored_resources"] or effective_pareto_tolerance() != 0):
                self.unknown["unsupported_native_transfer_scope"] += 1
                return original(left, right, *args, **kwargs)
            observed_left, observed_right = left.copy(), right.copy()
            plan = observed_left._prepare_join_plan(observed_right, values["shared_loop_index"], values["live_tensors"],
                values["still_live_reservations"], values["compatibility_left"], values["compatibility_right"],
                values["compatibility_joined"])
            self.inspect(observed_left, observed_right, plan)
            return original(left, right, *args, **kwargs)

        with patch.object(PmappingDataframe, "merge_next", wrapped):
            yield self


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", choices=("attention", "attention256", "attention512"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    case, domain, _ = problem(args.workload, "original12")
    audit = CapacityAudit(domain)
    with audit.observe():
        _, details = search(case, domain)
    result = dict(status="complete", workload=args.workload, points=len(domain.points),
                  mode="observation only; no native candidates removed",
                  counts=dict(audit.counts), unknown=dict(audit.unknown),
                  example_cut_witnesses=audit.witnesses, search_details=details)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(counts=result["counts"], unknown=result["unknown"])), flush=True)


if __name__ == "__main__":
    main()
