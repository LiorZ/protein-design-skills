# config.py — Every Key

`config.py` is plain Python; ProtFlow imports it as a module and reads string
constants from it via `protflow.load_config_path(config, "KEY_NAME")`.

The template lives at `protflow/config_template.py`. `protflow-init-config`
copies it to your config destination.

## Core (always needed)

| Key                              | Points to                                                                 | Notes |
|----------------------------------|---------------------------------------------------------------------------|-------|
| `PROTFLOW_DIR`                   | The cloned ProtFlow repo root                                              | Used by auxiliary scripts. |
| `PROTFLOW_ENV`                   | The python binary in your protflow env                                     | `/path/to/envs/protflow/bin/python3` |
| `AUXILIARY_RUNNER_SCRIPTS_DIR`   | `protflow/protflow/tools/runners_auxiliary_scripts/`                       | ProtFlow ships helper scripts there (e.g. `run_esm.py`); some runners import this dir. |

## Per-tool keys

Every entry has three flavours: a script path (or binary), a python path, and a
pre-command. **You only need to fill in keys for the tools you actually run.**
ProtFlow reads them lazily on first runner construction.

### Backbone generation

| Tool          | Script / bin                          | Python                              | Pre-cmd                                  |
|---------------|----------------------------------------|-------------------------------------|-------------------------------------------|
| RFdiffusion   | `RFDIFFUSION_SCRIPT_PATH` (`run_inference.py`) | `RFDIFFUSION_PYTHON_PATH`     | `RFDIFFUSION_PRE_CMD`                     |
| RFdiffusion3  | `RFDIFFUSION3_BIN_PATH` (`rfd3` cli) **plus** `RFDIFFUSION3_SCRIPT_PATH` (legacy alias) | `RFDIFFUSION3_PYTHON_PATH` | `RFDIFFUSION3_PRE_CMD`; also `RFDIFFUSION3_MODEL_DIR` for checkpoints |
| protein-generator | `PROTEIN_GENERATOR_SCRIPT_PATH`    | `PROTEIN_GENERATOR_PYTHON_PATH`     | —                                          |

### Sequence design

| Tool                  | Script                          | Python                          | Pre-cmd               |
|-----------------------|----------------------------------|---------------------------------|-----------------------|
| LigandMPNN / MPNN / SolubleMPNN / Membrane MPNN | `LIGANDMPNN_SCRIPT_PATH` (`run.py`) | `LIGANDMPNN_PYTHON_PATH` | `LIGANDMPNN_PRE_CMD` |
| Frame2Seq design      | (auxiliary script in ProtFlow)   | `FRAME2SEQ_PYTHON_PATH`         | `FRAME2SEQ_PRE_CMD`   |
| Caliby                | (Caliby paths — see Caliby docstring)                                           |                                  |                       |

### Structure prediction

| Tool          | Script / bin                          | Python                              | Pre-cmd / Extra                              |
|---------------|----------------------------------------|-------------------------------------|-----------------------------------------------|
| ESMFold       | (auxiliary `run_esmfold.py`)           | `ESMFOLD_PYTHON_PATH`               | `ESMFOLD_PRE_CMD`                              |
| ESM2          | (auxiliary `run_esm.py`)               | `ESM_PYTHON_PATH`                   | `ESM_PRE_CMD`                                  |
| ColabFold     | `COLABFOLD_SCRIPT_PATH` (`colabfold_batch`) | (uses script's shebang)        | `COLABFOLD_PRE_CMD`                            |
| AlphaFold3    | `ALPHAFOLD3_SCRIPT_PATH` (`run_alphafold.py`) | `ALPHAFOLD3_PYTHON_PATH`     | `ALPHAFOLD3_PRE_CMD`                           |
| Boltz         | `BOLTZ_PATH` (`boltz` CLI)             | `BOLTZ_PYTHON`                      | `BOLTZ_PRE_CMD`                                |
| Minifold      | `MINIFOLD_SCRIPT_PATH`                 | `MINIFOLD_PYTHON_PATH`              | `MINIFOLD_PRE_CMD`                             |

### Refinement / docking / MD

| Tool          | Key                              | Notes                                        |
|---------------|-----------------------------------|----------------------------------------------|
| Rosetta       | `ROSETTA_BIN_PATH`                | Directory containing `relax.linuxgccrelease`, etc. |
| Rosetta pre-cmd | `ROSETTA_PRE_CMD`                | Used to `source` env modules if needed.       |
| AttnPacker    | `ATTNPACKER_PYTHON_PATH`, `ATTNPACKER_DIR_PATH`, `ATTNPACKER_PRE_CMD` | DIR_PATH is the AttnPacker checkout. |
| PLACER        | `PLACER_SCRIPT_PATH`, `PLACER_PYTHON_PATH`, `PLACER_PRE_CMD` | `run_PLACER.py` script. |
| SigmaDock     | `SIGMADOCK_SCRIPT_PATH`, `SIGMADOCK_PYTHON_PATH`, `SIGMADOCK_CKPT_PATH`, `SIGMADOCK_PRE_CMD` | Checkpoint goes in CKPT_PATH. |
| GROMACS       | `GROMACS_PATH`                    | Directory containing `gmx`. |

### Metrics

| Tool          | Key                              | Notes                          |
|---------------|-----------------------------------|--------------------------------|
| FPocket       | `FPOCKET_PATH`                    | Either the binary or just `fpocket` if it's on PATH (ProtFlow resolves via `which`). |
| DSSP          | `DSSP_PATH`                       | Path to `mkdssp`.              |

## The `*_PRE_CMD` pattern

`*_PRE_CMD` is a shell string prepended to every command this runner generates,
joined by `; `. Use it when:

- The tool's Python doesn't have a clean shebang and you need `conda activate
  some_env` first.
- You need `module load cuda/12.1` (or any environment-module load) before
  invoking the tool.
- You need to export an env var that the tool reads at runtime.

Example:

```python
ESMFOLD_PRE_CMD = "module load cuda/12.1; export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512"
```

Leave empty (`""`) if you don't need it. `load_config_path(..., is_pre_cmd=True)`
returns the raw string even if empty — no file-existence check.

## Sharing a config across users

Two patterns work:

1. **Single shared file**: cluster admin puts `config.py` in
   `/shared/protflow/config.py`. Each user runs
   `protflow-set-config /shared/protflow/config.py` once. The pointer in
   `~/.config/protflow/config.path` persists.

2. **Per-user file with shared defaults**: each user has
   `~/.config/protflow/config.py`. Inside it, `from /shared/protflow/defaults
   import *` and override locally.

## Programmatic access

```python
from protflow import require_config, load_config_path, get_config

cfg = require_config()                          # raises MissingConfigError if no config
path = load_config_path(cfg, "BOLTZ_PATH")     # validates file exists
pre  = load_config_path(cfg, "BOLTZ_PRE_CMD", is_pre_cmd=True)  # raw string, may be ""
```

`get_config()` returns `None` instead of raising. Useful for code that wants
to opt out.
