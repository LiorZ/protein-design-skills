#!/usr/bin/env bash
# Bulk embedding extraction from a FASTA file using the `esm-extract` CLI.
#
# Output: one `<header>.pt` per FASTA record in OUT_DIR. Each .pt is a dict
# with keys label / mean_representations / representations / contacts
# depending on --include.

set -euo pipefail

MODEL="${MODEL:-esm2_t33_650M_UR50D}"      # standard 650M default
FASTA="${1:-seqs.fa}"
OUT_DIR="${2:-embeddings}"
LAYER="${LAYER:-33}"                       # final layer of 650M model

mkdir -p "${OUT_DIR}"

esm-extract \
    "${MODEL}" "${FASTA}" "${OUT_DIR}" \
    --repr_layers "${LAYER}" \
    --include mean per_tok \
    --toks_per_batch 4096 \
    --truncation_seq_length 1022

# To also include contact predictions (requires regression weights, which
# auto-download for ESM-2 but not ESM-1v / ESM-IF):
#   --include mean per_tok contacts
#
# To force CPU (e.g. for tiny smoke tests):
#   --nogpu
