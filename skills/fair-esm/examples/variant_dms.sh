#!/usr/bin/env bash
# Score a deep mutational scan with the ESM-1v 5-model ensemble.
#
# Inputs:
#   - DMS_CSV: CSV with one row per variant; mutation column formatted as
#     'A24P' (or 'A24P:G30L' for multi-mutations).
#   - WT_SEQ:  wild-type sequence as a single uppercase string.
#   - OFFSET:  1-based residue number that maps to position 0 of WT_SEQ.
#
# Output: <DMS_CSV>_labeled.csv with one extra column per model + ensemble.

set -euo pipefail

DMS_CSV="${DMS_CSV:?Set DMS_CSV=path/to/dms.csv}"
WT_SEQ="${WT_SEQ:?Set WT_SEQ to the wild-type amino-acid sequence}"
OFFSET="${OFFSET:-1}"
MUT_COL="${MUT_COL:-mutant}"
STRATEGY="${STRATEGY:-masked-marginals}"   # wt-marginals | masked-marginals | pseudo-ppl
OUT_CSV="${OUT_CSV:-${DMS_CSV%.csv}_labeled.csv}"

# Path to the upstream esm repo:
REPO="${REPO:-$HOME/Repos/esm_org}"
PREDICT="${REPO}/examples/variant-prediction/predict.py"

python "${PREDICT}" \
    --model-location \
        esm1v_t33_650M_UR90S_1 esm1v_t33_650M_UR90S_2 \
        esm1v_t33_650M_UR90S_3 esm1v_t33_650M_UR90S_4 \
        esm1v_t33_650M_UR90S_5 \
    --sequence "${WT_SEQ}" \
    --dms-input "${DMS_CSV}" \
    --mutation-col "${MUT_COL}" \
    --dms-output "${OUT_CSV}" \
    --offset-idx "${OFFSET}" \
    --scoring-strategy "${STRATEGY}"

echo "wrote ${OUT_CSV}"

# Then ensemble the five model columns:
python -c "
import pandas as pd
df = pd.read_csv('${OUT_CSV}')
cols = [c for c in df.columns if c.startswith('esm1v_t33_650M_UR90S_')]
df['esm1v_ensemble'] = df[cols].mean(axis=1)
df.to_csv('${OUT_CSV}', index=False)
print('added esm1v_ensemble column')
"
