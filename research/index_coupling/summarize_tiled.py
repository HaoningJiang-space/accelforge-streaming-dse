"""Summarize saved eex005 ablations; optionally render a publication-style plot."""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics

MODES = ("strips", "tiles_no_retention", "tiles_dual_retention", "tiles_scoped_retention")


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def summarize(root):
    rows = read(root / "sweep.jsonl") + read(root / "dual_sweep.jsonl")
    report = {"sources": sorted({r["commit"] for r in rows if r["kind"] == "metadata"}), "ablations": []}
    for grid in (False, True):
        for mode in MODES:
            group = [r for r in rows if r["kind"] == "ablation" and r["all_tiles"] == grid and r["mode"] == mode]
            assert len(group) == 512
            coverage, union = Counter(), Counter()
            for r in group:
                coverage.update(r["coverage"])
                union.update(r["union_coverage"])
            middle = [r["targets"][0] for r in group if r["shape"][0] == r["shape"][2]]
            report["ablations"].append(dict(all_tiles=grid, mode=mode, instances=len(group),
                coverage=dict(coverage), union_coverage=dict(union),
                midpoint_exact=sum(r["capacity"] == r["reference_capacity"] for r in middle),
                midpoint_better=sum(r["capacity"] < r["reference_capacity"] for r in middle),
                midpoint_total=len(middle), median_build_ms=statistics.median(r["seconds"]*1000 for r in group),
                total_build_seconds=sum(r["seconds"] for r in group),
                candidates_min=min(r["candidates"] for r in group), candidates_max=max(r["candidates"] for r in group)))
    benchmarks = [r for r in read(root / "benchmark.jsonl") if r["kind"] == "benchmark"]
    assert len(benchmarks) == 12
    totals = {m: sum(r["medians"][m] for r in benchmarks) for m in MODES}
    report["paired_timing"] = dict(cases=len(benchmarks), repetitions=12, sum_medians_seconds=totals,
        reduced_saving_fraction=1-totals["tiles_dual_retention"]/totals["tiles_scoped_retention"])
    audit = read(root / "audit.jsonl")
    size = next(r for r in audit if r["kind"] == "audit_size")
    executed = [r for r in audit if r["kind"] == "execution"]
    assert len(executed) == size["plans"] and all(r["execution"]["valid"] for r in executed)
    report["execution_audit"] = dict(size, completed=len(executed), macs=sum(r["execution"]["steps"] for r in executed))
    # Equal tile grids, compare the reduced family with the full mask family.
    differences = []
    for grid in (False, True):
        keyed = {(tuple(r["shape"]), r["cross"], r["mode"]): r for r in rows
                 if r["kind"] == "ablation" and r["all_tiles"] == grid}
        counts, worst = Counter(), 0
        for shape, cross, mode in list(keyed):
            if mode != "tiles_scoped_retention":
                continue
            full = keyed[(shape, cross, mode)]["frontier"]
            reduced = keyed[(shape, cross, "tiles_dual_retention")]["frontier"]
            for cap in {p[0] for p in full+reduced}:
                f = min(q for c, q in full if c <= cap)
                d = min(q for c, q in reduced if c <= cap)
                assert d >= f
                counts["equal" if d == f else "worse"] += 1
                worst = max(worst, d/f-1)
        differences.append(dict(all_tiles=grid, counts=dict(counts), worst_relative_traffic_excess=worst))
    report["reduced_vs_full"] = differences
    return report


def plot(report, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = ["Strips", "2D, no retention", "2D + two residence sets", "2D, all retention masks"]
    colors = ["#707b88", "#4698bb", "#158b79", "#4056a1"]
    data = [r for r in report["ablations"] if not r["all_tiles"]]
    exact = [r["coverage"].get("equal", 0) for r in data]
    times = [report["paired_timing"]["sum_medians_seconds"][m]*1000 for m in MODES]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.1), layout="constrained")
    for ax, values, title in zip(axes, (exact, times),
            ("Exact traffic matches / 6471 archived knots", "Paired construction time across 12 cases (ms)")):
        ax.barh(labels, values, color=colors)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=11)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xlim(0, max(values)*1.20)
        for i, value in enumerate(values):
            ax.text(value + max(values)*.02, i, f"{value:.0f}" if ax is axes[0] else f"{value:.2f}", va="center", fontsize=10)
    axes[0].set_xlabel("Matches; more is better")
    axes[1].set_xlabel("Sum of within-case medians; less is better")
    fig.suptitle("Fork construction: power-of-two tiles, same execution model", fontsize=13)
    fig.savefig(output.with_suffix(".png"), dpi=200)
    fig.savefig(output.with_suffix(".svg"))
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--plot", action="store_true")
    args = parser.parse_args()
    report = summarize(args.root)
    (args.root / "summary.json").write_text(json.dumps(report, indent=2)+"\n")
    if args.plot:
        plot(report, args.root / "ablation")
    print(json.dumps(report, indent=2))
