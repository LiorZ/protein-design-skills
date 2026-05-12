# Installation

BoltzGen requires **Python ≥ 3.11** and an NVIDIA GPU with CUDA 12.x.
The package is published to PyPI as `boltzgen` and hosts model weights on
Hugging Face Hub.

## Recommended path — conda + pip

```bash
# 1. Fresh env (Python 3.12 is what the project tests against)
conda create -n bg python=3.12 -y
conda activate bg

# 2. Install
pip install boltzgen

# 3. (Optional) pre-download all weights so the first run doesn't stall
boltzgen download all
```

The very first `boltzgen run` (or `boltzgen download all`) pulls ~6 GB
of checkpoints + the small-molecule reference data (`mols.zip`) into
`~/.cache` by default. Override with either:

```bash
boltzgen run ... --cache /scratch/$USER/bg_cache
# or
export HF_HOME=/scratch/$USER/bg_cache
```

`HF_HOME` is honored because all downloads go through `huggingface_hub`.

## Editable / dev install

```bash
git clone https://github.com/HannesStark/boltzgen
cd boltzgen
pip install -e .[dev]    # pulls in wandb, redis, ruff, pytest …
```

The dev extra is required only if you are training models or running the
tests. The `[lint]`, `[test]`, `[doc]`, `[build]` extras can be installed
individually if you want a thinner footprint.

## Docker

```bash
# Build
docker build -t boltzgen .

# Run (weights are downloaded lazily into the mounted cache directory)
mkdir -p workdir cache
docker run --rm --gpus all \
  -v "$(realpath workdir)":/workdir \
  -v "$(realpath cache)":/cache \
  -v "$(realpath example)":/example \
  boltzgen \
    boltzgen run /example/vanilla_protein/1g13prot.yaml \
      --output /workdir/test \
      --protocol protein-anything \
      --num_designs 2
```

Bake the weights into the image instead:

```bash
docker build -t boltzgen:weights --build-arg DOWNLOAD_WEIGHTS=true .
```

The default Dockerfile is based on
`nvidia/cuda:12.2.2-cudnn8-devel-ubuntu22.04`, installs Python 3.11 from
`deadsnakes`, sets `HF_HOME=/cache`, runs as a non-root `boltzgen` user
(UID 1000), and uses `pip install -e .` (so the source under `/app` is
the live source).

## Manual weight download

```bash
# All artifacts (~6 GB)
boltzgen download all --cache ~/.cache

# Subset
boltzgen download design-diverse design-adherence
boltzgen download folding affinity
boltzgen download inverse-fold
boltzgen download moldir          # small-molecule reference data (mols.zip)
```

Available artifact names:

| Name                | What it is                                                       | Hugging Face source                                    |
|---------------------|------------------------------------------------------------------|---------------------------------------------------------|
| `design-diverse`    | Diffusion checkpoint tuned for design diversity                  | `boltzgen/boltzgen-1:boltzgen1_diverse.ckpt`            |
| `design-adherence`  | Diffusion checkpoint tuned for site-adherence                    | `boltzgen/boltzgen-1:boltzgen1_adherence.ckpt`          |
| `inverse-fold`      | Inverse-folding model (trained jointly with the diffusion model) | `boltzgen/boltzgen-1:boltzgen1_ifold.ckpt`              |
| `folding`           | Boltz-2 structure model used for refolding                       | `boltzgen/boltzgen-1:boltz2_conf_final.ckpt`            |
| `affinity`          | Boltz-2 affinity head                                            | `boltzgen/boltzgen-1:boltz2_aff.ckpt`                   |
| `moldir`            | Per-ligand / per-residue reference structures (`mols.zip`)       | `boltzgen/inference-data:mols.zip`                      |
| `all`               | All of the above                                                 | —                                                       |

You can also pass any HF locator as a checkpoint path:
`--design_checkpoints huggingface:boltzgen/boltzgen-1:boltzgen1_diverse.ckpt`
or a local file path.

## Authenticated Hugging Face

Weights are downloaded with a default community token; if you need to
authenticate (corporate proxy, gated mirror) set either:

```bash
export HF_TOKEN=hf_…
# or pass per-invocation
boltzgen run ... --models_token hf_…
```

## CPU / non-CUDA notes

The code path exists but is unsupported in practice — diffusion sampling
of a 100-aa binder against a 200-aa target is intractable without a GPU.
For development on a Mac / CPU box, set up a remote dev box (e.g.,
RunPod, vast.ai, Modal — see the `vastai` and Modal-based skills) and
run there.

## Old GPUs (capability < 8)

`cuequivariance` kernels are enabled automatically only on
device-capability ≥ 8 (A100, H100, L40S, RTX 30/40-series). If you see
import or runtime errors mentioning `cuequivariance`, drop the kernels:

```bash
boltzgen run ... --use_kernels false
```

Slight performance hit, no accuracy loss.

## Verifying the install

```bash
boltzgen --version
boltzgen run --help
boltzgen check example/vanilla_protein/1g13prot.yaml
```

If `boltzgen check` opens, validates, and writes a CIF, your install
is good (no GPU is touched by `check`).

## Common install errors

| Symptom                                                            | Fix                                                                                            |
|--------------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| `numpy` / `numba` version conflict                                 | Use a *fresh* env. BoltzGen pins `numpy==2.0.2`, `numba==0.61.0`.                              |
| `cuequivariance_ops_cu12` missing                                  | Make sure you have CUDA 12.x on the host. The package is a hard dep.                            |
| `ModuleNotFoundError: cuequivariance_ops_torch_cu12` after upgrade | The new minor wasn't picked up. `pip install --upgrade cuequivariance-ops-torch-cu12`.          |
| `pdbeccdutils` build error                                         | Need `libboost`, `libxml2`, `libxslt` headers. Use the Docker image or install the deb packages. |
| First `boltzgen run` hangs at "downloading"                        | Pre-fetch with `boltzgen download all` to a fast disk; behind a corporate proxy set `HF_HOME` and `HF_HUB_ENABLE_HF_TRANSFER=1`. |
