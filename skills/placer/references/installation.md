# Installation — running PLACER from an Apptainer/Singularity SIF

PLACER's runtime is heavy and version-pinned: CUDA 12.1, PyTorch 2.3.1
(cuda12.1 build), DGL 2.4.0, openbabel 3.1.1, e3nn 0.5.4, plus the NVIDIA
SE3Transformer installed from GitHub. Packaging it into a SIF container makes it
portable and reproducible. The skill ships [`../examples/PLACER.def`](../examples/PLACER.def).

> `apptainer` and `singularity` are interchangeable on the command line —
> substitute whichever your site provides.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Apptainer ≥ 1.1 (or SingularityCE ≥ 3.8) | `apptainer --version` |
| Build privileges | `--fakeroot` (rootless, preferred) **or** `sudo` |
| Network during build | git clone + conda solve + SE3Transformer pip install (several GB) |
| NVIDIA driver on the **host** | Exposed at runtime with `--nv`. No driver/toolkit needed *inside* the image — the conda env brings CUDA 12.1 userspace libs; the kernel driver comes from the host. |
| Disk | ~8-12 GB for the final SIF |

The image does **not** require CUDA to be installed on the host — only the
kernel-mode NVIDIA driver. The host driver must support CUDA 12.1
(driver ≥ 530). Check with `nvidia-smi` on the host.

## Build

Rootless (preferred):

```bash
apptainer build --fakeroot placer.sif ~/.claude/skills/placer/examples/PLACER.def
```

If `--fakeroot` isn't configured for your user:

```bash
sudo apptainer build placer.sif ~/.claude/skills/placer/examples/PLACER.def
```

On an HPC login node without root or fakeroot, build the SIF on a machine where
you do have them (or in `--remote` mode if your site runs a build service), then
`scp` the `.sif` to the cluster. SIFs are single-file and portable.

To pin a specific PLACER commit/tag or use the exact env, edit the three
variables at the top of the `%post` block in `PLACER.def`:

```sh
PLACER_REPO=https://github.com/baker-laboratory/PLACER.git
PLACER_REF=main
ENV_FILE=envs/placer_env_lite.yml   # or envs/placer_env.yml for exact pins
```

`envs/placer_env_lite.yml` (the default) is loosely pinned and solves faster/
more robustly. `envs/placer_env.yml` is the exact, fully-pinned environment —
use it if you need bit-for-bit reproducibility and the lite solve drifts.

(The def file uses plain shell variables rather than Apptainer `{{ }}` build-arg
templating, so it builds on older Apptainer/Singularity too.)

## What the build does

1. Bootstraps from `condaforge/miniforge3` (provides `mamba`).
2. `git clone` PLACER into `/opt/PLACER` — this **includes the model weights**
   (`/opt/PLACER/weights/PLACER_model_1.pt`), so the SIF is self-contained.
3. `mamba env create -p /opt/conda/envs/placer -f .../placer_env_lite.yml`.
4. Imports torch/dgl/e3nn/openbabel/se3_transformer to fail fast on a bad build.
5. Sets `%environment` so `python` is the PLACER interpreter and exports
   `PLACER_DIR` and `PLACER_WEIGHTS`.

## Run

GPU (the normal case):

```bash
apptainer exec --nv placer.sif \
  python /opt/PLACER/run_PLACER.py \
    --ifile input.cif --odir out -n 50 --rerank prmsd \
    --weights /opt/PLACER/weights/PLACER_model_1.pt
```

`apptainer run placer.sif <args>` also works (the `%runscript` forwards to
`run_PLACER.py`), but `apptainer exec ... python /opt/PLACER/run_PLACER.py` is
explicit and is what the examples use.

### The `--weights` gotcha (important)

`run_PLACER.py` defaults `--weights` to `weights/PLACER_model_1.pt`, resolved
relative to the **current working directory** (not the script location). When
you run from an arbitrary host directory, that relative path doesn't exist, and
the run fails to load the model. Always either:

- pass `--weights /opt/PLACER/weights/PLACER_model_1.pt` (exported as
  `$PLACER_WEIGHTS` inside the image), **or**
- add `--pwd /opt/PLACER` to the `apptainer exec` command so cwd is the repo
  root (note: this changes where relative `--ifile`/`--odir` resolve too).

### Binds (file access)

Apptainer auto-mounts `$HOME` and the current working directory `$PWD`. Inputs
and `--odir` under those are visible with relative paths. For anything else,
bind it:

```bash
apptainer exec --nv \
  --bind /scratch/data:/scratch/data \
  placer.sif \
  python /opt/PLACER/run_PLACER.py \
    --ifile /scratch/data/complex.cif --odir /scratch/data/out -n 100 \
    --weights $PLACER_WEIGHTS
```

`$PLACER_WEIGHTS` expands inside the container shell created by `apptainer
exec`; if you're constructing the command from the host shell and the var isn't
set there, write the literal path.

### GPU selection

Restrict to one GPU with the host env var, passed through by apptainer:

```bash
APPTAINERENV_CUDA_VISIBLE_DEVICES=0 apptainer exec --nv placer.sif ...
# (SingularityCE: SINGULARITYENV_CUDA_VISIBLE_DEVICES=0)
```

### CPU-only

Omit `--nv`. PLACER falls back to CPU: ~7 min/model on 1 core, ~1 min/model on
8 cores. Fine for a handful of samples; impractical for large ensembles.

## Bind a host checkout instead of the baked-in source

To iterate on PLACER code/weights without rebuilding, bind a host clone over
`/opt/PLACER` (the conda env in the image still provides all dependencies):

```bash
git clone https://github.com/baker-laboratory/PLACER.git ~/Repos/PLACER
apptainer exec --nv \
  --bind ~/Repos/PLACER:/opt/PLACER \
  placer.sif \
  python /opt/PLACER/run_PLACER.py --ifile input.cif --odir out -n 50 \
    --weights /opt/PLACER/weights/PLACER_model_1.pt
```

## Docker / Podman alternative

The same recipe converts to a Dockerfile trivially (miniforge base, clone,
`mamba env create`, `ENV PATH=...`). Run with `--gpus all`. The SIF route is
documented here because it's the friendlier option on shared HPC where users
can't run a Docker daemon.

## Conda fallback (no container)

If you can't or don't want to containerize, the upstream conda env works
directly (this is what `protflow` expects via `PLACER_PYTHON_PATH`):

```bash
git clone https://github.com/baker-laboratory/PLACER.git
cd PLACER
conda env create -f envs/placer_env_lite.yml   # or placer_env.yml for exact pins
conda activate placer_env
python run_PLACER.py --ifile examples/inputs/4dtz.cif --odir out -n 10 \
  --predict_ligand D-LDP-501 --rerank prmsd
# (run from the repo root so the default --weights path resolves)
```

A Mac (Apple Silicon / MPS) env is also provided upstream:
`envs/placer_env_mac.yml`.
