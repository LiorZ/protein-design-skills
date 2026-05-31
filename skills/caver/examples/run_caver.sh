#!/usr/bin/env bash
# Convenience wrapper: forward args to the CAVER SIF with a sane heap.
#
# Usage:
#   ./run_caver.sh <pdb_dir> <config.txt> <out_dir> [-Xmx16g]
#
# Examples:
#   ./run_caver.sh ./md_snapshots ./config.txt ./out
#   ./run_caver.sh ./pdb ./config.txt ./out -Xmx32g

set -euo pipefail

if [[ $# -lt 3 ]]; then
    echo "Usage: $0 <pdb_dir> <config.txt> <out_dir> [-Xmx<size>]" >&2
    exit 2
fi

PDB_DIR="$1"
CONFIG="$2"
OUT="$3"
JAVA_OPTS="${4:--Xmx8g}"

: "${SINGULARITY_HOME:?must export SINGULARITY_HOME (dir containing CAVER.sif)}"
SIF="${SINGULARITY_HOME}/CAVER.sif"

[[ -f "$SIF"    ]] || { echo "Missing $SIF" >&2; exit 1; }
[[ -d "$PDB_DIR" ]] || { echo "Missing PDB dir $PDB_DIR" >&2; exit 1; }
[[ -f "$CONFIG"  ]] || { echo "Missing config $CONFIG" >&2; exit 1; }

mkdir -p "$OUT"

echo "[CAVER] SIF      = $SIF"
echo "[CAVER] pdb_dir  = $PDB_DIR"
echo "[CAVER] config   = $CONFIG"
echo "[CAVER] out      = $OUT"
echo "[CAVER] JAVA_OPTS= $JAVA_OPTS"

apptainer run --env JAVA_OPTS="$JAVA_OPTS" "$SIF" \
    -home /opt/caver \
    -pdb  "$PDB_DIR" \
    -conf "$CONFIG" \
    -out  "$OUT"

echo "[CAVER] done -> $OUT"
echo "        summary:  $OUT/summary.txt"
echo "        csv:      $OUT/summary_precise_numbers.csv"
echo "        pymol:    $OUT/pymol/*.pse"
echo "        warnings: $OUT/warnings.txt"
