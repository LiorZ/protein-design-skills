# Training / fine-tuning

> Updated training code for Boltz-2 is "coming soon" per the upstream repo (as of v2.2.1). Boltz-1 training is fully released. Use this doc as a guide; check the upstream repo for Boltz-2 specifics when they land.

## What you can train

| Model | Config | Status |
|-------|--------|--------|
| Boltz-1 structure | `scripts/train/configs/structure.yaml` | ✅ Released |
| Boltz-1 confidence | `scripts/train/configs/confidence.yaml` | ✅ Released |
| Boltz-2 structure / affinity | — | ⚠️ Coming soon (use Boltz-1 code as a template) |

## Data requirements

You need ~250 GB of disk for the pre-processed PDB + OpenFold distillation datasets. The pre-processed tarballs (one-time downloads):

```bash
# Pre-processed structures
wget https://boltz1.s3.us-east-2.amazonaws.com/rcsb_processed_targets.tar
tar -xf rcsb_processed_targets.tar && rm rcsb_processed_targets.tar

# Pre-processed PDB MSAs
wget https://boltz1.s3.us-east-2.amazonaws.com/rcsb_processed_msa.tar
tar -xf rcsb_processed_msa.tar && rm rcsb_processed_msa.tar

# OpenFold distillation set
wget https://boltz1.s3.us-east-2.amazonaws.com/openfold_processed_targets.tar
tar -xf openfold_processed_targets.tar && rm openfold_processed_targets.tar

wget https://boltz1.s3.us-east-2.amazonaws.com/openfold_processed_msa.tar
tar -xf openfold_processed_msa.tar && rm openfold_processed_msa.tar

# Per-ligand symmetry table
wget https://boltz1.s3.us-east-2.amazonaws.com/symmetry.pkl
```

## Config

Modify `scripts/train/configs/structure.yaml`:

```yaml
trainer:
  devices: 1                      # change for multi-GPU
output: /abs/path/to/checkpoints  # where to write checkpoints
resume: null                      # or path/to/.ckpt to resume

data:
  datasets:
    - _target_: boltz.data.module.training.DatasetConfig
      target_dir: /abs/path/to/rcsb_processed_targets
      msa_dir:    /abs/path/to/rcsb_processed_msa
      prob: 0.5
      sampler:
        _target_: boltz.data.sample.cluster.ClusterSampler
      cropper:
        _target_: boltz.data.crop.boltz.BoltzCropper
        min_neighborhood: 0
        max_neighborhood: 40
      split: ./scripts/train/assets/validation_ids.txt
    - _target_: boltz.data.module.training.DatasetConfig
      target_dir: /abs/path/to/openfold_processed_targets
      msa_dir:    /abs/path/to/openfold_processed_msa
      prob: 0.5
      sampler:
        _target_: boltz.data.sample.cluster.ClusterSampler
      cropper:
        _target_: boltz.data.crop.boltz.BoltzCropper
        min_neighborhood: 0
        max_neighborhood: 40

  symmetries: /abs/path/to/symmetry.pkl
  max_tokens: 512                 # crop size (token count); 256 / 384 / 512 are reasonable
  max_atoms:  4608                # crop atom budget; 2304 / 3456 / 4608 pair with the token sizes above
```

Memory budget rules of thumb (per GPU):

| `max_tokens` | `max_atoms` | Approx VRAM |
|--------------|-------------|-------------|
| 256          | 2304        | 24 GB       |
| 384          | 3456        | 40 GB       |
| 512          | 4608        | 80 GB       |

## Launching

```bash
# Debug — single GPU, no DDP, no wandb, num_workers=0
python scripts/train/train.py scripts/train/configs/structure.yaml debug=1

# Full run
python scripts/train/train.py scripts/train/configs/structure.yaml

# Confidence model
python scripts/train/train.py scripts/train/configs/confidence.yaml
```

The script uses Hydra; override any field on the CLI:

```bash
python scripts/train/train.py scripts/train/configs/structure.yaml \
  trainer.devices=4 \
  data.max_tokens=384 \
  data.max_atoms=3456 \
  output=/scratch/run42
```

## Processing your own raw data

If you want to train on additional data, the upstream pipeline is `scripts/process/`:

1. **CCD dictionary**: pre-built file is provided (`ccd.pkl`); regenerate from `components.cif` only if you need.
2. **Sequence clustering**: `cluster.py` uses MMseqs2 to assign 40%-identity clusters for proteins, unique-sequence clusters for NA, per-CCD clusters for ligands.
3. **MSAs**: provided pre-built for PDB / OpenFold (`rcsb_raw_msa.tar`, `openfold_raw_msa.tar` — 130 GB and 88 GB respectively). For your own data, use ColabFold's `colab_search` and MSA filenames must be `sha256(sequence).a3m`:

   ```python
   import hashlib
   def hash_sequence(seq: str) -> str:
       return hashlib.sha256(seq.encode()).hexdigest()
   ```

4. **MSA processing** (`msa.py`): annotates with taxonomy via a local Redis instance hosting the taxonomy database (`taxonomy.rdb`).
5. **Structure processing** (`rcsb.py`): expects mmCIF files; uses a Redis instance with `ccd.rdb` for the CCD lookups.

Full step-by-step is in the upstream `docs/training.md`; the prerequisites are MMseqs2 and Redis installed locally.

## Fine-tuning

`resume:` accepts a `.ckpt` file. To fine-tune the released Boltz-1 weights on a private dataset:

```yaml
resume: ~/.boltz/boltz1_conf.ckpt
data:
  datasets:
    - _target_: boltz.data.module.training.DatasetConfig
      target_dir: /path/to/your/processed_targets
      msa_dir:    /path/to/your/processed_msa
      prob: 1.0
```

The PairformerArgs / DiffusionParams defaults in `boltz.main` should match the released checkpoint; don't tweak architecture flags during fine-tuning unless you intend to also train from scratch.

## Evaluation

Evaluation scripts live at `scripts/eval/run_evals.py` and `scripts/eval/aggregate_evals.py`. They wrap OpenStructure 2.8.0 (the specific version matters for reproducibility). The Boltz-1 results CSVs and outputs are mirrored at:

```
https://drive.google.com/file/d/1JvHlYUMINOaqPTunI9wBYrfYniKgVmxf/view?usp=sharing
```

Updated Boltz-2 evaluation code and predictions for FEP+ / CASP16 / MF-PCBA are "coming soon" per the upstream repo.
