"""Plot fixed-shortlist misses and worst regret from a banked-scale report."""

import argparse
from collections import defaultdict
import gzip
from io import StringIO
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


METHODS = {
    "all/top1": ("Top 1", "o", "#3274a1"),
    "all/top2": ("Top 2", "s", "#e07a24"),
    "all/within10": ("Within 10%", "^", "#36826c"),
    "all/critical_top2": ("Critical-path top 2", "D", "#75489d"),
}


def plot(report, output):
    plt.rcParams.update({"svg.fonttype": "none", "svg.hashsalt": "banked-scale"})
    groups = defaultdict(list)
    for case in report["cases"].values():
        for cell in case["cells"]:
            groups[cell["size"]].append(cell["shortlists"])
    sizes = sorted(groups)
    labels = [f"{size:,}\n({len(groups[size])} cells)" for size in sizes]
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 3.6), layout="constrained")
    for key, (label, marker, color) in METHODS.items():
        trials = [[cell[key] for cell in groups[size]] for size in sizes]
        misses = [sum(trial["miss"] for trial in group) / len(group) for group in trials]
        regret = [max(trial["regret"] for trial in group) for group in trials]
        for axis, values in zip(axes, (misses, regret), strict=True):
            axis.plot(sizes, values, marker=marker, color=color, label=label, linewidth=1.5, markersize=5)
    for axis, title in zip(axes, ("Fraction of cells missing the optimum", "Maximum relative EDP regret"), strict=True):
        axis.set_xscale("log")
        axis.set_xticks(sizes, labels)
        axis.set_xlabel("Area-admitted architecture points")
        axis.set_title(title, loc="left", fontsize=11)
        axis.set_ylim(bottom=-0.025)
        axis.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        axis.grid(axis="y", alpha=0.3)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylim(top=1.05)
    axes[1].legend(loc="upper right", frameon=False, fontsize=8)
    svg = StringIO()
    figure.savefig(svg, format="svg", metadata={"Date": None})
    output.write_text("\n".join(line.rstrip() for line in svg.getvalue().splitlines()) + "\n",
                      encoding="utf-8", newline="\n")
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with gzip.open(args.report, "rt", encoding="utf-8") as stream:
        plot(json.load(stream), args.output)


if __name__ == "__main__":
    main()
