---
name: foundry
description: Use and extend the Foundry toolkit (RFdiffusion3, RosettaFold3, ProteinMPNN/LigandMPNN/SolubleMPNN/EnhancedMPNN/ThermalMPNN). Covers CLI/Python APIs, checkpoint management, common design workflows, and — most importantly — how to extend the toolkit (registering new MPNN checkpoints, adding new MPNN architectures, plugging new inference engines into the Hydra configs). Trigger when a user mentions foundry, rf3, rfd3, mpnn (any variant), enhancedmpnn, thermalmpnn, the `foundry` CLI, FOUNDRY_CHECKPOINT_DIRS, or asks to add/register a new MPNN model/checkpoint.
---

# Foundry — usage & extension skill

This repo (`rc-foundry`) bundles three model families under a shared infrastructure layer:

| Family | Purpose | CLI | Engine class |
|--------|---------|-----|--------------|
| **RFD3** (`models/rfd3`) | De novo backbone generation (diffusion) | `rfd3 design ...` | `rfd3.engine.RFD3InferenceEngine` |
| **RF3** (`models/rf3`) | Structure prediction for complexes | `rf3 fold ...` | `rf3.inference_engines.rf3.RF3InferenceEngine` |
| **MPNN** (`models/mpnn`) | Inverse folding (sequence ← backbone) | `python -m mpnn.inference --model <name> ...` | `mpnn.inference_engines.mpnn.MPNNInferenceEngine` |

The shared layer lives in `src/foundry/` (checkpoint registry, base engine, metrics, training utilities) and is exposed via the `foundry` CLI (`src/foundry_cli/download_checkpoints.py`).

The repo-root `CLAUDE.md` is the authoritative end-user cheatsheet for CLI flags, JSON input formats, and model aliases — **read it first** for any usage question. This skill exists to add the bits that aren't there: the *extension* paths.

---

## When to use this skill

- Running RFD3 / RF3 / MPNN inference, especially with **proprietary local checkpoints** (Enhanced / Thermal variants).
- Anything involving `FOUNDRY_CHECKPOINT_DIRS` or the `foundry install / list-* / clean` CLI.
- **Adding a new MPNN model** — new checkpoint of an existing architecture, *or* a new architecture subclass.
- Wiring a new inference engine into the RFD3/RF3 Hydra configs.
- Debugging "model not found", "architecture mismatch", or legacy-weight loading errors.

---

## Fast-path commands

```bash
# Install/download checkpoints (writes to ~/.foundry/checkpoints by default)
foundry install base-models                # rfd3, rf3, proteinmpnn, ligandmpnn
foundry install rfd3 rf3 ligandmpnn        # specific models
foundry list-available                      # all registered names
foundry list-installed                      # what's actually on disk + sizes

# Run inference
rfd3 design inputs=spec.json out_dir=out/
rf3 fold inputs=complex.json
python -m mpnn.inference --model ligandmpnn --structure_path in.pdb --out_directory out/

# List MPNN model aliases
python -m mpnn.inference --list_models
```

For proprietary weights (enhanced/thermal) export `FOUNDRY_CHECKPOINT_DIRS` *before* invoking the CLI — it's read at registry init.

```bash
export FOUNDRY_CHECKPOINT_DIRS="/path/to/enhanced:/path/to/thermal:$HOME/.foundry/checkpoints"
```

---

## Where things live (mental map)

```
foundry/
├── src/foundry/                       # shared infra
│   ├── inference_engines/
│   │   ├── base.py                    # base engine API
│   │   └── checkpoint_registry.py     # REGISTERED_CHECKPOINTS, FOUNDRY_CHECKPOINT_DIRS
│   ├── metrics/ trainers/ training/   # loss, fabric trainer, EMA, schedulers
│   ├── callbacks/ hydra/ utils/
│   └── ...
├── src/foundry_cli/
│   └── download_checkpoints.py        # `foundry` Typer app
├── models/
│   ├── rfd3/
│   │   ├── src/rfd3/{cli.py,engine.py,run_inference.py,...}
│   │   └── configs/                   # Hydra configs (inference.yaml, inference_engine/...)
│   ├── rf3/
│   │   ├── src/rf3/{cli.py,inference.py,inference_engines/rf3.py,...}
│   │   └── configs/
│   └── mpnn/
│       └── src/mpnn/
│           ├── inference.py                       # `mpnn` script entrypoint
│           ├── inference_engines/mpnn.py          # MPNNInferenceEngine
│           ├── model/mpnn.py                      # ProteinMPNN, LigandMPNN, Soluble/Antibody/Membrane/PSSM
│           ├── utils/
│           │   ├── inference.py                   # CLI builder, defaults, validation
│           │   ├── thermal_models.py              # THERMAL_MODELS, MODEL_ALIASES, resolve_model_config
│           │   └── weights.py                     # load_legacy_weights (key renaming, dim fixes)
│           ├── pipelines/ transforms/ collate/ samplers/ loss/ metrics/ trainers/
│           └── train.py
└── pyproject.toml                     # `[project.scripts]` defines rf3 / rfd3 / mpnn / foundry
```

