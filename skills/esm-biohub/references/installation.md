# Installation — building & running the `esm` SIF

The skill is built around running everything from an Apptainer / Singularity
image (`esm.sif`) so the heavy runtime (PyTorch + CUDA 12.6 + Biohub's
`transformers` fork + rdkit + biotite + flash-attn-optional) ships as a single
artifact. The repo source is `~/Repos/esm_biohub`; the definition file is
`esm.def`; the resulting SIF lives in the directory pointed to by
**`$SINGULARITY_HOME`**.

## The `$SINGULARITY_HOME` convention

The skill expects:

```bash
export SINGULARITY_HOME=/data/sifs            # or wherever you collect SIFs
ls "$SINGULARITY_HOME"/esm.sif                # this is the image
```

Add the `export` to your shell rc (`~/.bashrc`, `~/.zshrc`) so any new shell
sees it. Every example in this skill resolves the image as
`"$SINGULARITY_HOME"/esm.sif` — replace if your path differs.

## What's in the SIF

From `esm.def` (Bootstrap: docker, From: `nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04`):

- **OS**: Ubuntu 24.04 base.
- **Python**: 3.12 (system) with `update-alternatives` aliasing
  `python`/`python3`.
- **Venv**: `/opt/venv` (PEP 668 forces this on 24.04). On PATH via
  `%environment`.
