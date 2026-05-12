# Installation

Chai-1 is distributed on PyPI and as a GitHub repo. The package is named
`chai_lab`; the installed CLI is `chai-lab`.

## PyPI install (recommended for users)

```bash
pip install chai_lab==0.6.1
```

Pin the version — the Python API changes between minor releases. The
package depends on PyTorch with CUDA + bfloat16 support; install a torch
build matching your CUDA before installing `chai_lab` if pip's default
torch wheel is wrong for your system.

## Latest dev build

```bash
pip install git+https://github.com/chaidiscovery/chai-lab.git
```

The `main` branch updates daily; use it only if you need an unreleased
feature.

## Editable install (for development)

```bash
git clone https://github.com/chaidiscovery/chai-lab.git
cd chai-lab
pip install -e .
```

The project uses Hatchling + a `requirements.in` for runtime deps and
`requirements.dev` for dev deps.

## Where weights live

On first inference run, Chai downloads its TorchScript components
(`feature_embedding.pt`, `token_embedder.pt`, `trunk.pt`,
`diffusion_module.pt`, `confidence_head.pt`, `bond_loss_input_proj.pt`,
plus ESM-2 weights) into:

```
<site-packages>/chai_lab/downloads/
```

Override the location with the `CHAI_DOWNLOADS_DIR` env var — useful in
Docker, on a shared/mounted drive, or when `site-packages` is read-only:

```bash
export CHAI_DOWNLOADS_DIR=/scratch/chai-downloads
chai-lab fold input.fasta out/
```

Total weight size is ~25 GB. The download is one-shot per cache dir.

## GPU requirements

| Tier         | GPU examples            | What it can do |
|--------------|-------------------------|----------------|
| Minimum      | RTX 4090, A10, A30      | Small complexes (<700 tokens). MSAs may push you over VRAM. |
| Recommended  | L40S 48GB               | Most workloads |
| Comfortable  | A100 80GB, H100 80GB    | Up to the 2048-token cap with MSAs + templates |

Multi-GPU is supported only via `chai-lab fold-batch` — one fasta per GPU
in parallel. There is no within-fold model parallelism.

## Docker

The repo ships two Dockerfiles:

- `Dockerfile.chailab` — runtime image with Chai installed, suitable for
  Vast.ai / RunPod / k8s.
- `Dockerfile.vastai` — same but tuned for Vast.ai's filesystem layout.

Both expect `CHAI_DOWNLOADS_DIR` to point at a mounted volume so weights
persist across container restarts.

## Devcontainer

The repo ships a `.devcontainer/` config; VS Code "Reopen in Container"
gives an identical dev environment. Recommended for contributors only.

## Verifying the install

```bash
chai-lab --help
chai-lab citation     # prints BibTeX
python -c "from chai_lab.chai1 import run_inference; print('ok')"
```

The first real inference run will trigger the weight download (slow,
once); subsequent runs are fast.
