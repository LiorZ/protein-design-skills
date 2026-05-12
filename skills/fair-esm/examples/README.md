# `fair-esm` examples

Each example is short (≤ 60 lines) and self-contained. Most default to
the smallest checkpoint (`esm2_t6_8M_UR50D`, 8 M params, ~30 MB
download) so they run in well under a minute on CPU. Swap to a larger
checkpoint when you're ready.

| File | What it does |
|------|--------------|
| [`extract_embeddings.py`](extract_embeddings.py)         | Minimal ESM-2 forward pass; saves mean + per-token reps |
| [`bulk_extract.sh`](bulk_extract.sh)                     | `esm-extract` CLI invocation pattern |
| [`fold_single.py`](fold_single.py)                       | Load `esmfold_v1`; fold one sequence; print mean pLDDT |
| [`fold_bulk.sh`](fold_bulk.sh)                           | `esm-fold` CLI for bulk FASTA folding |
| [`inverse_fold_sample.py`](inverse_fold_sample.py)       | ESM-IF1 sample N sequences for a target chain |
| [`inverse_fold_multichain.py`](inverse_fold_multichain.py)| Multi-chain complex sequence design |
| [`inverse_fold_score.py`](inverse_fold_score.py)         | Score variant sequences against a backbone |
| [`inverse_fold_partial_mask.py`](inverse_fold_partial_mask.py) | Mask a span, resample with partial constraint |
| [`inverse_fold_encoder_output.py`](inverse_fold_encoder_output.py) | Extract L × 512 structure representation |
| [`variant_dms.sh`](variant_dms.sh)                       | 5-model ESM-1v ensemble DMS scoring |
| [`contact_prediction.py`](contact_prediction.py)         | Extract attention-based contacts and plot |
| [`atlas_api.sh`](atlas_api.sh)                           | Fold via the ESM Atlas public API |
