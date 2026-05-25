# Installation — running Protenix from an Apptainer/Singularity SIF

Protenix's runtime is heavy and version-pinned: PyTorch 2.7.1 on CUDA 12.6,
DeepSpeed, NVIDIA cuEquivariance, and custom CUDA kernels (layer-norm +
DS4Sci_EvoformerAttention) that are **JIT-compiled at first use** — so the image
must ship `nvcc` (it bootstraps from a PyTorch *devel* base). Packaging it into a
SIF makes it portable and reproducible on clusters where Docker isn't available.

The Protenix repo at `~/Repos/Protenix` already contains a complete Apptainer
setup under `apptainer/`:

```
apptainer/
├── protenix.def          # image definition (bootstraps pytorch:2.7.1-cuda12.6 devel)
├── build.sh              # stage source + build protenix.sif (--fakeroot)
├── download_weights.sh   # fetch checkpoints + caches into PROTENIX_ROOT_DIR
├── run_protenix.sh       # launch wrapper: --nv + bind-mount weights
└── protenix.sif          # the built image (created by build.sh; git-ignored)
```

> `apptainer` and `singularity` are interchangeable on the command line —
> substitute whichever your site provides.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Apptainer ≥ 1.1 (or SingularityCE ≥ 3.8) | `apptainer --version` |
| Build privileges | `--fakeroot` (rootless, used by `build.sh`) **or** `sudo` |
| Network during build | Docker Hub base pull + pip install of `requirements.txt` + CUTLASS clone (several GB; 20-40 min) |
| NVIDIA driver on the **host** | Exposed at runtime with `--nv`. No CUDA toolkit needed on the host; the image carries CUDA 12.6 userspace. Host driver must support CUDA 12.6 (driver ≥ 555). Check `nvidia-smi`. |
| Disk | ~7.5 GB SIF + ~7.5 GB host weights + JIT kernel cache |

## Build the image

From the repo root:

```bash
cd ~/Repos/Protenix
bash apptainer/build.sh                 # -> apptainer/protenix.sif
# or choose an output path:
bash apptainer/build.sh /path/to/protenix.sif
```

What `build.sh` does:

1. `rsync` a clean copy of the working tree into `/tmp/protenix_build_src`,
   excluding `.git`, `__pycache__`, `*.egg-info`, `output/`, `test_outputs/`,
   `release_data/`, and `apptainer/*.sif`.
2. `apptainer build --fakeroot --force` the `.sif` from `apptainer/protenix.def`.

The `%files` section bakes that staged tree into the image at `/opt/protenix`,
then `%post` installs `requirements.txt`, clones CUTLASS to `/opt/cutlass`
(`CUTLASS_PATH`), and `pip install -e .` so the `protenix` console script and the
`examples/` are available inside the image.

### Build caches

The build cache and scratch can be large. `build.sh` keeps them off the
(often small) default locations:

```bash
export APPTAINER_CACHEDIR=$HOME/.apptainer/cache   # default in build.sh
export APPTAINER_TMPDIR=/tmp/apptainer-build       # default in build.sh
```

Override these to point at a big filesystem if `$HOME`/`/tmp` are tight.

### Building without fakeroot (HPC)

If `--fakeroot` isn't configured for your user, either build with `sudo` on a
machine you control, or build on a workstation and `scp` the single-file `.sif`
to the cluster. SIFs are portable. (The build needs to bake in the repo source,
so on a login node without root/fakeroot, build elsewhere and copy.)

## Model weights (host-side, bind-mounted)

Weights are **not** baked into the image. Protenix resolves all weights/caches
from the `PROTENIX_ROOT_DIR` environment variable (see
`configs/configs_inference.py` → `load_checkpoint_dir = $PROTENIX_ROOT_DIR/checkpoint`,
and `configs/configs_data.py` → CCD/cluster/release caches under
`$PROTENIX_ROOT_DIR/common`). Default when unset is `$HOME`.

Expected layout:

```
$PROTENIX_ROOT_DIR/                     # e.g. /shared/ModelWeights/Protenix
├── checkpoint/
│   ├── protenix_base_default_v1.0.0.pt
│   ├── protenix_base_20250630_v1.0.0.pt
│   ├── protenix_base_default_v0.5.0.pt
│   ├── protenix_base_constraint_v0.5.0.pt
│   ├── protenix_mini_default_v0.5.0.pt
│   └── protenix_tiny_default_v0.5.0.pt
└── common/
    ├── components.cif                  # CCD source (ligand/residue chemistry)
    ├── components.cif.rdkit_mol.pkl
    ├── clusters-by-entity-40.txt
    ├── release_date_cache.json
    ├── obsolete_release_date.csv
    └── obsolete_to_successor.json
```

