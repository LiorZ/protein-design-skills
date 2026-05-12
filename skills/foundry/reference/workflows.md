# Common foundry workflows

End-to-end recipes that span more than one model. For per-model CLI flags and input JSON schemas, see the repo-root `CLAUDE.md`.

## 1. De novo binder design

```bash
# Step 1 — generate backbones (RFD3)
rfd3 design \
    inputs=binder_spec.json \
    out_dir=backbones/ \
    n_batches=10 \
    diffusion_batch_size=8

# Step 2 — design sequences on each backbone (LigandMPNN if target has ligands, otherwise ProteinMPNN)
for cif in backbones/*.cif; do
    python -m mpnn.inference \
        --model ligandmpnn \
        --structure_path "$cif" \
        --out_directory sequences/ \
        --batch_size 8 \
        --temperature 0.1
done

# Step 3 — fold the binder-target complex and gate on confidence (RF3)
for fa in sequences/*.fa; do
    rf3 fold inputs="$fa" out_dir=folds/
done
```

`binder_spec.json` carries `target` (`pdb_path` + chains), `binder` (length, hotspot residues), and `num_designs`. The hotspot syntax (`"A:45"`, `"A:67"`) matches the atomworks chain:residue indexing used everywhere in the toolkit.

## 2. Enzyme redesign around a cofactor

```bash
python -m mpnn.inference \
    --model enhanced \
    --structure_path enzyme_with_cofactor.cif \
    --fixed_residues "A:118,A:145,A:204" \
    --out_directory redesigned/ \
    --batch_size 8 \
    --temperature 0.1
```

`enhanced` (alias for `enhancedmpnn_80000`) and `empnn` are the recommended starting points for ligand-aware enzyme design — they're LigandMPNN-architecture (num_neighbors=32) and pick up the cofactor via the ligand subgraph features.

Use `--fixed_residues` for the catalytic residues; everything else is re-designed. For metal-coordinating residues, fix them all to avoid breaking the geometry.

## 3. Thermostable variant design

```bash
# tvp02 = thermal_vanilla_plddt85_noise02 — recommended for thermostability
python -m mpnn.inference \
    --model tvp02 \
    --structure_path backbone.pdb \
    --out_directory thermostable/ \
    --batch_size 16 \
    --temperature 0.1

# tsp02 = thermal_soluble_plddt85_noise02 — when you also want solubility
python -m mpnn.inference \
    --model tsp02 \
    --structure_path backbone.pdb \
    --out_directory thermostable_soluble/ \
    --batch_size 16
```

Higher noise (`noise02`) ⇒ more sequence diversity; lower noise (`noise002`) ⇒ closer to the wild-type sequence. `plddt85` variants were trained only on regions with predicted-LDDT > 85, biasing toward structured/folded regions.

## 4. Self-consistency / design validation

```bash
# 1. Design with MPNN
python -m mpnn.inference --model ligandmpnn --structure_path design.cif --out_directory seqs/

# 2. Fold the designed sequence back with RF3
rf3 fold inputs=seqs/design.fa out_dir=folds/

# 3. Compare the predicted structure to the original design — high TM-score / low RMSD
#    + RF3 confidence (pLDDT > 80, pTM > 0.5) ⇒ likely a real design
```

The RF3 confidence outputs (`metrics_cfg` in `inference_engine/rf3.yaml` configures pTM, ipTM, clash counts) are the standard self-consistency filter.

## 5. Multi-state / fixed-residue design

`mpnn.inference` accepts both `--fixed_residues` and `--designed_residues`. Use whichever produces the shorter list:

```bash
# Design everything except the catalytic triad
python -m mpnn.inference --model ligandmpnn --fixed_residues "A:57,A:102,A:195" ...

# Design only a flexible loop
python -m mpnn.inference --model proteinmpnn --designed_residues "A:80,A:81,A:82,A:83,A:84,A:85" ...

# Symmetric (homo-oligomer) design — tie residues across chains
python -m mpnn.inference --model proteinmpnn --homo_oligomer_chains "A,B,C" ...
```

Symmetry, bias, omit, and pair-bias also have `_per_residue` variants — see `MPNN_PER_INPUT_INFERENCE_DEFAULTS` in `models/mpnn/src/mpnn/utils/inference.py`.

## 6. Python API instead of CLI

When you need finer control or want to keep results in memory:

```python
from mpnn.inference_engines.mpnn import MPNNInferenceEngine
from mpnn.utils.thermal_models import resolve_model_config

ckpt, model_type, is_legacy = resolve_model_config("enhancedmpnn_80000")

engine = MPNNInferenceEngine(
    model_type=model_type,
    checkpoint_path=ckpt,
    is_legacy_weights=is_legacy,
    out_directory="output/",
    write_fasta=True,
    write_structures=True,
)

results = engine.run(input_dicts=[{
    "structure_path": "input.pdb",
    "name": "design",
    "batch_size": 8,
    "temperature": 0.1,
    "fixed_residues": ["A:118", "A:145"],
}])

for r in results:
    print(r.output_dict["designed_sequence"], r.output_dict["sequence_recovery"])
```

The `resolve_model_config` helper is the supported way to look up *all three* of (checkpoint_path, model_type, is_legacy_weights) by canonical name or alias — use it instead of hard-coding paths.
