# All ESM checkpoints

Every checkpoint is exposed as a function on `esm.pretrained` that returns
a `(model, alphabet)` tuple. Weights download to
`~/.cache/torch/hub/checkpoints/<name>.pt` on first call.

## ESM-2 (recommended PLM)

| Function | Layers | Params | Embed dim | Dataset | URL |
|----------|--------|--------|-----------|---------|-----|
| `esm2_t6_8M_UR50D`   | 6  | 8 M   | 320  | UR50/D 2021_04 | https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t6_8M_UR50D.pt |
| `esm2_t12_35M_UR50D` | 12 | 35 M  | 480  | UR50/D 2021_04 | https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t12_35M_UR50D.pt |
| `esm2_t30_150M_UR50D`| 30 | 150 M | 640  | UR50/D 2021_04 | https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t30_150M_UR50D.pt |
| `esm2_t33_650M_UR50D`| 33 | 650 M | 1280 | UR50/D 2021_04 | https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t33_650M_UR50D.pt |
| `esm2_t36_3B_UR50D`  | 36 | 3 B   | 2560 | UR50/D 2021_04 | https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t36_3B_UR50D.pt |
| `esm2_t48_15B_UR50D` | 48 | 15 B  | 5120 | UR50/D 2021_04 | https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t48_15B_UR50D.pt |

- The number after `t` is the layer count — that's the layer index for the
  final-layer representation (`repr_layers=[33]` for the 650 M model).
- 650 M is the sweet spot for most downstream ML. 3 B helps marginally on
  hard tasks. 15 B rarely worth it for transfer learning; useful for the
  best ESMFold-quality structures and for raw scientific curiosity.
- Sequences are truncated at 1024 tokens (1022 residues + BOS + EOS) by
  default. ESM-2 *can* run on longer sequences via the
  `--truncation_seq_length` flag but quality drops past the training
  length.

## ESMFold (single-sequence structure)

| Function | Description | URL |
|----------|-------------|-----|
| `esmfold_v1` | **Recommended.** ESM-2 3 B backbone + 690 M folding trunk. | https://dl.fbaipublicfiles.com/fair-esm/models/esmfold_3B_v1.pt |
| `esmfold_v0` | Original release (paper experiments) | https://dl.fbaipublicfiles.com/fair-esm/models/esmfold_3B_v0.pt |
| `esmfold_structure_module_only_{8M,35M,150M,650M,3B,15B}` | Ablation models, **not recommended for predictions** | — |
| `esmfold_structure_module_only_{8M,35M,150M,650M,3B,15B}_270K` / `_500K` | Partially trained variants | — |

ESMFold weights are ~10 GB on disk because they bundle the ESM-2 3 B LM.

## ESM-IF1 (inverse folding)

| Function | Layers | Params | Embed dim | Dataset |
|----------|--------|--------|-----------|---------|
| `esm_if1_gvp4_t16_142M_UR50` | 20 | 124 M | 512 | CATH 4.3 + 12 M AF2-predicted UR50 |

The "142 M" in the name is historical and overcounts; the actual parameter
count is ~124 M. Encoder is GVP graph layers; decoder is autoregressive
sequence transformer. Native sequence recovery 51 %, 72 % on buried
residues.

## ESM-1v (variant effect ensemble)

| Function | Layers | Params | Embed dim |
|----------|--------|--------|-----------|
| `esm1v_t33_650M_UR90S_1` … `_5` | 33 | 650 M | 1280 |

Same architecture as ESM-1b but trained on UR90/S. Five-model ensemble
averaging is the published recipe. ESM-2 also works well for this task
and is usually faster — but the paper baseline uses ESM-1v.

## MSA Transformer

| Function | Layers | Params | Embed dim |
|----------|--------|--------|-----------|
| `esm_msa1b_t12_100M_UR50S` | 12 | 100 M | 768 |
| `esm_msa1_t12_100M_UR50S`  | 12 | 100 M | 768 |

Use `1b` (June 2021, ICML version). Input tensor is `(B, N, L)` —
batch × MSA depth × residues. `MSATransformer` cannot be used with the
generic `esm-extract` CLI (extract.py explicitly errors on it).

## ESM-1b / ESM-1 (legacy)

| Function | Layers | Params | Embed dim |
|----------|--------|--------|-----------|
| `esm1b_t33_650M_UR50S` | 33 | 650 M | 1280 |
| `esm1_t34_670M_UR50S` / `_UR50D` / `_UR100` | 34 | 670 M | 1280 |
| `esm1_t12_85M_UR50S` | 12 | 85 M | 768 |
| `esm1_t6_43M_UR50S`  | 6  | 43 M | 768 |

Superseded by ESM-2 for almost every use.

## Regression weights (contact prediction)

A separate `*-contact-regression.pt` file is auto-downloaded for every
checkpoint except:

- ESM-1v (`esm1v_*`)
- ESM-IF (`esm_if*`)
- Partially-trained ESM-2 (`esmfold_structure_module_only_*_270K` /
  `_500K`)

URL pattern:
`https://dl.fbaipublicfiles.com/fair-esm/regression/<name>-contact-regression.pt`

For those models that lack regression weights, `predict_contacts(...)` and
`return_contacts=True` return tensors that are not the published
predictor and should not be used.

## Loading a model from a local checkpoint

```python
from esm.pretrained import load_model_and_alphabet
model, alphabet = load_model_and_alphabet("/path/to/esm2_t33_650M_UR50D.pt")
# Regression weights must sit next to it:
#   /path/to/esm2_t33_650M_UR50D-contact-regression.pt
```

`load_model_and_alphabet(name)` dispatches to `_local` if the argument
ends in `.pt` else `_hub`.

## Hugging Face mirror

ESM-1b, ESM-2 (all sizes), and ESMFold are also available via
`transformers` (`EsmModel`, `EsmForMaskedLM`, `EsmForProteinFolding`).
That avoids `nvcc` / OpenFold install pain for ESMFold but is a different
API; this skill covers the `fair-esm` reference path.

## ESM-3 / ESM-C

These models are **not** in `fair-esm`. They live in
[`evolutionaryscale/esm`](https://github.com/evolutionaryscale/esm). If
you need ESM-3, install that package instead.