Download it all once:

```bash
PROTENIX_ROOT_DIR=/shared/ModelWeights/Protenix bash apptainer/download_weights.sh
```

`download_weights.sh` uses `aria2c` (16 connections) when available because the
TOS server throttles single streams to ~40 KB/s; it falls back to `wget -c`.
Anything still missing at run time that Protenix can fetch itself is downloaded
into this (writable, persistent) directory on first use.

> **Not downloaded by default:**
> - **`protenix-v2.pt`** — not served publicly at the TOS endpoint (HTTP 403). Add
>   it back to `download_weights.sh` if/when ByteDance publishes it.
> - **ESM/ISM checkpoints** (`protenix_mini_esm_v0.5.0`, `_ism_`) — need the
>   ~5 GB ESM2-3B weights (`esm2_t36_3B_UR50D*`). Append those entries to
>   `download_weights.sh` to enable them.

## Run

### With the wrapper (recommended)

`run_protenix.sh` adds `--nv` (GPU) and bind-mounts `$PROTENIX_ROOT_DIR`:

```bash
cd ~/Repos/Protenix
apptainer/run_protenix.sh --help

apptainer/run_protenix.sh pred \
    -i examples/input.json -o ./output \
    -n protenix_base_default_v1.0.0 --use_default_params true
```

Environment overrides honored by the wrapper:

```bash
PROTENIX_SIF=/path/to/protenix.sif \
PROTENIX_ROOT_DIR=/data/weights/Protenix \
apptainer/run_protenix.sh pred -i my.json -o out -n protenix_base_default_v1.0.0
```

It errors clearly if the SIF or the weights directory is missing.

### Manual invocation

```bash
apptainer run --nv \
    --bind /shared/ModelWeights/Protenix:/shared/ModelWeights/Protenix \
    --env PROTENIX_ROOT_DIR=/shared/ModelWeights/Protenix \
    apptainer/protenix.sif pred -i examples/input.json -o ./output
```

`%runscript` forwards to the `protenix` CLI, so `apptainer run protenix.sif <args>`
== `protenix <args>`. For a shell or other commands, use `exec`:

```bash
apptainer exec --nv \
    --bind /shared/ModelWeights/Protenix:/shared/ModelWeights/Protenix \
    --env PROTENIX_ROOT_DIR=/shared/ModelWeights/Protenix \
    apptainer/protenix.sif bash
```

### Binds (file access)

Apptainer auto-mounts `$HOME` and the current working directory `$PWD`, so input
JSONs and `-o`/output dirs under them are visible without extra flags. Bind
anything outside explicitly:

```bash
apptainer/run_protenix.sh pred -i /scratch/jobs/run1.json -o /scratch/jobs/out ...
# if /scratch is not under $HOME, add to the manual command:
#   --bind /scratch:/scratch
```

### GPU selection

```bash
CUDA_VISIBLE_DEVICES=0 apptainer/run_protenix.sh pred ...
# or, manual:  --env CUDA_VISIBLE_DEVICES=0
```

### Kernel JIT cache

The first prediction JIT-compiles the layer-norm and (if selected) Evoformer
attention CUDA kernels. The image points the cache at a writable per-user
location:

```
TORCH_EXTENSIONS_DIR=$HOME/.cache/protenix_torch_ext   # default in the image
```

Subsequent runs reuse it. Override with `--env TORCH_EXTENSIONS_DIR=...` if
`$HOME` is read-only on compute nodes (point it at node-local scratch).

> **cwd shadows the baked-in source.** The Protenix package is installed
> editable from `/opt/protenix`, but Apptainer mounts `$PWD`. If you launch from
> *inside* a Protenix checkout, Python imports `protenix` from that checkout
> instead of the image copy, and JIT artifacts land in your working tree. It's
> harmless (same code) but messy. **Run from a data directory**, not a checkout,
> to use the baked-in copy + the `$TORCH_EXTENSIONS_DIR` cache.

## Alternatives to the SIF

These are documented upstream; the SIF is preferred on shared HPC.

- **pip** (`docs/kernels.md`): `pip install --upgrade protenix --index-url
  https://pypi.org/simple`, then set `CUTLASS_PATH` to a CUTLASS v3.5.1 checkout
  if you use the DeepSpeed Evoformer kernel. Needs a matching CUDA/torch stack.
- **Docker** (`docs/docker_installation.md`): pull
  `ai4s-share-public-cn-beijing.cr.volces.com/release/protenix:1.0.0.4`, mount
  the repo at `/app`, `pip install -e .`, run with `--gpus all`. The Apptainer
  `protenix.def` mirrors this image but bakes in the source.
</content>
