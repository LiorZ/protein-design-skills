# Installation, cache, and Docker

## PyPI install

```bash
pip install -U "boltz[cuda]"
```

The `[cuda]` extra installs `cuequivariance_ops_cu12`, `cuequivariance_ops_torch_cu12`, and `cuequivariance_torch` (≥ 0.5.0) — these are the CUDA-12-compiled kernels Boltz uses on recent NVIDIA GPUs.

For CPU-only or non-CUDA hardware, omit the extras:

```bash
pip install -U boltz
```

For daily updates / development:

```bash
git clone https://github.com/jwohlwend/boltz.git
cd boltz
pip install -e ".[cuda]"
```

A fresh virtualenv / conda env is **strongly recommended** — Boltz pins exact versions of `pytorch-lightning`, `hydra-core`, `einops`, `einx`, `fairscale`, etc., and mixing it into an existing scientific env usually causes conflicts. Example:

```bash
python -m venv boltz-env
source boltz-env/bin/activate
pip install -U "boltz[cuda]"
```

Python: **3.10 – 3.12** (`requires-python = ">=3.10,<3.13"`). PyTorch ≥ 2.2.

## Verify install

```bash
boltz --help
boltz predict --help
```

Both should return without error. The `boltz` script is registered in `pyproject.toml` as `boltz.main:cli`.

## Model weights / CCD cache

On the **first** `boltz predict`, Boltz downloads:

| Path under cache       | Size  | Notes |
|------------------------|-------|-------|
| `boltz2_conf.ckpt`     | ~1 GB | Boltz-2 structure model |
| `boltz2_aff.ckpt`      | ~1 GB | Boltz-2 affinity head |
| `mols.tar` → `mols/`   | ~1 GB | Per-residue / per-ligand reference structures for Boltz-2 |
| `boltz1_conf.ckpt`     | ~1 GB | Boltz-1 structure model (only if `--model boltz1`) |
| `ccd.pkl`              | ~50 MB | CCD dictionary used by Boltz-1 |

Download sources (with fallbacks):

```
https://model-gateway.boltz.bio/ (primary)
https://huggingface.co/boltz-community/boltz-1/...  (fallback)
https://huggingface.co/boltz-community/boltz-2/...  (fallback)
```

Cache resolution order:

1. `--cache /abs/path` CLI flag.
2. `BOLTZ_CACHE` environment variable (**must be an absolute path**, otherwise raises).
3. `~/.boltz` (default).

To pre-warm a cache (useful for Docker / offline clusters):

```python
from pathlib import Path
from boltz.main import download_boltz1, download_boltz2

cache = Path("/opt/boltz_cache")
cache.mkdir(parents=True, exist_ok=True)
download_boltz2(cache)
download_boltz1(cache)  # only if you'll use --model boltz1
```

## Docker

The repo ships a `Dockerfile` based on a Vast.ai CUDA-12.4.1 image:

```bash
# GPU build (default)
docker build -t boltz:latest .

# Run with the current dir mounted at /workspace
docker run --rm --gpus all -v "$PWD:/workspace" \
  boltz:latest predict /workspace/input.yaml --use_msa_server
```

`BOLTZ_CACHE=/opt/boltz_cache` is baked into the image, and weights for both Boltz-1 and Boltz-2 are downloaded at build time (so the image is ~7 GB but offline-ready).

CPU-only image (skip CUDA extras and use a slim base):

```bash
docker build --build-arg BASE_IMAGE=python:3.11-slim --build-arg BOLTZ_EXTRAS= -t boltz:cpu .
docker run --rm -v "$PWD:/workspace" boltz:cpu predict /workspace/input.yaml --use_msa_server
```

The entrypoint is `boltz`, so the image accepts subcommands directly (`docker run ... boltz:latest predict ...` is short for `boltz predict ...`).

## Troubleshooting installation

- **`ImportError: libcudart.so.12`** — your driver doesn't match CUDA 12. Either install a matching driver, or use the CPU install (drop `[cuda]`).
- **`cuequivariance ... not found / not compiled for sm_XX`** — your GPU is older than what the kernels target (typically pre-Ampere). Re-run with `--no_kernels`; perf hit is small for inference.
- **Slow first run** — model + mol cache download. Subsequent runs reuse `~/.boltz` (or `$BOLTZ_CACHE`).
- **`BOLTZ_CACHE must be an absolute path`** — `BOLTZ_CACHE=~/cache` doesn't expand; use `BOLTZ_CACHE=/home/me/cache` or `export BOLTZ_CACHE="$(realpath ~/cache)"`.
- **macOS / Apple Silicon** — only CPU install works; Apple GPUs aren't supported by the kernels. Expect very slow predictions.

See [troubleshooting.md](troubleshooting.md) for runtime issues.
