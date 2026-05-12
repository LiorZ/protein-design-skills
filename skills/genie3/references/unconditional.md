# Application 1 — Unconditional Generation

De-novo design of monomeric protein backbones with no external constraints.
Sweep a length range and produce N samples per length.

## Quick start

```bash
genie3 run -c examples/unconditional/experiment.yaml
```

The shipped example generates 5 samples at length 50 and runs ESMFold-based evaluation. Total runtime on a single L40 ≈ a few minutes.

## Config schema

```yaml
experiment:
  name: <EXPERIMENT_NAME>

paths:
  rootdir: <OUTDIR>

generation:
  dataset:
    source: unconditional
    min_length: <MIN_LENGTH>      # inclusive
    max_length: <MAX_LENGTH>      # inclusive
    length_step: <LENGTH_STEP>    # increment
    n_sample: <NUM_SAMPLES>       # samples per length
  sampler:
    sampler:
      direction_scale: <DIRECTION_SCALE>

evaluation:
  version: unconditional
  folding:
    model_name: esmfold           # or colabfold (slower, slightly more accurate)
```

### Recommended `direction_scale`

| Length range | `direction_scale` |
|--------------|-------------------|
| ≤ 300 (short monomers) | `0.8` |
| > 300 (long monomers)  | `0.0` |

Monotonically increasing this value shifts the quality/diversity trade-off toward higher per-sample confidence at the cost of mode collapse. For exploratory sweeps, leave at the recommended value.

### Sweeping lengths

To produce 50 samples each at lengths `{50, 100, 150, ..., 500}`:

```yaml
dataset:
  source: unconditional
  min_length: 50
  max_length: 500
  length_step: 50
  n_sample: 50
```

The total dataset size is `((max - min) / step + 1) * n_sample`.

## Multi-device (single node)

```bash
genie3 run -c <CFG> --num-devices 4
```

Or split stages:

```bash
genie3 generate -c <CFG> --num-devices 4
genie3 evaluate -c <CFG> --num-devices 4
genie3 evaluate --reduce -c <CFG>
```

## Multi-node sharding

Add `--shard-id` and `--num-shards` so each node generates / evaluates a slice of `n_sample`:

```bash
# Node k of N (per shard):
genie3 generate -c <CFG> --num-devices <PER_NODE> --shard-id k --num-shards N
genie3 evaluate -c <CFG> --num-devices <PER_NODE> --shard-id k --num-shards N

# Then on a single node, after all shards complete:
genie3 evaluate --reduce -c <CFG>
```

The loader applies `_apply_shard_to_config`: it sets `dataset.n_sample` to the shard's slice and `dataset.sample_index_offset` to the starting global index. Sample IDs in `info.csv` therefore remain globally unique across shards.

`genie3 status -c <CFG>` shows which shards are done and prints the exact missing-shard re-run commands.

## Outputs

Results are written to `<rootdir>/results/`:

| File | Contents |
|------|----------|
| `info.csv` | One row per generated design: `domain`, `name`, `len`, sequences, `scrmsd` (self-consistency RMSD between Genie 3 backbone and the ESMFold model of the inverse-folded sequence), `avg_plddt`, `pct_alpha_helix`, `pct_strand`, `pct_loop` |
| `successful_generation_info.csv` | Subset where `scrmsd < 2Å` (in-silico success) |
| `successful_generations/` | PDB files of successful designs |
| `successful_generations_cluster.csv` | FoldSeek clusters at TM 0.5 / 0.6 / 0.8 |

Success criterion: **`scrmsd < 2Å`**.

Diversity is reported as the count of FoldSeek clusters at each TM threshold (number of unique structural neighborhoods).

## Diagnostics

- **Low success rate at long lengths** → reduce `direction_scale` to `0.0`; ESMFold pLDDT also tends to drop above L≈400, so prefer ColabFold at long lengths.
- **All samples look the same** → `direction_scale` is too high; lower it or sweep `0.0 / 0.4 / 0.8` to find the diversity sweet spot.
- **Spurious helices everywhere** → expected at very short lengths (≤80); use length sweeps starting at 60 or higher.

## Legacy Genie 2 backbone-only

Genie 2 (Cα-trace only) checkpoints are loadable via the legacy config:

```bash
genie3 run -c examples/unconditional/experiment_legacy.yaml
```

This swaps `generation.base.checkpoint`/`config` to the Genie 2 paths but keeps the same evaluation pipeline.