- **PyTorch**: `torch torchvision torchaudio` from
  `https://download.pytorch.org/whl/cu126` (pinned to the image's CUDA).
- **`esm` 3.3.0**: installed from the bundled checkout at `/opt/esm` via
  `pip install .`. The `pyproject.toml` pulls in:
  - `transformers @ git+https://github.com/Biohub/transformers.git@3a8956fb…`
    — the **EvolutionaryScale fork** of transformers (contains the
    `ESMFold2Model` class etc.). Plain upstream `transformers` does **not**
    work.
  - `biotite>=1.0.0`, `rdkit`, `biopython`, `msgpack-numpy`, `brotli`,
    `attrs`, `pandas`, `cloudpathlib`, `httpx`, `tenacity`, `zstd`,
    `ipywidgets`, `py3dmol`, `pydssp`, `boto3`, `pygtrie`,
    `dna_features_viewer`, `accelerate`.
- **Source baked in** at `/opt/esm` (the package), `/opt/esm/cookbook` (the
  tutorials), `/opt/esm/tests`, `/opt/esm/tools`, `/opt/esm/_assets`.
- **A `/workspace` mountpoint** ready for `--bind /host:/workspace`.

The runscript is `exec python "$@"` — so `apptainer run --nv esm.sif foo.py`
behaves like `python foo.py` inside the container.

## Build it

### Locally with `--fakeroot`

```bash
cd ~/Repos/esm_biohub
apptainer build --fakeroot "$SINGULARITY_HOME"/esm.sif esm.def
```

You need an apptainer install where unprivileged user-namespace builds are
enabled (`apptainer config global --get` shows `allow setuid = no`,
`enable fakeroot = yes`; `/etc/subuid` and `/etc/subgid` populated for your
user). On Debian/Ubuntu the package is usually `apptainer-suid` plus
`apptainer-fakeroot`.

### Without fakeroot — `sudo`

```bash
sudo apptainer build "$SINGULARITY_HOME"/esm.sif esm.def
```

Slower (root-owned cache) but works without the fakeroot setup.

### On a cluster

If the cluster nodes can't run `apptainer build` (no fakeroot, no sudo):

1. Build the image on a workstation with the same arch (linux-amd64).
2. `scp` the resulting `esm.sif` to `$SINGULARITY_HOME` on the cluster.
3. Verify: `apptainer inspect "$SINGULARITY_HOME"/esm.sif`.

The SIF is fully self-contained — no host installs other than the NVIDIA
driver are needed on the cluster.

### Build cache & disk

The build pulls a 4-5 GB CUDA base layer, then ~5-8 GB of pip wheels
(PyTorch CUDA + transformers + the rest). Plan on **~10-15 GB of free disk**
in `$APPTAINER_CACHEDIR` (default `~/.apptainer/cache`) during the build,
and ~6-8 GB for the final image. Tear it down after:

```bash
apptainer cache clean -f         # drops OCI blob cache
```

If the build dies with "No space left on device", that's the cache — clean
it and retry, or set `APPTAINER_CACHEDIR=/big/disk/cache`.

## Run it

### One-off Python script

```bash
apptainer run --nv "$SINGULARITY_HOME"/esm.sif script.py [args ...]
```

`%runscript` is `exec python "$@"`, so the first arg is the script.

### Anything else — `exec`

```bash
apptainer exec --nv "$SINGULARITY_HOME"/esm.sif python -m esm
apptainer exec --nv "$SINGULARITY_HOME"/esm.sif jupyter notebook --no-browser --port 8888 /opt/esm/cookbook
apptainer exec --nv "$SINGULARITY_HOME"/esm.sif python -c "import esm, torch; print(esm.__version__, torch.cuda.is_available())"
```

### Interactive shell

```bash
apptainer shell --nv "$SINGULARITY_HOME"/esm.sif
# Inside:
Apptainer> which python                   # /opt/venv/bin/python
Apptainer> python -c "import esm; print(esm.__version__)"
```

### GPU selection

`--nv` exposes **all** host GPUs. Restrict at the container boundary:

```bash
apptainer exec --nv --env CUDA_VISIBLE_DEVICES=0 "$SINGULARITY_HOME"/esm.sif python script.py
```

Multi-GPU is supported by the underlying transformers code (e.g.
`device_map="auto"`), but ESMFold2 inference is single-GPU.

### Network access

`apptainer run/exec/shell` inherit the host network namespace by default —
so `from_rcsb(...)`, HF Hub downloads, and Biohub Platform API calls all
work without extra flags. To run air-gapped, pre-download:

```bash
# On a networked host:
HF_HOME=/some/cache apptainer exec --nv "$SINGULARITY_HOME"/esm.sif \
  python -c "from huggingface_hub import snapshot_download; snapshot_download('Biohub/ESMC-600M')"
# Then ship /some/cache to the offline host and set HF_HUB_OFFLINE=1 there.
```

## Bind-mounts

Apptainer auto-mounts `$HOME` and `$PWD`. Anything else needs an explicit
bind:

```bash
apptainer exec --nv \
  --bind /data/proteins:/data/proteins \
  --bind /scratch/$USER/hf:/hf_cache \
  --env HF_HOME=/hf_cache \
  "$SINGULARITY_HOME"/esm.sif python script.py
```

Common patterns:

| Bind | Why |
|------|-----|
| `--bind /scratch/$USER/hf:$HOME/.cache/huggingface` | Move HF cache to fast scratch (recommended on shared clusters) |
| `--bind /scratch/$USER/torch:$HOME/.cache/torch` | Move Torch cache (mostly for `torch.hub` weights) |
| `--bind /data:/data` | Project data dir |
| `--bind /tmp:/tmp` | Override apptainer's default tmpfs |

## Hugging Face cache & gated weights

ESM model weights are downloaded **at first use** from HF Hub into
`$HF_HOME`. The SIF defaults `HF_HOME=${HF_HOME:-$HOME/.cache/huggingface}`
in its `%environment` block, which resolves to the calling user's home
directory — and **apptainer auto-mounts `$HOME`**, so by default the
container reuses the host's HF cache without any extra flags.

### The default (zero-config) — host `$HOME/.cache/huggingface`

Because apptainer auto-mounts `$HOME` into the container, `$HF_HOME`
resolves to **the same directory inside and outside** the image. Anything
the host already cached at `~/.cache/huggingface` is visible inside; any
download that happens inside the container persists on the host.

```bash
# Host:
ls ~/.cache/huggingface           # ← whatever you already downloaded
huggingface-cli login             # writes token to ~/.cache/huggingface/token
# Container — the same cache, no binds needed:
apptainer exec --nv "$SINGULARITY_HOME"/esm.sif \
  python -c "from huggingface_hub import HfApi; print(HfApi().whoami())"
```

So in the common case, **you don't have to do anything** — the home-dir
HF cache is shared automatically. The recipes below are for when you want
the cache somewhere *other* than `$HOME`.

### When the home dir isn't writable / big enough — explicit bind

On many clusters home is on a small / slow NFS volume. Move the cache to
fast scratch and bind it back to the container path you want HF to use:

```bash
# Pick a writable, big-enough host path:
HFCACHE=/scratch/$USER/huggingface
mkdir -p "$HFCACHE"

# Bind it to ~/.cache/huggingface (the SIF's default $HF_HOME) — nothing else changes:
apptainer exec --nv \
  --bind "$HFCACHE":"$HOME/.cache/huggingface" \
  "$SINGULARITY_HOME"/esm.sif \
  python script.py
```

Or rewrite `$HF_HOME` directly inside the container and bind to a custom
path — equivalent, sometimes more readable:

```bash
apptainer exec --nv \
  --bind "$HFCACHE":/hf_cache \
  --env HF_HOME=/hf_cache \
  "$SINGULARITY_HOME"/esm.sif \
  python script.py
```

Either way the model is fetched **once**; subsequent runs (on the same
host, by the same user) hit the cache instantly.

### Shared cache across a team / cluster

If many users on the cluster share a common HF cache (read-only is fine —
HF re-uses existing blobs and only writes new ones to a writable layer):

```bash
# /shared/hf_cache is populated once by an admin / the first user.
# In each user's shell rc:
export HF_HOME=/shared/hf_cache

apptainer exec --nv \
  --bind /shared/hf_cache:/shared/hf_cache \
  --env HF_HOME=/shared/hf_cache \
  "$SINGULARITY_HOME"/esm.sif python script.py
```

For pure write-through caching to scratch with read-through from shared:

```bash
# Two binds, two HF env vars (HF_HUB_CACHE + HF_HOME) so writes go to scratch:
apptainer exec --nv \
  --bind /shared/hf_cache:/shared/hf_cache:ro \
  --bind /scratch/$USER/hf:/scratch_hf \
  --env HF_HOME=/scratch_hf \
  --env HF_HUB_CACHE=/scratch_hf \
  "$SINGULARITY_HOME"/esm.sif \
  python -c "from huggingface_hub import snapshot_download; snapshot_download('Biohub/ESMC-600M', cache_dir='/scratch_hf')"
```

### Same idea for Torch cache

The SIF also defaults `TORCH_HOME=${TORCH_HOME:-$HOME/.cache/torch}`.
Apptainer's auto-mount of `$HOME` makes that share with the host
automatically; bind explicitly if it lives elsewhere:

```bash
apptainer exec --nv \
  --bind /scratch/$USER/torch:$HOME/.cache/torch \
  "$SINGULARITY_HOME"/esm.sif python script.py
```

### Pre-warming the cache (download once, run many)

A nice pattern for clusters / Slurm: prefetch every model you'll touch
into the cache before any job runs, so all subsequent jobs hit the cache
and never block on network:

```bash
apptainer exec --nv "$SINGULARITY_HOME"/esm.sif python - <<'PY'
from huggingface_hub import snapshot_download
for repo in [
    "Biohub/ESMC-300M",
    "Biohub/ESMC-600M",
    "Biohub/ESMC-6B",                                  # gated → log in first
    "Biohub/ESMFold2",
    "Biohub/ESMC-6B-sae-k64-codebook16384",
]:
    snapshot_download(repo)
PY
```

After this, the host's `~/.cache/huggingface` (or wherever you bound
`$HF_HOME`) holds every weight; from then on **no run downloads
anything**.

