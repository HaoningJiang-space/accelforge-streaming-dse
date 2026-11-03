#!/bin/bash
# How does the speedup of shared search grow with the number of capacities K?
#
#   sweep_capacity_count.sh OUT_DIR REPEATS "K1 K2 ..." CASE [CASE ...]
#   CASE = name:workload:arch:params:log2_min:log2_max
#
# For each case and K, runs capacity_audit.py (indep,var,push, 8 workers) on K
# GlobalBuffer capacities spaced evenly in log2 between 2^log2_min and 2^log2_max MiB.
# With K-1 dividing a common multiple (e.g. K in 2 4 6 16 over a span of 5), the
# smaller sets are subsets of the larger ones. Each run is capped by run_capped.sh;
# logs go to OUT_DIR/<name>_K<k>.log and exit codes to OUT_DIR/status.
set -u
OUT=$1; REPEATS=$2; KS=$3; shift 3
A=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
for spec in "$@"; do
  IFS=: read -r name workload arch params lo hi <<< "$spec"
  for k in $KS; do
    caps=$(python3 -c "import sys; lo, hi, k = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3]); \
print(','.join(repr(2 ** (lo + (hi - lo) * i / (k - 1))) for i in range(k)))" "$lo" "$hi" "$k")
    "$A/run_capped.sh" 24 7200 "$OUT/${name}_K$k.log" -- python "$A/capacity_audit.py" "$params" "$caps" \
      indep,var,push --workload "$workload" --arch "$arch" --jobs 8 --repeats "$REPEATS"
    echo "${name}_K$k rc=$?" >> "$OUT/status"
  done
done
echo ALLDONE >> "$OUT/status"
