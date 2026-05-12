# Adding a new MPNN architecture

Use this when the model isn't just a new checkpoint of `protein_mpnn` or `ligand_mpnn` — it needs different layers, different input features, or a different forward pass. If you only need to plug in a new `.pt` file, use [adding-mpnn-checkpoints.md](adding-mpnn-checkpoints.md) instead.

## Where the two existing architectures live

`models/mpnn/src/mpnn/model/mpnn.py` contains:

- `ProteinMPNN(nn.Module)` — base class (~lines 19–2130). Drives the encoder/decoder, vocab, and the public `forward` / `sample` API.
- `SolubleMPNN(ProteinMPNN)`, `AntibodyMPNN(ProteinMPNN)`, `MembraneMPNN(ProteinMPNN)`, `PSSMMPNN(ProteinMPNN)` — light overrides for re-trained weights / minor head changes.
- `LigandMPNN(ProteinMPNN)` (~line 2263) — overrides graph featurization (ligand subgraph, `num_neighbors=32`, atomized side chains).

These are the two **architectures** the inference engine knows about. Subclasses that don't change `state_dict` shape can re-use one of them by registering only a new checkpoint.

## Recipe

### 1. Add the model class

Subclass `ProteinMPNN` or `LigandMPNN` in `models/mpnn/src/mpnn/model/mpnn.py`. Follow the existing `SolubleMPNN` / `MembraneMPNN` examples for shape-preserving variants, or `LigandMPNN` if you need to swap the graph featurization module.

Key extension points:

- `graph_featurization_module=` argument (override the `ProteinFeatures` / `ProteinFeaturesLigand` module).
- `HAS_NODE_FEATURES = True` to enable the `W_v` node-feature projection in the base class.
- Override `__init__` / `forward` only if the I/O contract changes; otherwise prefer adding a new `graph_featurization_module`.

### 2. Add a `model_type` string to the engine allowlist

Edit `models/mpnn/src/mpnn/inference_engines/mpnn.py`:

```python
self.allowed_model_types = {"protein_mpnn", "ligand_mpnn", "my_new_mpnn"}
```

and in `_build_and_load_model`:

```python
if self.model_type == "protein_mpnn":
    model = ProteinMPNN()
elif self.model_type == "ligand_mpnn":
    model = LigandMPNN()
elif self.model_type == "my_new_mpnn":
    model = MyNewMPNN()
else:
    raise ValueError(f"Unsupported model_type: {self.model_type}")
```

### 3. Plumb the pipeline

`mpnn.pipelines.mpnn.build_mpnn_transform_pipeline(model_type=...)` builds the AtomWorks transform pipeline keyed by `model_type`. If your model needs different input features (extra channels, atomized side chains, etc.), extend this builder to recognise your new `model_type` string and produce the right pipeline.

### 4. Register the checkpoint

Same as for new checkpoints — see [adding-mpnn-checkpoints.md](adding-mpnn-checkpoints.md). Then teach `mpnn.utils.thermal_models.resolve_model_config` to map your new canonical name → `("my_new_mpnn", is_legacy)` so `--model` works.

### 5. Handle weight loading

Two paths:

**a) Re-trained from inside foundry** — checkpoint is saved as `{"model": state_dict, ...}` and weight names already match the new module names. Set `is_legacy_weights=False`; the engine calls `model.load_state_dict(checkpoint["model"], strict=True)`.

**b) Legacy checkpoint from upstream ProteinMPNN/LigandMPNN** — checkpoint is saved as `{"model_state_dict": state_dict, ...}` with the old key names. Set `is_legacy_weights=True`; the engine calls `mpnn.utils.weights.load_legacy_weights(model, path)`.

`load_legacy_weights`:

- Renames legacy keys to new names via the `legacy_weight_to_new_weight` dict.
- Slices the 120-atom-type embedding down to 119 (LigandMPNN cleanup).
- Reorders the pairwise backbone-atom-distance embedding to match the new atom-pair iteration order (N, Ca, C, O, Cb outer product).
- Reorders the AA token embedding/projection from alphabetic-1-letter order to alphabetic-3-letter order.

If your new architecture *also* needs a custom remap, add a separate loader function (`load_my_new_legacy_weights`) and dispatch on the `is_legacy_weights` flag. Don't try to overload `load_legacy_weights` — the existing remap is specific to the upstream ProteinMPNN/LigandMPNN checkpoint format.

### 6. Test

```bash
# Make sure the engine can build the architecture from scratch (no weights)
python -c "
from mpnn.inference_engines.mpnn import MPNNInferenceEngine
e = MPNNInferenceEngine(
    model_type='my_new_mpnn',
    checkpoint_path='/path/to/checkpoint.pt',
    is_legacy_weights=False,   # or True
    out_directory='/tmp/test',
)
print('OK')
"

# End-to-end CLI smoke test
python -m mpnn.inference \
    --model my_new_mpnn_alias \
    --structure_path test.pdb \
    --out_directory /tmp/mpnn_test \
    --batch_size 1 --number_of_batches 1
```

A clean run prints the legacy-weights message, completes one design, and writes a CIF + FASTA to `/tmp/mpnn_test`.
