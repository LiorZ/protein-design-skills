# `boltz predict` — full CLI reference

```bash
boltz predict <INPUT_PATH> [OPTIONS]
```

`<INPUT_PATH>` is either:

- a single `.yaml` (preferred) or `.fasta` (deprecated) file, **or**
- a directory containing any mix of `.yaml` and `.fasta` files. Every file inside is predicted, sharded across `--devices` GPUs via PyTorch-Lightning DDP.

There is no separate `train` console script — training is launched via `python scripts/train/train.py` (see [training.md](training.md)).

## Common flags

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--out_dir PATH` | path | `./` | Root for predictions. A subdir `boltz_results_<input_stem>/` is always created. |
| `--cache PATH` | path | `~/.boltz` (or `$BOLTZ_CACHE`) | Where to keep weights and CCD. |
| `--checkpoint PATH` | path | None | Custom structure checkpoint (else default per `--model`). |
| `--affinity_checkpoint PATH` | path | None | Custom affinity checkpoint (Boltz-2). |
| `--model boltz1\|boltz2` | choice | `boltz2` | Which model. |
| `--devices N` | int | `1` | Number of GPUs (>1 → DDP). |
| `--accelerator gpu\|cpu\|tpu` | choice | `gpu` | Hardware. |
| `--num_workers N` | int | `2` | DataLoader workers per device. |
| `--preprocessing-threads N` | int | `cpu_count()` | Threads for input preprocessing. |
| `--seed N` | int | None | RNG seed (call `pytorch_lightning.seed_everything`). |
| `--override` | flag | False | Re-run even if cached predictions / processed inputs exist. |
| `--no_kernels` | flag | False | Disable `cuequivariance` kernels (use on old NVIDIA cards). |

## Sampling / diffusion

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--recycling_steps N` | int | `3` | Trunk recycles. AF3-style is 10. |
| `--sampling_steps N` | int | `200` | Diffusion sampling steps. |
| `--diffusion_samples N` | int | `1` | Candidate structures to generate. AF3-style is 5–25. |
| `--max_parallel_samples N` | int | `5` | Cap on parallel diffusion samples (memory tradeoff). |
| `--step_scale FLOAT` | float | `1.5` (Boltz-2) / `1.638` (Boltz-1) | Diffusion temperature. Range 1–2; lower → more diversity. |
| `--method NAME` | str | None | Boltz-2 only. Conditions on a determination method (see below). |

Allowed `--method` values (case-insensitive):

```
md, x-ray diffraction, electron microscopy, solution nmr,
solid-state nmr, neutron diffraction, electron crystallography,
fiber diffraction, powder diffraction, infrared spectroscopy,
fluorescence transfer, epr, theoretical model, solution scattering,
other, afdb, boltz-1, future1, future2, future3, future4, future5
```

In practice, `x-ray diffraction` is the safe default if you want to bias the prediction toward crystallographic-quality geometry. `afdb` mimics the AlphaFold-DB distribution; `md` produces MD-snapshot-style ensembles.

## MSA / server

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--use_msa_server` | flag | False | Query ColabFold MMseqs2 for any protein chain without `msa:`. |
| `--msa_server_url URL` | str | `https://api.colabfold.com` | Self-hosted endpoint. |
| `--msa_pairing_strategy greedy\|complete` | str | `greedy` | How to pair chains for multimers. |
| `--msa_server_username STR` | str | None (or `BOLTZ_MSA_USERNAME`) | Basic-auth username. |
| `--msa_server_password STR` | str | None (or `BOLTZ_MSA_PASSWORD`) | Basic-auth password. |
| `--api_key_header STR` | str | None | API-key header name (default `X-API-Key`). |
| `--api_key_value STR` | str | None (or `MSA_API_KEY_VALUE`) | API-key value. |
| `--max_msa_seqs N` | int | `8192` | Cap MSA depth. |
| `--subsample_msa` | flag | False | Subsample at runtime. |
| `--num_subsampled_msa N` | int | `1024` | Subsample depth when `--subsample_msa` is set. |

Only one auth scheme can be used at a time; mixing basic + API key raises an error. See [msas.md](msas.md) for full details.

## Outputs / extras

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--output_format mmcif\|pdb` | choice | `mmcif` | Structure format. |
| `--write_full_pae` | flag | False | Dump per-token PAE NPZ for every sample. |
| `--write_full_pde` | flag | False | Dump per-token PDE NPZ for every sample. |
| `--write_embeddings` | flag | False | Dump per-token single (`s`) and pair (`z`) embeddings NPZ. |
| `--use_potentials` | flag | False | Apply inference-time physical potentials (slower, cleaner poses; equivalent to the "Boltz-1x" mode in the Boltz-1 paper). |

## Affinity (Boltz-2 only)

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--sampling_steps_affinity N` | int | `200` | Diffusion steps for affinity head. |
| `--diffusion_samples_affinity N` | int | `5` | Affinity samples (averaged in the JSON). |
| `--affinity_mw_correction` | flag | False | Apply molecular-weight correction to the affinity value head. Recommended in some hit-finding workflows; see [affinity.md](affinity.md). |
| `--affinity_checkpoint PATH` | path | None | Custom affinity checkpoint. |

Affinity is **only** computed for `properties.affinity.binder` entries in the YAML, and only for **single-chain ligand binders ≤ 128 heavy atoms**.

## Examples

Minimal:

```bash
boltz predict input.yaml --use_msa_server
```

AF3-style sampling:

```bash
boltz predict input.yaml --use_msa_server \
  --recycling_steps 10 --diffusion_samples 5
```

Two GPUs, deterministic, write everything:

```bash
boltz predict inputs/ \
  --use_msa_server \
  --devices 2 \
  --seed 42 \
  --write_full_pae --write_full_pde \
  --output_format pdb
```

Boltz-1 (legacy parity):

```bash
boltz predict input.yaml --use_msa_server --model boltz1
```

Inference potentials (cleaner poses, slower):

```bash
boltz predict input.yaml --use_msa_server --use_potentials
```

Old GPU:

```bash
boltz predict input.yaml --use_msa_server --no_kernels
```

CPU smoke test (slow):

```bash
boltz predict examples/prot.yaml --accelerator cpu --use_msa_server
```

## Caching behavior

Inside `--out_dir`, Boltz creates `boltz_results_<stem>/`:

```
boltz_results_<stem>/
├── processed/          # tokenized inputs, MSAs, constraints, templates (reused if same name)
├── lightning_logs/
└── predictions/
    └── <stem>/         # per-sample CIFs + JSONs + NPZs
```

Between runs that share `--out_dir`:

- If `processed/<stem>` already exists, preprocessing is skipped (faster reruns).
- If `predictions/<stem>` already exists, that input is **skipped** entirely.
- Add `--override` to ignore both caches and recompute everything.

## Exit codes / errors

Boltz uses Lightning's default behaviour: errors propagate as Python exceptions and the script exits non-zero. Common ones:

- `ValueError: Method conditioning is not supported for Boltz-1.` — `--method` requires `--model boltz2`.
- `ValueError: Affinity prediction is only supported for Boltz2!` — same for `properties.affinity` in the YAML.
- `ValueError: Templates are not supported in Boltz 1.0!` — Boltz-1 has no template head.
- `RuntimeError: Failed to download model from all URLs.` — both `model-gateway.boltz.bio` and the HuggingFace fallback unreachable; mirror the file manually into the cache.
- `ValueError: BOLTZ_CACHE must be an absolute path` — env var must be absolute.