If you don't want to re-download 12 GB of ESMC-6B per node, point all
nodes' `$HF_HOME` at shared storage:

```bash
export HF_HOME=/shared/hf_cache       # in the user's shell rc
apptainer exec --nv "$SINGULARITY_HOME"/esm.sif python ...
```

### Gated models (ESMC-6B, possibly ESMFold2)

1. On the host: `huggingface-cli login` (or `export HF_TOKEN=hf_…`).
2. Accept the model card terms in your browser.
3. The token is written to `$HF_HOME/token` — apptainer reads it from the
   bind-mounted `$HOME` automatically.

To inject a token without an interactive login:

```bash
apptainer exec --nv --env HF_TOKEN="$HF_TOKEN" "$SINGULARITY_HOME"/esm.sif \
  python -c "from huggingface_hub import HfApi; print(HfApi().whoami())"
```

## CUDA driver requirements

The container's CUDA libs are 12.6, but `--nv` provides the **host's**
driver libraries — the driver must support CUDA 12.6 (NVIDIA driver
≥ 525.60.x for CUDA 12.x; safest is ≥ 560.x for CUDA 12.6 features).

Check: `nvidia-smi` on the host. If it reports a driver too old for CUDA
12.6 you'll see runtime errors like `CUDA error: no kernel image is
available for execution on the device` — upgrade the host driver, or
rebuild the SIF against a CUDA-12.4 base by editing the `From:` line.

## Caches that matter at runtime

| Env var | Default in SIF | Purpose |
|---------|----------------|---------|
| `HF_HOME` | `$HOME/.cache/huggingface` | Hugging Face model downloads |
| `TORCH_HOME` | `$HOME/.cache/torch` | `torch.hub` weights (rarely used by esm itself) |
| `ESM_API_KEY` | unset | Biohub Platform API token (read by SDK if no `token=` is passed) |
| `PYTHONDONTWRITEBYTECODE=1` | hard-coded | No `.pyc` clutter |
| `PYTHONUNBUFFERED=1` | hard-coded | Live stdout — useful in batch logs |
| `LC_ALL` / `LANG` | `C.UTF-8` | Avoids locale errors in some downstreams |

Pass extras with `--env KEY=VAL` on the `apptainer` line.

## Docker (alternative to apptainer)

The repo also ships `Dockerfile` (and `Dockerfile.vastai` for vast.ai
GPU-rental boxes). Build and run:

```bash
docker build -t esm-biohub:latest ~/Repos/esm_biohub
docker run --rm --gpus all -it esm-biohub:latest
```

The Dockerfile bakes the same environment into `/opt/venv` and sets
`WORKDIR /opt/esm`. Use for local dev when you don't need to push to a
cluster.

The `Dockerfile.vastai` flavor adds vast.ai-specific niceties (jupyter,
extra ports). Not generally needed otherwise.

## Conda fallback

If you can't use a container at all:

```bash
conda create -n esm python=3.12 -y
conda activate esm
pip install --index-url https://download.pytorch.org/whl/cu126 torch torchvision torchaudio
cd ~/Repos/esm_biohub
pip install .
python -c "import esm; print(esm.__version__)"
```

You will be responsible for matching CUDA toolkit and driver yourself, and
for getting flash-attn to build if you want it (`pip install flash-attn
--no-build-isolation` is the usual recipe; needs a working `nvcc` matching
the wheels).

## Pixi (the upstream project's tool)

`pyproject.toml` is also a [pixi](https://pixi.sh) workspace; `pixi.lock`
is in the repo. If you have pixi:

```bash
cd ~/Repos/esm_biohub
pixi install         # creates .pixi/envs/default
pixi run python -c "import esm; print(esm.__version__)"
pixi run -e dev cov-test   # the dev test suite
```

Pixi's `dev` feature adds matplotlib, pyright, pytest, pre-commit. Useful if
you intend to **develop** `esm` itself; for inference just use the SIF.

## Verifying a build

```bash
apptainer inspect "$SINGULARITY_HOME"/esm.sif       # labels + help
apptainer test --nv "$SINGULARITY_HOME"/esm.sif     # runs %test (import smoke check)
apptainer exec --nv "$SINGULARITY_HOME"/esm.sif \
  python -c "import esm, torch; print('esm', esm.__version__, 'torch', torch.__version__, 'cuda', torch.cuda.is_available())"
```

A healthy run prints something like:

```
esm 3.3.0 torch 2.7.x+cu126 cuda True
```