---

## Extension reference (read this for any "add a new ..." task)

| Goal | File(s) | See |
|------|---------|-----|
| Register a new checkpoint for an existing MPNN architecture (most common — e.g. `enhancedmpnn_90000`) | `src/foundry/inference_engines/checkpoint_registry.py`, `models/mpnn/src/mpnn/utils/thermal_models.py` | [reference/adding-mpnn-checkpoints.md](reference/adding-mpnn-checkpoints.md) |
| Add a brand-new MPNN architecture subclass | `models/mpnn/src/mpnn/model/mpnn.py`, `inference_engines/mpnn.py` | [reference/adding-mpnn-architectures.md](reference/adding-mpnn-architectures.md) |
| Convert legacy `.pt` weights to the new layout | `models/mpnn/src/mpnn/utils/weights.py` | [reference/adding-mpnn-architectures.md](reference/adding-mpnn-architectures.md) |
| Where checkpoints are searched on disk | `src/foundry/inference_engines/checkpoint_registry.py` (`get_default_checkpoint_dirs`) | [reference/checkpoints.md](reference/checkpoints.md) |
| Add a new RFD3 / RF3 inference-engine variant | `models/rfd3/configs/inference_engine/`, `models/rf3/configs/inference_engine/` | [reference/extending-rfd3-rf3.md](reference/extending-rfd3-rf3.md) |
| Common end-to-end design workflows | (across all three models) | [reference/workflows.md](reference/workflows.md) |

> When in doubt about *what files need to change to add a new MPNN model*, follow the recipe in [reference/adding-mpnn-checkpoints.md](reference/adding-mpnn-checkpoints.md) verbatim — the most recent additions (`enhancedmpnn_70000`, `enhancedmpnn_80000`) touched exactly these files and nothing else.

---

## Conventions and gotchas

- **Architecture vs. checkpoint** — `protein_mpnn` (num_neighbors=48) and `ligand_mpnn` (num_neighbors=32) are the only two architectures the engine knows about (`MPNNInferenceEngine.allowed_model_types`). A new "model" is almost always a new *checkpoint* for one of these two architectures; only add a new architecture if the layer topology actually changes.
- **Legacy weights** — All thermal/enhanced/original ProteinMPNN/LigandMPNN/SolubleMPNN checkpoints require `is_legacy_weights=True`. The `load_legacy_weights` helper performs key renames + a 120→119 atom-type slice + atom-pair reorder + AA token reorder. Re-trained checkpoints (saved as `{"model": state_dict}`) should set `is_legacy_weights=False`.
- **Model resolution via `--model`** — When passing `--model <alias>`, `cli_to_json` calls `resolve_model_config(name) → (checkpoint_path, model_type, is_legacy_weights)`. To make a new model usable via `--model` you must register it in `thermal_models.py` *and* the checkpoint registry.
- **Two env vars for checkpoint dirs** — `FOUNDRY_CHECKPOINT_DIRS` (colon-separated, preferred) and the legacy `FOUNDRY_CHECKPOINTS_DIR` (singular). The default `~/.foundry/checkpoints` is always appended last.
- **MPNN num_neighbors mismatch** — Loading a ligand checkpoint into `ProteinMPNN` (or vice versa) silently produces wrong shapes; always set `model_type` to match `LIGAND_MPNN_VARIANTS` membership.
- **RFD3/RF3 use Hydra** — CLI flags are passed through as `key=value` overrides into `inference.yaml`; new engines/configs are added under `configs/inference_engine/*.yaml`, not by editing the Python CLI.
- **`atomworks` is the structure backbone** for all three models — input parsing (`.pdb`, `.cif`, `.cif.gz`), residue indexing (`A:118` style), and feature extraction all flow through it.

---

## How agents should work in this repo

1. **Default to editing existing files** — both the CLI surface and the registry pattern are well established. Adding a model means appending entries to existing tables, not creating new modules.
2. **Run `python -m mpnn.inference --list_models`** after any registry change to confirm the model resolves *and* the checkpoint is found on disk.
3. **Test inference with `--batch_size 1 --number_of_batches 1`** on a small structure before scaling up — model-loading errors surface immediately.
4. **Never download proprietary weights via `foundry install`** — they have empty `url=""` in the registry. They must come from a path in `FOUNDRY_CHECKPOINT_DIRS`.
5. When committing model additions, follow the existing tiny commit pattern (see `git log` for `enhancedmpnn_70000`/`_80000`): one commit per checkpoint, touching only the registry + `thermal_models.py`.
