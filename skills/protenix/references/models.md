# Model zoo — which checkpoint to use

Pass the checkpoint with `-n/--model_name`. Naming convention:
`protenix_{size}_{features}_{version}` where size ∈ `base`/`mini`/`tiny`,
features ∈ `default`/`constraint`/`esm`/`ism` (multiple joined by `-`), e.g.
`protenix_base_default_v1.0.0`. `protenix-v2` is the simplified name for the
newest enhanced model.

| Model | Params | MSA | RNA MSA | Template | Constraint | ESM | Data cutoff | Notes |
|-------|:------:|:---:|:-------:|:--------:|:----------:|:---:|:-----------:|-------|
| `protenix-v2` | 464 M | ✅ | ✅ | ✅ | ❌ | ❌ | 2021-09-30 | **Best accuracy** (antibody-antigen, ligand plausibility). **Weights not served publicly yet (403).** |
| `protenix_base_default_v1.0.0` | 368 M | ✅ | ✅ | ✅ | ❌ | ❌ | 2021-09-30 | **Recommended default.** AF3-aligned; outperforms AF3 on diverse benchmarks. |
| `protenix_base_20250630_v1.0.0` | 368 M | ✅ | ✅ | ✅ | ❌ | ❌ | 2025-06-30 | Same size, **newer data cutoff** — for applied/practical use. |
| `protenix_base_default_v0.5.0` | 368 M | ✅ | ❌ | ❌ | ❌ | ❌ | 2021-09-30 | Backward-compat for v0.5.0-era pipelines. |
| `protenix_base_constraint_v0.5.0` | 368 M | ✅ | ❌ | ❌ | ✅ | ❌ | 2021-09-30 | **Required for `pocket`/`contact` constraints** (pocket+contact embedders). |
| `protenix_mini_default_v0.5.0` | 134 M | ✅ | ❌ | ❌ | ❌ | ❌ | 2021-09-30 | Fast; high-throughput screening. |
| `protenix_tiny_default_v0.5.0` | 110 M | ✅ | ❌ | ❌ | ❌ | ❌ | 2021-09-30 | Fastest; fewest layers. |
| `protenix_mini_esm_v0.5.0` | 135 M | (off) | ❌ | ❌ | ❌ | ✅ | 2021-09-30 | Single-sequence (ESM2-3B); no MSA. **Needs ESM weights (not downloaded by default).** |
| `protenix_mini_ism_v0.5.0` | 135 M | (off) | ❌ | ❌ | ❌ | ✅ | 2021-09-30 | As above with ISM embeddings. |

## Default inference params (`--use_default_params true`)

| Model class | `cycle` (Pairformer) | `step` (diffusion) | `use_msa` |
|-------------|:--------------------:|:------------------:|:---------:|
| base / 20250630 / v0.5.0 / constraint / v2 | 10 | 200 | true |
| mini / tiny | 4 | 5 | true |
| mini-esm / mini-ism | 4 | 5 | **false** |

Always set `--use_default_params true`; an unrecognized model name raises a
"not supported for inference" error there, which is a useful guard.

## Picking a model

- **General complex, max accuracy you can actually download:**
  `protenix_base_default_v1.0.0`.
- **Recent targets / applied work:** `protenix_base_20250630_v1.0.0` (training
  data through mid-2025).
- **Throughput (many jobs):** `protenix_mini_default_v0.5.0`, then `tiny`. Fewer
  cycles/steps → much faster, some accuracy loss. Mini > Tiny in capacity.
- **You have a known pocket/epitope or distance restraints:**
  `protenix_base_constraint_v0.5.0` + a `constraint` block (see `inputs.md`).
- **No MSA available / orphan sequence:** an ESM/ISM mini model (download the
  ESM2-3B weights first), or run a base model with `--use_msa false`.
- **Templates or RNA MSA needed:** only `protenix_base_default_v1.0.0`,
  `protenix_base_20250630_v1.0.0`, `protenix-v2` support them (`--use_template` /
  `--use_rna_msa`).

## Inference-time scaling

For hard targets (e.g. antibody–antigen) accuracy improves log-linearly with the
sampling budget. Increase `--sample` and/or use multiple `--seeds`, then rank by
`ranking_score` (see `outputs.md`). Protenix-v2 reaches Protenix-v1's 1000-seed
quality at ~5 seeds, so prefer v2 when you can get the weights.

## Weights & availability

Downloaded by `apptainer/download_weights.sh` into
`$PROTENIX_ROOT_DIR/checkpoint/` (the six non-ESM `*.pt` above, ~1.5 GB each;
mini/tiny smaller). **Not** fetched by default:

- `protenix-v2.pt` — endpoint returns HTTP 403 (not public yet). Re-add to the
  `CHECKPOINTS` array in `download_weights.sh` when published.
- ESM/ISM checkpoints + `esm2_t36_3B_UR50D*` (~5 GB) — append to the script to
  enable the `_esm`/`_ism` models.

CCD/cluster/release caches go in `$PROTENIX_ROOT_DIR/common/` (see
`installation.md`). Full upstream detail: `~/Repos/Protenix/docs/supported_models.md`.
</content>
