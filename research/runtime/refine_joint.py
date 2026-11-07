"""Solve one geometry-ordered shape exactly; search every other shape jointly."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse
from research.fusion_envelope.search import PolicyOracle, problem
from research.joint_budget.analytic_bounds import lower_bound
from research.joint_budget.protocol import Domain
from research.joint_physical.demand import search
from research.joint_physical.replay import encode
from research.joint_physical.run import source_digest
from research.joint_search.validation import WorkCounter, frontier
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import validate_pick


def run(workload, output, reference, anchor_only):
    start = time.perf_counter()
    def fingerprint():
        return hashlib.sha256(source_digest().encode() + Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    source = fingerprint()
    case, domain, budgets = problem(workload, "factors96")
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    shape_seed = min(domain.points, key=lambda p: (lower_bound(case, p).latency,
                                                   max(p.px, p.py) / min(p.px, p.py), p))
    shape = (shape_seed.px, shape_seed.py)
    exact_points = tuple(p for p in domain.points if (p.px, p.py) == shape)
    rest = Domain(tuple(p for p in domain.points if p not in exact_points))

    def select(rows):
        result = []
        for budget in budgets:
            candidates = [(p, row) for p, row in rows.items() if row is not None and budget.admits(p)]
            point, row = min(candidates, key=lambda item: float(item[1]["Total<SEP>energy"])
                                                         * float(item[1][common.LATENCY]))
            witness = validate_pick(case, (point.px, point.py), point.capacity_bytes, row)
            if not witness["feasible"] or not witness["ok"]:
                raise ValueError("invalid budget incumbent")
            witness["mapping"] = encode(row["Total<SEP>mapping"]())
            result.append(dict(architecture=asdict(point), budget=asdict(budget), witness=witness,
                               elapsed_s=time.perf_counter() - start))
        return result

    oracle = PolicyOracle(case, "relaxed")
    with EnumerationReuse() as cache:
        oracle.solve(shape, exact_points, cache)
    outputs = dict(oracle.outputs)
    rows = {p: common.best_row(frame) for p, frame in outputs.items()}
    anchor_winners = select(rows)
    print(json.dumps(dict(stage="exact_anchor_complete", shape=shape, elapsed_s=time.perf_counter() - start,
                          edp=[r["witness"]["edp"] for r in anchor_winners])), flush=True)
    with WorkCounter() as counter:
        if not anchor_only:
            approximations, details = search(case, rest)
            outputs.update(approximations)
            rows.update({p: common.best_row(frame) for p, frame in approximations.items()})
        else:
            details = None
    final = select(rows)
    search_s = time.perf_counter() - start
    peak_rss = common.peak_rss_gb()
    points = []
    for point in domain.points:
        if point not in outputs:
            continue
        row = rows[point]
        entry = dict(architecture=asdict(point), vectors=frontier(outputs[point]).to_dict("records"),
                     point_status="no_candidate" if row is None else "feasible",
                     origin="exact Event" if point in exact_points else "joint demand")
        if row is not None:
            witness = validate_pick(case, (point.px, point.py), point.capacity_bytes, row, capture_actions=True)
            if not witness["ok"] or not witness["feasible"]:
                raise ValueError("invalid per-point mapping")
            witness["mapping"] = encode(row["Total<SEP>mapping"]())
            entry["witness"] = witness
        points.append(entry)
    after = fingerprint()
    if source != after:
        raise ValueError("search source changed during the run")
    joint_work = dict(counter.counts)
    if details is not None:
        joint_work["model_rows"] = details["proposer"]["materialized_rows"]
        joint_work["model_templates"] = details["proposer"]["symbolic_models"]
    report = dict(status="complete", case=dict(workload=case.workload, arch=case.arch, params=list(case.params)),
                  domain=[asdict(p) for p in domain.points if p in outputs],
                  requested_full_domain=[asdict(p) for p in domain.points], workers=1, policy="relaxed",
                  method="exact anchor only control" if anchor_only else "exact anchor + joint physical generation",
                  source_before=source, source_after=after, reference_read_before_search=False,
                  search_s=search_s, peak_rss_gib_before_validation=peak_rss, points=points,
                  budget_selections=final, seed_budget_selections=anchor_winners, details=details,
                  anchor_only=anchor_only, exact_hardware_points=[asdict(p) for p in exact_points],
                  exact_oracle_details=oracle.details, joint_work=joint_work,
                  all_selected_physical_sources_valid=all(p["point_status"]=="feasible" for p in points),
                  physical_mapspace_optimality=False, external_sota_acceptance=False)
    if reference is not None:
        data = reference.read_bytes()
        baseline = json.loads(data)
        if (baseline["status"]!="complete" or baseline["case"]!=report["case"] or
            baseline["domain"]!=report["requested_full_domain"] or baseline["policy"]!=report["policy"]):
            raise ValueError("reference case/domain/policy differs")
        targets = [w["witness"]["edp"] for w in baseline["budget_selections"]]
        report["post_search_reference_sha256"] = hashlib.sha256(data).hexdigest()
        report["relative_edp_by_budget"] = [w["witness"]["edp"] / t for w, t in zip(final, targets, strict=True)]
        report["seed_relative_edp_by_budget"] = [w["witness"]["edp"] / t
                                                 for w, t in zip(anchor_winners, targets, strict=True)]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: report[k] for k in ("status", "search_s", "relative_edp_by_budget",
                                            "seed_relative_edp_by_budget") if k in report}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", choices=("attention", "attention256", "attention512"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--anchor-only", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    run(args.workload, args.output, args.reference, args.anchor_only)


if __name__ == "__main__":
    main()
