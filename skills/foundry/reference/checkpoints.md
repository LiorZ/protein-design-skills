# Checkpoint management

## How discovery works

`foundry.inference_engines.checkpoint_registry` is the single source of truth.

- `REGISTERED_CHECKPOINTS: dict[str, RegisteredCheckpoint]` — name → metadata (url, filename, description, optional sha256).
- `get_default_checkpoint_dirs()` — returns the ordered search path:
  1. Every entry of `FOUNDRY_CHECKPOINT_DIRS` (colon-separated; falls back to `FOUNDRY_CHECKPOINTS_DIR` if unset).
  2. `~/.foundry/checkpoints` (always appended last).
- `RegisteredCheckpoint.get_default_path()` — walks the search path looking for the registered `filename`, returns the first hit (or the primary-dir path if nothing exists, so downloads can target it).

So the contract for an MPNN-style model is: **register a `filename`, then make sure that filename is reachable in one of the search dirs**. Nothing else looks at paths.

## The `foundry` CLI (`src/foundry_cli/download_checkpoints.py`)

Typer app with four subcommands:

| Command | What it does |
|---------|--------------|
| `foundry install <name>...` | Downloads each registered model. `all` ⇒ everything; `base-models` ⇒ rfd3, rf3, proteinmpnn, ligandmpnn. `--checkpoint-dir/-d` overrides target dir and persists it into `.env` as `FOUNDRY_CHECKPOINT_DIRS` if `.env` exists. `--force/-f` overwrites. |
| `foundry list-available` | Prints names + descriptions from `REGISTERED_CHECKPOINTS`. |
| `foundry list-installed` | Walks all checkpoint dirs, prints `*.ckpt` and `*.pt` files with sizes. |
| `foundry clean` | Deletes all `*.ckpt`/`*.pt` under all checkpoint dirs (interactive confirm by default). |

Empty `url=""` entries (proprietary models) are skipped silently by `install`. They must be placed manually in a directory reachable through `FOUNDRY_CHECKPOINT_DIRS`.

## Adding a *publicly downloadable* checkpoint

Just append to `REGISTERED_CHECKPOINTS` with `url` filled in:

```python
"my_public_model": RegisteredCheckpoint(
    url="https://example.com/path/to/weights.pt",
    filename="my_public_model_weights.pt",
    description="My new public MPNN variant",
    sha256="abc123...",   # optional but recommended
),
```

Then `foundry install my_public_model` will download it to `~/.foundry/checkpoints/my_public_model_weights.pt`. SHA-256 is verified after download if provided.

## Adding a *local-only/proprietary* checkpoint

Same registry entry with `url=""` (and no `sha256`):

```python
"my_internal_model": RegisteredCheckpoint(
    url="",
    filename="my_internal_model.pt",
    description="Proprietary internal model",
),
```

Users place the file somewhere on disk and either:

- copy it to `~/.foundry/checkpoints/my_internal_model.pt`, **or**
- `export FOUNDRY_CHECKPOINT_DIRS="/path/to/that/dir:..."` before invoking the model.

## Inspecting the current path

```bash
python - <<'PY'
from foundry.inference_engines.checkpoint_registry import get_default_checkpoint_dirs
for d in get_default_checkpoint_dirs():
    print(d, d.exists())
PY
```

## Common failure modes

| Symptom | Likely cause |
|---------|--------------|
| `foundry install <name>` fails with empty URL | Proprietary model — place file manually. |
| `--list_models` shows `✗ (not installed)` | Registry entry exists but file isn't in any search dir; check `FOUNDRY_CHECKPOINT_DIRS`. |
| Engine `__init__` raises `FileNotFoundError: checkpoint_path does not exist` | `get_default_path()` fell back to the primary dir but file isn't there; same fix. |
| Hash mismatch error | Mid-download corruption — file is deleted automatically; re-run `foundry install`. |
| `.env` not updated when running `foundry install -d` | The repo has no `.env`; `append_checkpoint_to_env` returns `False` silently. Create one (`touch .env`) if you want persistence. |
