# Training BoltzGen / inverse-fold from scratch

The repo ships with all three training configs and the data pipeline.
Most users never touch this — the released checkpoints are excellent.
You'd retrain if:

- You want a model specialized to a non-standard chemistry (e.g.,
  D-amino acids, non-canonical backbones).
- You want to fine-tune on an internal complex dataset.
- You're doing methodology research on diffusion schedules / IF design.

## Install in dev mode

```bash
git clone https://github.com/HannesStark/boltzgen
cd boltzgen
pip install -e .[dev]    # adds wandb, redis, requests, lint/test
```

## Download training data

```bash
mkdir -p training_data && cd training_data

# Targets (PDB-derived complex set)
wget -O targets.zip "https://huggingface.co/datasets/boltzgen/boltzgen1_train/resolve/main/targets.zip?download=true"
unzip targets.zip

# MSAs
wget -O msa.zip "https://huggingface.co/datasets/boltzgen/boltzgen1_train/resolve/main/msa.zip?download=true"
unzip msa.zip

# Small-molecule dictionary
wget -O mols.zip "https://huggingface.co/datasets/boltzgen/inference-data/resolve/main/mols.zip?download=true"
mkdir mols && cd mols && unzip ../mols.zip && cd ..

# Folding checkpoint (Boltz-2; used as a refold reference)
wget -O boltz2_fold.ckpt "https://huggingface.co/boltzgen/boltzgen-1/resolve/main/boltz2_conf_final.ckpt?download=true"

# Optional: structure-only pretrained init (only if you're resuming)
wget -O boltzgen1_structuretrained_small.ckpt \
  "https://huggingface.co/boltzgen/boltzgen-1/resolve/main/boltzgen1_structuretrained_small.ckpt?download=true"
```

Resulting layout:

```
training_data/
├── targets/                                       (target_dir in YAML)
├── msa/                                           (msa_dir in YAML)
├── mols/                                          (mol_dir / moldir in YAML)
├── boltz2_fold.ckpt                               (folding_checkpoint)
└── boltzgen1_structuretrained_small.ckpt          (pretrained, optional)
```

`./training_data` is the default path referenced in all three training
YAMLs. If you put data elsewhere, search-and-replace `target_dir`,
`msa_dir`, `moldir`, `pretrained`, `folding_checkpoint` (and where
present `monomer_target_dir`, `ligand_target_dir`) in:

- `src/boltzgen/resources/config/train/boltzgen.yaml`        — large model
- `src/boltzgen/resources/config/train/boltzgen_small.yaml`  — small model
- `src/boltzgen/resources/config/train/inverse_folding.yaml` — IF model

## Training commands

| Config                       | Hardware                                              | Command |
|------------------------------|--------------------------------------------------------|---------|
| `boltzgen_small.yaml`        | 8 GPUs, gradient accumulation 16                       | `python src/boltzgen/resources/main.py src/boltzgen/resources/config/train/boltzgen_small.yaml name=boltzgen_small` |
| `boltzgen.yaml`              | 8+ GPUs, full distillation dataset (not yet released)  | `python src/boltzgen/resources/main.py src/boltzgen/resources/config/train/boltzgen.yaml name=boltzgen_large`        |
| `inverse_folding.yaml`       | 8 GPUs                                                 | `python src/boltzgen/resources/main.py src/boltzgen/resources/config/train/inverse_folding.yaml name=boltzgen_if`    |

Set `CUDA_VISIBLE_DEVICES` to the GPUs you want to use:

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
python src/boltzgen/resources/main.py \
  src/boltzgen/resources/config/train/boltzgen_small.yaml \
  name=boltzgen_small
```

The large model expects additional distillation datasets that have not
yet been publicly released — you can still play with its hyper-parameters
and train on PDB data alone by trimming the data section, but expect
worse downstream design quality than the released checkpoints.

## Resuming from a checkpoint

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
python src/boltzgen/resources/main.py \
  src/boltzgen/resources/config/train/boltzgen_small.yaml \
  pretrained=./training_data/boltzgen1_structuretrained_small.ckpt \
  name=boltzgen_small_pretrained
```

## Wiring custom data

The training YAMLs all share roughly this data block (see the actual
files for the source of truth):

```yaml
data:
  datasets:
    - target_dir: ./training_data/targets
      msa_dir:    ./training_data/msa
  moldir: ./training_data/mols
pretrained: ./training_data/boltzgen1_structuretrained_small.ckpt
folding_checkpoint: ./training_data/boltz2_fold.ckpt
```

You can:

- Append more `targets/msa` pairs to `datasets:` for additional
  training data (each is a directory with one CIF per training target +
  associated MSAs).
- Replace `pretrained:` to start from a different init.
- Replace `folding_checkpoint:` to use a custom Boltz-2 variant for
  the refold reference.

## Inference with a custom checkpoint

```bash
boltzgen run spec.yaml \
  --design_checkpoints /path/to/your.ckpt \
  --output OUT \
  --num_designs 50
```

You can pass several checkpoints — each will run an equal fraction of
the designs, useful for mixing diversity-tuned and adherence-tuned
models, or your custom model alongside the released ones:

```bash
boltzgen run spec.yaml \
  --design_checkpoints \
    huggingface:boltzgen/boltzgen-1:boltzgen1_diverse.ckpt \
    /path/to/your_finetune.ckpt \
  --output OUT
```

Similarly for IF (`--inverse_fold_checkpoint`), refolding
(`--folding_checkpoint`), and affinity (`--affinity_checkpoint`).

## Hardware ballpark

| Model         | Recommended hardware                                       | Notes                                           |
|---------------|------------------------------------------------------------|-------------------------------------------------|
| `boltzgen_small`     | 8× A100 80 GB, grad accum 16                        | The "development setup". ~days per epoch on full data. |
| `boltzgen` (large)   | 8+× H100 / A100 80 GB                                | Requires distillation data not yet released. Expect weeks of training. |
| `inverse_folding`    | 8× A100 80 GB                                        | Smaller / faster than the diffusion model.       |

If you only have ≤ 24 GB GPUs, you can drop `data.cfg.batch_size` and
crank `gradient_accumulation` to stay tractable; convergence will be
slower.
