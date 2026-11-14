#!/bin/bash
# Usage: run.sh NEURA_ROOT KERNEL_DIR OUT_DIR [ARCH_YAML]
# Lowers each kernel C file through the Neura e2e pipeline and records the mapping II.
set -u
R=$1; KDIR=$2; OUT=$3
BIN=$R/llvm-project/build/bin; NOPT=$R/neura/build/tools/mlir-neura-opt/mlir-neura-opt
ARCH=${4:-$R/neura/test/arch_spec/architecture.yaml}
[ -x "$NOPT" ] || NOPT=$(find $R/neura/build -name mlir-neura-opt -type f | head -1)
mkdir -p "$OUT"
for src in "$KDIR"/*.c; do
  name=$(basename "$src" .c); d="$OUT/$name"; mkdir -p "$d"; cd "$d"
  "$BIN/clang" -S -emit-llvm -O3 -fno-vectorize -fno-unroll-loops -std=c11 -o full.ll "$src"
  "$BIN/llvm-extract" --func=kernel full.ll -S -o kernel.ll
  "$BIN/mlir-translate" --import-llvm kernel.ll -o kernel.mlir
  timeout 1800 "$NOPT" kernel.mlir --assign-accelerator --lower-llvm-to-neura \
    --promote-input-arg-to-const --fold-constant --canonicalize-return --canonicalize-live-in \
    --leverage-predicated-value --transform-ctrl-to-data-flow --fold-constant --insert-data-mov \
    --map-to-accelerator="mapping-strategy=heuristic" --architecture-spec="$ARCH" \
    -o mapped.mlir > map.log 2>&1
  rc=$?
  info=$(grep -oE 'mapping_info = \{[^}]*\}' mapped.mlir 2>/dev/null | head -1)
  get() { echo "$info" | grep -oE "$1 = [0-9]+" | grep -oE '[0-9]+$'; }
  ops=$(grep -cE '= "?neura\.' mapped.mlir 2>/dev/null)
  movs=$(grep -c 'neura.data_mov' mapped.mlir 2>/dev/null)
  mem=$(grep -cE 'neura\.(load|store)' mapped.mlir 2>/dev/null)
  echo "$name rc=$rc II=$(get compiled_ii) ResMII=$(get res_mii) RecMII=$(get rec_mii) ops=$ops data_mov=$movs mem=$mem" | tee -a "$OUT/summary.txt"
done
