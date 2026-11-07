"""Summarize independently replayed native Event and demand-search trials."""

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def stats(values):
    return dict(median=median(values), min=min(values), max=max(values))


def checkout_hashes(raw):
    # The historical Windows runner hashed CRLF bytes; Git normalizes text to
    # LF in blobs. Accept only those two newline encodings of the exact bytes.
    lf = raw.replace(b"\r\n", b"\n")
    return {hashlib.sha256(value).hexdigest() for value in (raw, lf, lf.replace(b"\n", b"\r\n"))}


def load_trial(directory, method, trial):
    stem = directory / f"{method}_r{trial}"
    raw = stem.with_suffix(".json").read_bytes()
    report = json.loads(raw)
    check = json.loads(stem.with_name(stem.name + "_check.json").with_suffix(".json").read_bytes())
    require(report["status"] == "complete" and check["status"] == "verified", f"{stem}: incomplete trial")
    require(check["report_sha256"] in checkout_hashes(raw), f"{stem}: replay hash mismatch")
    require(report["source_before"] == report["source_after"], f"{stem}: code changed during search")
    require(report["workers"] == 1 and not report["reference_read_before_search"], f"{stem}: protocol mismatch")
    domain = {tuple(sorted(point.items())) for point in report["domain"]}
    actual = [tuple(sorted(point["architecture"].items())) for point in report["points"]]
    require(len(actual) == len(domain) and set(actual) == domain, f"{stem}: missing or duplicate architectures")
    if method == "demand":
        require(all(point.get("witness", {}).get("feasible") and point["witness"]["ok"] for point in report["points"]),
                f"{stem}: a proposed point has no valid witness")
        require(check["serialized_physical_witnesses"] == len(domain) + len(report["budget_selections"])
                + sum(bool(s) for s in report["seed_budget_selections"]), f"{stem}: incomplete physical replay")
    return report, check


def reached(value, target):
    return value <= target or math.isclose(value, target, rel_tol=1e-12, abs_tol=0)


def anytime(report, check, method, targets):
    times = []
    for index, target in enumerate(targets):
        possible = []
        if reached(check["canonical_edp"][index], target):
            possible.append(report["search_s"])
        if method == "events":
            possible.extend(entry["elapsed_s"] for entry in report["trajectory"]
                            if index in entry["budget_indices"] and entry["witness"]["feasible"]
                            and reached(entry["witness"]["edp"], target))
        else:
            seed = check["seed_canonical_edp"][index]
            if seed is not None and reached(seed, target):
                possible.append(report["seed_budget_selections"][index]["elapsed_s"])
        times.append(min(possible, default=None))
    return times


def summarize(directory, repetitions):
    reference, proof = load_trial(directory, "events", 1)
    budgets = [point["budget"] for point in reference["budget_selections"]]
    targets = proof["canonical_edp"]
    table = {}
    for method in ("events", "demand"):
        trials = []
        source = None
        for index in range(1, repetitions + 1):
            report, check = load_trial(directory, method, index)
            require(all(report[key] == reference[key] for key in ("case", "domain", "policy")),
                    f"{method}/{index}: different physical experiment")
            require([point["budget"] for point in report["budget_selections"]] == budgets,
                    f"{method}/{index}: different budget order")
            require(len(check["canonical_edp"]) == len(targets), f"{method}/{index}: incomplete quality record")
            require(all(reached(value, target) for value, target in zip(check["canonical_edp"], targets)),
                    f"{method}/{index}: replayed quality regressed")
            if method == "demand":
                require(report["reference_sha256"] == proof["report_sha256"],
                        f"{method}/{index}: different post-search reference")
            source = source or report["source_before"]
            require(report["source_before"] == source, f"{method}/{index}: different source digest")
            work = report["work"] if method == "demand" else {
                key: sum(group["work"][key] for group in report["oracle_details"])
                for key in ("model_rows", "join_pair_rows")}
            times = anytime(report, check, method, targets)
            trials.append(dict(
                round=index, search_s=report["search_s"], target_per_budget_s=times,
                all_targets_s=max(times) if None not in times else None,
                canonical_edp=check["canonical_edp"],
                physical_witnesses=check["serialized_physical_witnesses"],
                peak_gib=report["peak_rss_gib_before_validation"]["main"],
                model_rows=work["model_rows"], join_pair_rows=work["join_pair_rows"],
                replay_s=check.get("replay_s")))
        columns = ("search_s", "all_targets_s", "peak_gib", "model_rows", "join_pair_rows", "replay_s")
        table[method] = dict(source=source, trials=trials, summary={
            key: stats([trial[key] for trial in trials]) for key in columns
            if all(trial[key] is not None for trial in trials)})
    ratios = {key: table["events"]["summary"][key]["median"] / value["median"]
              for key, value in table["demand"]["summary"].items()
              if key in table["events"]["summary"]}
    return dict(case=reference["case"], policy=reference["policy"], domain_points=len(reference["domain"]),
                budgets=budgets, reference_canonical_edp=targets, repetitions=repetitions,
                methods=table, event_over_demand_median=ratios,
                external_sota_acceptance=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summarize(args.directory, args.repetitions)
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
