# Adding a new MPNN checkpoint

Use this recipe when a new `.pt` file becomes available for the existing **`protein_mpnn`** or **`ligand_mpnn`** architecture (most common case — e.g. a new EnhancedMPNN training step, a new SolubleMPNN variant, a new ThermalMPNN noise level).

If the model has a genuinely new architecture (different layer counts, new module), see [adding-mpnn-architectures.md](adding-mpnn-architectures.md) instead.

## The full checklist

Adding `enhancedmpnn_90000` (a hypothetical new step of EnhancedMPNN, ligand_mpnn architecture) requires **only two files**:

### 1. Register the checkpoint

Edit `src/foundry/inference_engines/checkpoint_registry.py` and append an entry to `REGISTERED_CHECKPOINTS`:

```python
"enhancedmpnn_90000": RegisteredCheckpoint(
    url="",                                        # empty for proprietary/local-only
    filename="enhanced_mpnn_step_90000.pt",        # actual file name on disk
    description="EnhancedMPNN (step 90000)",
),
```

- The dict key is the **canonical name** (what `--model` and `resolve_model_config` accept).
- `filename` is searched inside every directory in `FOUNDRY_CHECKPOINT_DIRS` (plus `~/.foundry/checkpoints`).
- If the checkpoint is *downloadable*, fill in `url=...` and (optionally) `sha256=...` so `foundry install <name>` works.

### 2. Wire it into `thermal_models.py`

Edit `models/mpnn/src/mpnn/utils/thermal_models.py` in **three** places:

a. Add short aliases in `MODEL_ALIASES` (optional but conventional — `--list_models` shows them):

```python
"enhanced90000": "enhancedmpnn_90000",
"empnn90000":    "enhancedmpnn_90000",
```

b. If the model uses the **LigandMPNN architecture** (num_neighbors=32, ligand-aware features), add the canonical name to `LIGAND_MPNN_VARIANTS`:

```python
LIGAND_MPNN_VARIANTS = {
    "ligandmpnn",
    "enhancedmpnn_70000",
    "enhancedmpnn_80000",
    "enhancedmpnn_90000",   # <-- add
}
```

Skip this step for `protein_mpnn`-architecture models (proteinmpnn, solublempnn, thermal_*).

c. Add the canonical name to the standard/enhanced whitelist inside `resolve_model_config`:

```python
if model_name in (
    "proteinmpnn", "ligandmpnn", "solublempnn",
    "enhancedmpnn_70000", "enhancedmpnn_80000",
    "enhancedmpnn_90000",        # <-- add
):
    ...
```

d. (Optional but nice) Extend the iteration in `print_available_models` so `--list_models` shows it under "Enhanced Models":

```python
for name in ("enhancedmpnn_70000", "enhancedmpnn_80000", "enhancedmpnn_90000"):
    ...
```

### 3. (Thermal-style additions only) Add a `ThermalModelInfo`

For new *thermal* models — different noise level / filtering — also append an entry to the `THERMAL_MODELS` dict in the same file. The `name` field must match the dict key. Example:

```python
"thermal_vanilla_plddt85_noise03": ThermalModelInfo(
    name="thermal_vanilla_plddt85_noise03",
    filename="vanilla_training_out_seqid_0.5_plddt_85_noise_0.3.pt",
    model_type="vanilla",      # "vanilla" or "soluble"
    noise_level=0.3,
    plddt_filtered=True,
    description="Thermal ProteinMPNN vanilla pLDDT>85 (noise=0.3)",
),
```

Thermal models are always `protein_mpnn` architecture + legacy weights; `resolve_model_config` handles them automatically as long as they appear in `THERMAL_MODELS` and `REGISTERED_CHECKPOINTS`.

## Verification

```bash
# 1. Make the checkpoint visible
export FOUNDRY_CHECKPOINT_DIRS="/path/with/enhanced_mpnn_step_90000.pt:$HOME/.foundry/checkpoints"

# 2. Confirm resolution and that the file is found
python -m mpnn.inference --list_models | grep -i enhanced

# 3. Smoke-test inference
python -m mpnn.inference \
    --model enhanced90000 \
    --structure_path some_input.pdb \
    --out_directory /tmp/mpnn_test \
    --batch_size 1 --number_of_batches 1
```

If `--list_models` shows `✗ (not found)`, the alias is registered but the file isn't reachable — re-check `FOUNDRY_CHECKPOINT_DIRS`.

If you get a state-dict shape mismatch, the architecture is wrong — flip the `LIGAND_MPNN_VARIANTS` membership (or fix in `resolve_model_config` so `model_type` resolves to the other architecture).

## Reference example

The PRs that added `enhancedmpnn_70000` and `enhancedmpnn_80000` are the canonical templates — both modified only `checkpoint_registry.py` + `thermal_models.py`:

```bash
git show a5c4035 --stat  # add mpnn 70000 model
git show 525c339 --stat  # adding enhanced mpnn checkpoint (file only)
git show 62975d1 --stat  # initial enhanced + thermal model wiring
```
