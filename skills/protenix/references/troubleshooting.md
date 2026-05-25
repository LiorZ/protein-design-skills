# Troubleshooting

## Build time

| Symptom | Cause / fix |
|---------|-------------|
| `apptainer build` fails: fakeroot not allowed | `--fakeroot` subuid/subgid not configured. Build with `sudo apptainer build ...`, or build on a workstation and `scp` the `.sif`. |
| Out of space mid-build (`/tmp` or `$HOME` full) | Point caches at a big FS: `export APPTAINER_CACHEDIR=/big/cache APPTAINER_TMPDIR=/big/tmp` before `bash apptainer/build.sh`. |
| pip resolve/network errors during `%post` | The build needs internet (Docker Hub base, PyPI, CUTLASS clone). Retry on a connected node; behind a proxy, set `HTTP(S)_PROXY` in the build environment. |
| Base image pull fails | `pytorch/pytorch:2.7.1-cuda12.6-cudnn9-devel` must be reachable from Docker Hub. Pre-pull or mirror it if your site blocks Docker Hub. |

## Weights & paths

| Symptom | Cause / fix |
|---------|-------------|
| `run_protenix.sh`: "weights dir not found" | Download first: `PROTENIX_ROOT_DIR=/shared/ModelWeights/Protenix bash apptainer/download_weights.sh`. |
| Checkpoint-not-found at load | `-n` name has no matching `$PROTENIX_ROOT_DIR/checkpoint/<name>.pt`. Check spelling vs. `models.md`; confirm the bind-mount and `PROTENIX_ROOT_DIR` env both point at the host dir. |
| `protenix-v2` download/load fails (403) | `protenix-v2.pt` isn't served publicly yet. Use `protenix_base_default_v1.0.0`, or add the URL to `download_weights.sh` once published. |
| ESM/ISM model fails to load | ESM2-3B weights aren't downloaded by default. Add `esm2_t36_3B_UR50D*` + the `_esm`/`_ism` checkpoints to `download_weights.sh`. |
| Downloads crawl at ~40 KB/s | The TOS server throttles single streams. Install `aria2c` (the script uses 16 connections when present); otherwise `wget -c` resumes. |
| CCD / missing `common/*` errors | `$PROTENIX_ROOT_DIR/common/` lacks `components.cif` etc. Re-run `download_weights.sh`; Protenix also auto-fetches missing caches into this (writable) dir. |

## Runtime — GPU & kernels

| Symptom | Cause / fix |
|---------|-------------|
| Runs on CPU / "no CUDA device" | Missing `--nv`. Use `apptainer/run_protenix.sh` (adds it) or add `--nv` to a manual `apptainer run`. Confirm host `nvidia-smi` works. |
| CUDA error: driver too old | Host driver must support CUDA 12.6 (≥ 555). Update the host NVIDIA driver (no in-container toolkit needed). |
| First run hangs for minutes compiling | Expected: layer-norm / Evoformer kernels JIT-compile into `$TORCH_EXTENSIONS_DIR` once, then cache. Ensure that dir is writable; on read-only `$HOME` set `--env TORCH_EXTENSIONS_DIR=/node/scratch/ext`. |
| Triton / triangle-attention kernel crash (RTX 3090/4090) | Consumer-GPU kernel issue (#185). It should fall back to PyTorch automatically; if not, add `--triatt_kernel torch --trimul_kernel torch`. |
| DeepSpeed Evoformer (`--triatt_kernel deepspeed`) fails | Needs `CUTLASS_PATH` (image sets `/opt/cutlass`). If broken, switch to `--triatt_kernel cuequivariance` (default) or `torch`. |
| OOM on GPU | Reduce `--sample`; use a smaller model (`mini`/`tiny`); split a multi-chain job; keep `--dtype bf16` (default). Large token counts dominate memory. |
| DeepSpeed/Pydantic import error | Fixed upstream by DeepSpeed 0.17.5 (#182) — pinned in `requirements.txt`, so rebuild the SIF from current source. |

## Runtime — inference behaving oddly

| Symptom | Cause / fix |
|---------|-------------|
| cycle/step not what you set | `--use_default_params true` overrides `-c/-p` with the model's recommended values. Drop it to hand-tune, or rely on it for correctness. |
| MSA search runs when you didn't want it | With `--use_msa true` (default) and no MSA paths in the JSON, an MMseqs2 search runs. Pre-cache with `protenix msa`/`prep`, or set `--use_msa false`. |
| `--use_template`/`--use_rna_msa` asserts | Only `protenix_base_default_v1.0.0`, `protenix_base_20250630_v1.0.0`, `protenix-v2` support them. Switch model or drop the flag. |
| `kalign` not found (template search) | Install in the image / on PATH, or pass `--kalign_binary_path`. The SIF installs `kalign` + `hmmer`. |
| Constraints ignored | `pocket`/`contact` need `protenix_base_constraint_v0.5.0`. With another model the `constraint` block has no effect. |
| Slow per job from a checkout dir | Launch shadows baked-in `/opt/protenix` and recompiles kernels into your tree. Run from a plain data directory (see `installation.md`). |

## Inputs

| Symptom | Cause / fix |
|---------|-------------|
| JSON rejected / empty result | Top level must be a **list** of jobs, even for one (`runner/inference.py` validates non-empty list). |
| Ligand has no/garbage geometry | A `FILE_` ligand must contain a **3D conformation**. SMILES is embedded by RDKit. Bad SDFs are skipped with a warning in `protenix pred` over a ligand dir. |
| Ion vs. ligand confusion | Ions use a bare CCD code (`"MG"`); ligands prefix `CCD_` (`"CCD_ATP"`). |
| Covalent bond points to wrong atom | `entity` is the 1-based order in `sequences`; ligand `position` is `1` for single-CCD/SMILES/FILE; SMILES/FILE atoms are 0-based indices (or element+occurrence like `C3`). |
| dsDNA modeled as one strand | `dnaSequence` is single-stranded — add the reverse-complement as a second entry. |

## Sanity checks

```bash
# CLI present and version
apptainer/run_protenix.sh --help
apptainer exec --nv apptainer/protenix.sif protenix --version

# GPU visible inside the container
apptainer exec --nv apptainer/protenix.sif python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"

# Weights mounted and discoverable
ls "$PROTENIX_ROOT_DIR/checkpoint" "$PROTENIX_ROOT_DIR/common"

# Smallest end-to-end test (fast model, single sample)
apptainer/run_protenix.sh pred -i examples/input.json -o /tmp/ptx_test \
    -n protenix_tiny_default_v0.5.0 --use_default_params true --sample 1
```
</content>
