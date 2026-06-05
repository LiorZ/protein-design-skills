# CLI + Python API reference

`bioemu.sample.main` is the one entry point. It is exposed two ways:

```bash
# CLI (Fire-style — every kwarg becomes a flag)
python -m bioemu.sample --sequence GYDPETGTWG --num_samples 10 --output_dir ~/test
```

```python
from bioemu.sample import main as sample
sample(sequence='GYDPETGTWG', num_samples=10, output_dir='~/test')
```

The signature lives in `src/bioemu/sample.py`. Every kwarg below is
accepted by both the CLI (with `--<name>`) and the Python API.

## Required

| Name | Type | Notes |
|------|------|-------|
| `sequence` | `str` or `Path` | Amino acid string, **or** a path to a FASTA file (first record used), **or** a path to an `.a3m` MSA file (query in the first row). |
| `num_samples` | `int` | Target number of samples. Resumes from existing batches in `output_dir`. |
| `output_dir` | `str` or `Path` | Output directory. **Created if missing; re-used if existing.** |

## Common

| Name | Default | Notes |
|------|---------|-------|
| `batch_size_100` | `10` | Batch size for a length-100 sequence. Real batch = `int(batch_size_100 × (100/L)²)`, clamped ≥ 1. Halve on OOM. |
| `model_name` | `"bioemu-v1.1"` | One of `"bioemu-v1.0"`, `"bioemu-v1.1"` (Science paper, **default**), `"bioemu-v1.2"`. Auto-downloaded from `huggingface.co/microsoft/bioemu`. |
| `denoiser_type` | `"dpm"` | One of `"dpm"` (default) or `"heun"`. Ignored if `denoiser_config` is set. |
| `denoiser_config` | `None` | Path (str / Path) to a denoiser **or steering** YAML, or an already-loaded dict / DictConfig. When set, the file owns the entire denoiser config (including SMC / FKC steering). |
| `filter_samples` | `True` | Filter out unphysical samples (clashes, chain breaks). Set `False` to keep everything — useful for diagnostics, dangerous for production. |
| `base_seed` | `time.time_ns()` | Base seed. Each batch uses `base_seed + start_idx` so a given (config, seed) is **reproducible** across re-runs. |

## Less common

| Name | Default | Notes |
|------|---------|-------|
| `ckpt_path` | `None` | Path to a custom checkpoint. If set, **ignores** `model_name` and **requires** `model_config_path`. |
| `model_config_path` | `None` | Path to the model config YAML (only when `ckpt_path` is set). |
| `cache_embeds_dir` | `~/.cache/colabfold/embeds_cache/` | Where to cache MSA single + pair embeddings. Reuse across runs for the same sequence to skip the ColabFold call. |
| `cache_so3_dir` | `~/sampling_so3_cache/` | Where to cache SO(3) tables (a one-time precomputation). |
| `msa_host_url` | `None` (= public ColabFold) | URL of an MMseqs2 server. Ignored if `sequence` is an `.a3m`. Set to your own MMseqs2 / `colabfold_search` server URL for production. |

## CLI examples

### Default — unfiltered, system-time seed

```bash
python -m bioemu.sample \
    --sequence GYDPETGTWG \
    --num_samples 100 \
    --output_dir ~/chignolin
```

### Reproducible large ensemble

```bash
python -m bioemu.sample \
    --sequence "$(cat my_protein.fasta | tail -n +2 | tr -d '\n')" \
    --num_samples 1000 \
    --output_dir ~/my_protein \
    --batch_size_100 5 \
    --base_seed 42
```

### Bring your own MSA (skip ColabFold)

```bash
python -m bioemu.sample \
    --sequence ~/my.a3m \
    --num_samples 100 \
    --output_dir ~/my_protein
```

The first row of the A3M is the query sequence. `msa_host_url` is
ignored.

### Custom MMseqs2 server

```bash
python -m bioemu.sample \
    --sequence GYDPETGTWG \
    --num_samples 100 \
    --output_dir ~/chignolin \
    --msa_host_url https://your-mmseqs2-server/api
```

### Physical steering (clash + chain-break avoidance)

```bash
python -m bioemu.sample \
    --sequence GYDPETGTWG \
    --num_samples 100 \
    --output_dir ~/chignolin-steered \
    --denoiser_config src/bioemu/config/steering/physical_steering.yaml
```

### FKC steering toward RMSD-to-reference

```bash
# Override the placeholder in cv_steer.yaml via Hydra dotted syntax
python -m bioemu.sample \
    --sequence GYDPETGTWG \
    --num_samples 100 \
    --output_dir ~/chignolin-cv \
    --denoiser_config src/bioemu/config/steering/cv_steer.yaml \
    +denoiser_config.fk_potentials.0.cv.reference_pdb=/abs/path/ref.pdb
```

(Or copy `cv_steer.yaml`, edit the `reference_pdb:` field, and point
`--denoiser_config` at your copy.)

### Custom checkpoint

```bash
python -m bioemu.sample \
    --sequence GYDPETGTWG \
    --num_samples 100 \
    --output_dir ~/chignolin-custom \
    --ckpt_path /path/to/my.ckpt \
    --model_config_path /path/to/my-config.yaml
```

### Smaller batch (OOM mitigation)

```bash
python -m bioemu.sample \
    --sequence "<long sequence>" \
    --num_samples 1000 \
    --output_dir ~/long_protein \
    --batch_size_100 3   # real batch ≈ 3 × (100/L)²
```

## Python API examples

### Resumable + reproducible

```python
from bioemu.sample import main as sample
sample(
    sequence='GYDPETGTWG',
    num_samples=1000,
    output_dir='~/chignolin',
    batch_size_100=5,
    base_seed=42,
)
```

### Steering with an inline dict (no YAML file)

```python
from bioemu.sample import main as sample

denoiser = {
    "_target_": "bioemu.steering.dpm_smc.dpm_solver_smc",
    "_partial_": True,
    "eps_t": 0.001, "max_t": 0.99, "N": 100, "noise": 0.5,
    "fk_potentials": [
        {
            "_target_": "bioemu.steering.UmbrellaPotential",
            "cv": {"_target_": "bioemu.steering.CaCaDistance"},
            "target": 0.38, "flatbottom": 0.1, "slope": 10.0,
            "order": 1, "linear_from": 0.1, "weight": 1.0,
        },
        {
            "_target_": "bioemu.steering.UmbrellaPotential",
            "cv": {"_target_": "bioemu.steering.PairwiseClash",
                   "min_dist": 0.41, "offset": 3},
            "target": 0.0, "flatbottom": 0.0, "slope": 30.0, "weight": 1.0,
        },
    ],
    "steering_config": {
        "num_particles": 5, "ess_threshold": 0.5,
        "start": 0.1, "end": 0.0,
    },
}

sample(sequence='GYDPETGTWG', num_samples=100,
       output_dir='~/steered', denoiser_config=denoiser)
```

### Sidechain relax

`sidechain_relax` has a separate Typer CLI:

```bash
python -m bioemu.sidechain_relax \
    --pdb-path ~/chignolin/topology.pdb \
    --xtc-path ~/chignolin/samples.xtc \
    --outpath ~/chignolin/relaxed
```

See `references/sidechain-relax.md` for all flags.
