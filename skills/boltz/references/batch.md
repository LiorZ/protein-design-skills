# Batch / multi-GPU inference

## A directory of YAMLs

The simplest way to run many predictions:

```bash
boltz predict /path/to/yamls/ --out_dir /path/to/results --use_msa_server
```

Boltz globs every `.yaml`, `.yml`, `.fasta`, `.fa` under the input directory. Each input creates its own `boltz_results_<stem>/` subdirectory under `--out_dir`.

## Multi-GPU via DDP

```bash
boltz predict /path/to/yamls/ \
  --out_dir /path/to/results \
  --devices 4 \
  --use_msa_server
```

With `--devices > 1`, Boltz uses PyTorch-Lightning DDP. The start method is `fork` on Linux/macOS and `spawn` on Windows. If the number of inputs is smaller than `--devices`, Boltz clamps `--devices` to the input count (you'll see `Number of requested devices is greater than the number of predictions, taking the minimum.`).

Predictions are distributed at the input level (each YAML is assigned to one GPU). There is no within-prediction parallelism across GPUs — a single very large complex still runs on one GPU.

## Specifying which GPUs

`--devices` is an integer count; Lightning picks GPUs `0..N-1`. To use specific devices, set `CUDA_VISIBLE_DEVICES` before launching:

```bash
CUDA_VISIBLE_DEVICES=2,3,5,7 boltz predict yamls/ --devices 4 --use_msa_server
```

## Memory tuning

| Lever | Effect |
|-------|--------|
| `--max_parallel_samples N` | Cap concurrent diffusion samples (default 5). Drop to 1 for OOM-prone large complexes. |
| `--num_workers N` | DataLoader workers per device (default 2). |
| `--preprocessing-threads N` | CPU threads for input prep (default = cpu count). Drop if you're constrained on RAM. |
| `--max_msa_seqs N` | Cap MSA depth (default 8192). Smaller → less VRAM. |
| `--subsample_msa` + `--num_subsampled_msa N` | Subsample at runtime; 1024 is a good starting point. |
| `--diffusion_samples N` | Each sample is a forward pass through the diffusion module. |
| `--recycling_steps N` | More recycles → more accurate, more memory and time. |
| `--no_kernels` | Disable `cuequivariance` kernels (less VRAM-efficient but works on old cards). |

For a 24 GB card running a 600-residue complex: `--max_parallel_samples 1 --max_msa_seqs 4096 --diffusion_samples 1` usually fits.

## Reusing preprocessing across runs

Boltz caches per-input tokenization under `boltz_results_<stem>/processed/`. If you change YAML parameters but want to keep the same `--out_dir`:

- Without `--override`: existing predictions are skipped; `processed/` is reused.
- With `--override`: everything is recomputed.

For "predict 10,000 ligand poses against the same target," cache the **target MSA** once (`processed/msa/<sha256(target_seq)>.a3m`) and reference it from every per-ligand YAML's `msa:` field. That sidesteps the ColabFold server entirely after the first run.

## Sample pipeline

```bash
# 1. One-time: predict the target alone to populate the MSA cache.
boltz predict target.yaml --out_dir cache_run/ --use_msa_server

# 2. Extract the MSA path (it's named by sha256 of the sequence).
TARGET_MSA="$(realpath cache_run/boltz_results_target/processed/msa/*.a3m)"

# 3. Generate per-ligand YAMLs referencing $TARGET_MSA.
for L in ligands/*.smi; do
  STEM=$(basename "$L" .smi)
  SMILES=$(cat "$L")
  cat > yamls/${STEM}.yaml <<EOF
version: 1
sequences:
  - protein:
      id: A
      sequence: $TARGET_SEQ
      msa: $TARGET_MSA
  - ligand:
      id: L
      smiles: '$SMILES'
properties:
  - affinity:
      binder: L
EOF
done

# 4. Predict across 4 GPUs.
boltz predict yamls/ --out_dir screen_results/ --devices 4

# 5. Aggregate.
python aggregate.py screen_results/
```

## Aggregating results

```python
import json
from pathlib import Path
import pandas as pd

rows = []
for d in Path("screen_results").glob("boltz_results_*"):
    stem = d.name.removeprefix("boltz_results_")
    aff_files = list(d.glob(f"predictions/{stem}/affinity_*.json"))
    cfg_files = sorted(d.glob(f"predictions/{stem}/confidence_*_model_0.json"))
    if not aff_files or not cfg_files:
        continue
    aff = json.loads(aff_files[0].read_text())
    cfg = json.loads(cfg_files[0].read_text())
    rows.append({"stem": stem, **aff, **{f"struct_{k}": v for k, v in cfg.items() if not isinstance(v, dict)}})

df = pd.DataFrame(rows).sort_values("affinity_probability_binary", ascending=False)
print(df.head(20))
```

## Restart / resume

If a batch run is killed:

```bash
# Re-run; finished inputs are skipped automatically.
boltz predict yamls/ --out_dir screen_results/ --devices 4
```

To force-retry a specific input, delete its `boltz_results_<stem>/predictions/<stem>/` directory and re-run.

## Slurm template

```bash
#!/usr/bin/env bash
#SBATCH --job-name=boltz_screen
#SBATCH --gres=gpu:4
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=24:00:00

source ~/envs/boltz-env/bin/activate
export BOLTZ_CACHE=/scratch/$USER/boltz_cache

srun boltz predict /scratch/$USER/yamls/ \
  --out_dir /scratch/$USER/results/ \
  --devices 4 \
  --use_msa_server \
  --diffusion_samples 3 \
  --seed 42
```

## Gotchas

- **Restart with `--seed` set is not bit-exact** across restarts because DDP shuffles input → GPU assignment differently if the input set changes. For exact reproducibility, predict each YAML in a separate single-GPU job.
- **Network throttling** on the public ColabFold server hits at ~1 request/sec; for thousands of inputs, pre-cache MSAs.
- **One affinity ligand per YAML** — you cannot batch many ligands into one YAML and get per-ligand affinity. Use one YAML per ligand.
