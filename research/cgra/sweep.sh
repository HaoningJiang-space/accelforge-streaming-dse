#!/bin/bash
# Usage: sweep.sh LLVM_BIN MAPPER_SO KERNEL_DIR OUT_DIR
# One run per (kernel, unroll, array size). Each run gets its own directory with param.json.
set -u
BIN=$1; SO=$2; KDIR=$3; OUT=$4
mkdir -p "$OUT"
for src in "$KDIR"/*.c; do
  name=$(basename "$src" .c)
  for u in 1 2 4; do
    for dim in 4 8; do
      d="$OUT/${name}_u${u}_${dim}x${dim}"; mkdir -p "$d"; cd "$d"
      # -fno-unroll-loops marks loops unroll.disable; strip that so opt can apply the requested factor.
      "$BIN/clang" -O2 -fno-unroll-loops -fno-vectorize -fno-slp-vectorize -emit-llvm -S -c "$src" -o raw.ll
      sed 's/!"llvm.loop.unroll.disable"/!"llvm.loop.mustprogress"/' raw.ll | "$BIN/llvm-as" -o base.bc
      if [ "$u" -gt 1 ]; then
        "$BIN/opt" -loop-unroll -unroll-count=$u -unroll-allow-partial base.bc -o kernel.bc
      else
        cp base.bc kernel.bc
      fi
      "$BIN/llvm-dis" kernel.bc -o kernel.ll
      mem=$(seq -s, 0 $((dim - 1)))
      all=$(seq -s, 0 $((dim * dim - 1)))
      cat > param.json <<JSON
{
  "kernel": "kernel", "targetFunction": false, "targetNested": false, "targetLoopsID": [0],
  "doCGRAMapping": true, "row": $dim, "column": $dim, "precisionAware": false,
  "fusionStrategy": [], "isTrimmedDemo": true, "heuristicMapping": true,
  "parameterizableCGRA": false, "vectorizationMode": "all", "bypassConstraint": 4,
  "isStaticElasticCGRA": false, "ctrlMemConstraint": 64, "regConstraint": 8,
  "supportDVFS": false, "expandableMapping": false, "DVFSAwareMapping": false,
  "enablePowerGating": false, "optLatency": {}, "optPipelined": [], "fusionPattern": {},
  "additionalFunc": {"load": [$mem], "store": [$mem], "complex-Ctrl": [$all]}
}
JSON
      timeout 600 "$BIN/opt" -load "$SO" -mapperPass -disable-output kernel.bc > map.log 2>&1
      rc=$?
      field() { grep -aoE "$1" map.log | grep -oE '[0-9]+$' | tail -1; }
      echo "$name u=$u dim=$dim rc=$rc ResMII=$(field '\[ResMII: [0-9]+') RecMII=$(field '\[RecMII: [0-9]+') II=$(field 'Mapping II: [0-9]+') nodes=$(field 'DFG node count: [0-9]+') load=$(field '^load : [0-9]+') store=$(field '^store : [0-9]+') ok=$(grep -ac '^\[Mapping Success\]' map.log)" | tee -a "$OUT/summary.txt"
    done
  done
done
