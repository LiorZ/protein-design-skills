# Setup — Install Environment, Pretrained Weights, and Data

This page documents `scripts/setup/setup.sh` and `scripts/setup/download.sh`
in detail so you can reason about failures and customize the install.

## One-shot install

```bash
git clone https://github.com/aqlaboratory/genie3.git
cd genie3
bash scripts/setup/setup.sh             # ~30–60 min, downloads weights for ColabFold etc.
bash scripts/setup/download.sh          # downloads pretrained Genie 3 weights + training data
conda activate genie3
genie3 --help
```

## What `scripts/setup/setup.sh` installs

It runs sequentially (each step is logged to `logs/setup/<TIMESTAMP>.log` unless `--verbose`):

| Step | What | Notes |
|------|------|-------|
| `ensure_conda_env` | Creates `genie3` conda env (Python 3.10) | Skips if already exists. Activates and installs `pip git`. |
| `configure_package_cache` | Sets `GENIE3_CACHE_ROOT`, `PIP_CACHE_DIR`, `TMPDIR`, `XDG_CACHE_HOME`, `GENIE3_COLABFOLD_DATA_DIR` | Defaults to `<repo>/packages/.cache` but respects `PSCRATCH`/`SCRATCH`/`TMPDIR` if set. |
| `install_genie3` | `pip install -e .` (editable) | Bootstraps `setuptools wheel numpy>=2.0.2 Cython` first. |
| `install_esmfold` | GCC 13 toolchain + `omegaconf dm-tree modelcif dllogger openfold esm deepspeed` | Registers `esmfold_env.sh` activation script that exports `LD_LIBRARY_PATH`/`CC`/`CXX`. |
| `install_colabfold` | `kalign2 hhsuite mmseqs2 openmm`, `colabfold[alphafold]`, `jax[cuda12_pip]`, then downloads AF2-multimer-v3 weights | Registers `colabfold_env.sh` exporting `XDG_CACHE_HOME` and `GENIE3_COLABFOLD_DATA_DIR`. |
| `install_foldseek` | `conda install -c conda-forge -c bioconda foldseek` | Used for clustering successful designs. |
| `install_ipsae` | Clones `DunbrackLab/IPSAE` into `packages/IPSAE` | Used by the binder reducer for ipsae scoring. |
| `install_proteinmpnn` | Clones `dauparas/ProteinMPNN` into `packages/ProteinMPNN` | Default inverse-folding model. |
| `install_tmscore` | Builds `TMscore` and `TMalign` into `packages/TMscore` | g++ build from zhanggroup.org sources. |
| `install_dssp` | Downloads `mkdssp` helper into `packages/dssp-2.3.0` | From BindCraft repo. |

Flags:
- `-v / --verbose` — print installer output to terminal instead of log file.
- `-h / --help` — usage.

### Cache root

The install puts heavy caches under `$GENIE3_CACHE_ROOT` to keep the repo light. Order of precedence for the cache root:

1. `GENIE3_CACHE_ROOT` env var (explicit)
2. `PSCRATCH` (NERSC)
3. `SCRATCH` (slurm)
4. `TMPDIR`
5. `<repo>/packages/.cache` (fallback)

ColabFold AF2-multimer-v3 weights live at `$XDG_CACHE_HOME/colabfold` (~6 GB). Before running on a different node, ensure the same `XDG_CACHE_HOME` is reachable — the `colabfold_env.sh` activation script will set it.

### Activation scripts

Two files are written into `$CONDA_PREFIX/etc/conda/activate.d/`:

- `colabfold_env.sh` — exports `XDG_CACHE_HOME`, `GENIE3_COLABFOLD_DATA_DIR`
- `esmfold_env.sh` — exports `LIBRARY_PATH`, `LD_LIBRARY_PATH`, `CC`, `CXX` to the env's GCC toolchain

These ensure subsequent `conda activate genie3` shells inherit the right paths automatically. If you need to relocate caches, delete these scripts and re-run `setup.sh`.

## What `scripts/setup/download.sh` fetches

Pulls from HuggingFace `yeqinglin/genie3` via `hf download`:

| Flag | Pattern | Lands at |
|------|---------|----------|
| `--weights` (default with no flags or with `--data`) | `pretrained/**` | `<repo>/pretrained/` |
| `--data` (default with no flags or with `--weights`) | `data/train/**` | `<repo>/data/train/` |
| (no flag) | both | both |

Pretrained checkpoint default path used by the loader:
- `pretrained/v1/checkpoints/step=600000.ckpt`
- `pretrained/v1/config.yaml`

These are set by `_parse_generation` in `src/genie3/config/loader.py`. Override per-experiment via `generation.base.checkpoint` / `generation.base.config`.

Training data manifests after download:

| Dataset | Path |
|---------|------|
| AlphaFold DB representatives (L≤512, pLDDT≥70) | `data/train/afdbreps_l-512_plddt-70/info.csv` |
| PiNDER (2024-02) | `data/train/pinder/2024-02/info.csv` |

## Verifying the install

```bash
conda activate genie3

# Show CLI is on PATH and registered
which genie3
genie3 --help

# Confirm pretrained checkpoint is present
ls pretrained/v1/checkpoints/step=600000.ckpt
ls pretrained/v1/config.yaml

# Smoke test: tiny unconditional run on 1 GPU (~minutes)
genie3 run -c examples/unconditional/experiment.yaml
```

The shipped `examples/unconditional/experiment.yaml` requests 5 samples at length 50 — the smallest meaningful workload for verifying the full pipeline (generate → ESMFold → metrics → reduce).

## Sample data layouts (after install + downloads)

```
genie3/
  pretrained/
    v1/
      checkpoints/step=600000.ckpt
      config.yaml
  data/
    design/
      binder_design/binderbench/        # example binder problem set (in repo)
      motif_scaffolding/motifbench/     # example single-motif problem set
      motif_scaffolding/rsvf/           # example multi-motif problem set
    train/                              # downloaded by --data
      afdbreps_l-512_plddt-70/info.csv
      pinder/2024-02/info.csv
  packages/                             # gitignored, ~10–20 GB
    .cache/                             # if no SCRATCH/TMPDIR
    IPSAE/  ProteinMPNN/  TMscore/  dssp-2.3.0/
```

## Common install failures

- **`huggingface-cli not found`** when running `download.sh` → activate the env first (`conda activate genie3`); `huggingface_hub` is installed as part of the `genie3` package.
- **GCC errors in ESMFold step** → `setup.sh` installs GCC 13 from conda-forge into the env. If you see `cc1plus: error: bad value for -mtune`, your shell is using a system GCC; deactivate/reactivate the env so the activation script's `CC`/`CXX` exports take effect.
- **ColabFold weight download stalls** → re-run `setup.sh`; the download is resumable via the colabfold helper, but you may need to delete a partial file in `$GENIE3_COLABFOLD_DATA_DIR/params/`.
- **`genie3 executable not found on PATH`** when running `genie3 run` → the `run` subcommand spawns child processes via `subprocess.run([shutil.which("genie3"), ...])`. You must be in the `genie3` env, not an outer shell.
- **CUDA OOM at startup** → another process is holding GPU memory; check `nvidia-smi`. Genie 3 uses `torch.cuda.empty_cache()` between stages but not between Python processes.
