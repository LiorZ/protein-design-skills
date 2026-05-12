# Installation

ProtFlow is the orchestrator; it does **not** install the underlying tools
(RFdiffusion, ESMFold, AlphaFold3, Boltz, …). You install each tool into its
own conda/mamba environment and point ProtFlow at the per-tool Python binary
and entry-script via `config.py`.

## 1) Install ProtFlow itself

```bash
git clone https://github.com/mabr3112/ProtFlow.git
cd ProtFlow

conda create -n protflow python=3.11 -y     # 3.11+ required
conda activate protflow

pip install -e .
```

The package is under active development; install editable so you can `git pull`
and pick up fixes without re-running `pip install`.

## 2) Initialise `config.py`

```bash
protflow-init-config                                # writes ~/.config/protflow/config.py
protflow-init-config --dest /shared/protflow/config.py  # custom destination
```

This copies `protflow/config_template.py` to the destination. Edit it to point
at your installed tools.

If you keep a shared cluster-wide config:

```bash
protflow-set-config /shared/protflow/config.py      # pin a config for future runs
protflow-check-config                                # which file is currently in use?
protflow-set-config --unset                          # revert to default search path
```

Search order resolved by `_try_load_config_module`:

1. Pointer saved by `protflow-set-config` (in `$XDG_CONFIG_HOME/protflow/config.path`)
2. `$PROTFLOW_CONFIG` environment variable
3. `$XDG_CONFIG_HOME/protflow/config.py` (default `~/.config/protflow/config.py`)
4. The bundled `protflow/config.py` (only if you copied a real one into the package)

## 3) Install the tools you actually need

Each tool has its own install recipe. ProtFlow only needs to know:

- the path to the tool's `run_*.py` (or executable), and
- the path to the **Python binary inside the tool's conda env**, and
- (optional) a `*_PRE_CMD` that runs in the same shell before the tool, e.g.
  to load modules or activate environments that don't ship clean shebangs.

For example, after installing LigandMPNN into a conda env called `ligandmpnn_env`:

```python
# in your config.py
LIGANDMPNN_SCRIPT_PATH = "/home/me/LigandMPNN/run.py"
LIGANDMPNN_PYTHON_PATH = "/home/me/miniconda3/envs/ligandmpnn_env/bin/python"
LIGANDMPNN_PRE_CMD     = ""   # or e.g. "module load cuda/12.1"
```

You only need to set keys for tools you actually invoke; ProtFlow lazily reads
config on first `Runner.__init__`. Trying to instantiate a runner whose keys
aren't set raises `ProtFlowConfigError` or `MissingConfigSettingError` with a
message pointing you at the right key.

## 4) Verify

```python
import protflow
from protflow.poses import Poses
from protflow.jobstarters import LocalJobStarter

poses = Poses(work_dir="./protflow_smoketest", jobstarter=LocalJobStarter())
print("OK:", poses)
```

If this prints without error, the package and config loading work. To test a
specific tool, instantiate its Runner — that triggers config path resolution
for *that* tool only.

## Common installation issues

- **`MissingConfigError` on import-time** of any runner: no resolvable
  `config.py`. Run `protflow-init-config`.
- **`FileNotFoundError: Path set for X does not exist`** during runner
  construction: a `*_PATH` in config.py points somewhere wrong. Fix the
  path; `protflow-check-config` tells you which file you're editing.
- **`bash: protflow-init-config: command not found`**: the `protflow` package
  isn't on PATH. Make sure the env is activated (`conda activate protflow`)
  and that `pip install -e .` succeeded — the entry points are declared in
  `pyproject.toml` and exposed by pip.
- **Tool import errors at runtime, not at runner-construction time**: ProtFlow
  shells out to a *different* Python (the one in `*_PYTHON_PATH`); errors
  inside that Python show up in the stderr that ProtFlow tails into the
  exception. Read the appended log block.
