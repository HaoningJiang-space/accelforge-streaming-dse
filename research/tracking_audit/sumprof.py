import json, sys
for f in sys.argv[1:]:
    d = json.load(open(f))
    ev = d["events"]
    m = [e for e in ev if e["ev"] == "pd_merge"]
    p = [e for e in ev if e["ev"] == "fast_pareto"]
    print(f, json.dumps(d["summary"]))
    if m:
        print(" merges", len(m), "rows_materialized", sum(e["n_out"] for e in m), "max", max(e["n_out"] for e in m),
              "max_mb", round(max(e["mem_mb"] for e in m), 1))
    if p:
        print(" pareto calls", len(p), "rows_in", sum(e["n_in"] for e in p), "rows_out", sum(e["n_out"] for e in p),
              "max_in", max(e["n_in"] for e in p), "dims", sorted({(e["n_min"], e["n_diff"]) for e in p}))
