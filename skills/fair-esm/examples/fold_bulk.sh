#!/usr/bin/env bash
# Fold every sequence in a FASTA with ESMFold.
#
# Sequences are sorted by length and batched together; shorter sequences
# fold in groups to maximize GPU utilization. Each output PDB has pLDDT
# in the B-factor column.

set -euo pipefail

FASTA="${1:-seqs.fa}"
OUT_DIR="${2:-pdbs}"

mkdir -p "${OUT_DIR}"

esm-fold \
    -i "${FASTA}" -o "${OUT_DIR}" \
    --num-recycles 4 \
    --max-tokens-per-batch 1024

# For long sequences or small GPUs:
#   --chunk-size 64               # axial-attention chunking
#   --cpu-offload                 # FSDP offload of the 3B ESM-2 LM to CPU
# CPU-only fallback (slow):
#   --cpu-only
