# Application 3 — Binder Design (Basic)

Generate de-novo binders against a target protein with specified hotspot
residues. Outputs are PDB files of the predicted binder–target complex,
ranked by ColabFold-based confidence metrics.

For beam search, iterative conditioning, and probabilistic interface
sampling see [iterative-and-beam.md](iterative-and-beam.md).
For preparing your own target problem set see [problem-prep.md](problem-prep.md).

## Quick start

```bash
genie3 run -c examples/binder_design/experiment.yaml
```

Generates 5 binders for `01_bhrf1` from BinderBench, runs ProteinMPNN inverse folding, then ColabFold (template mode), and applies Version 0 filters.

## Config schema

```yaml
experiment:
  name: <EXPERIMENT_NAME>

paths:
  rootdir: <OUTDIR>
  dataset: <DATADIR>           # path to a binder problem set (e.g. binderbench)

generation:
  dataset:
    source: target
    selections: <CSV>          # optional: comma-separated problem names
    tags: <CSV>                # optional: tag filter (e.g. "AlphaProteo")
    n_sample: <NUM_SAMPLES>    # candidates per problem
    cond_strategy: hotspot     # hotspot | extended | common | iter_common | iter_common_prob
  sampler:
    sampler:
      direction_scale: 0.0     # recommended for binder design

evaluation:
  version: binder
  inverse_folding:
    num_seq: 1                 # 1 sequence per backbone (default 8 is slow)
  folding:
    model_name: colabfold
    mode: template             # template (no MSA) | msa
```

### Folding modes

| `evaluation.folding.mode` | Behavior | Use when |
|---------------------------|----------|----------|
| `template` | ColabFold runs without MSA on the binder; target structure is passed as a template | Default — fast, accurate enough for V0 filters |
| `msa` | ColabFold uses MSA of the *target* sequence only (binder MSA is null) | When target structure quality is uncertain |

### `cond_strategy` (interface conditioning)

The diffusion sampler conditions on which target residues the binder should engage. Strategies:

| `cond_strategy` | Source | Notes |
|-----------------|--------|-------|
| `hotspot` | `target_interface_residues.hotspot` | Minimal hotspots from problem JSON |
| `extended` | `target_interface_residues.extended` | Auto-computed extended interface around hotspots |
| `common` | `target_interface_residues.common` | User-supplied common interface |
| `iter_common` | Computed from prior round successes | Iterative-mode only; see iterative-and-beam.md |
| `iter_common_prob` | Probabilistic version of `iter_common` | Iterative-mode only |

For one-shot binder design, `extended` is a good general default. For iterative campaigns, use `iter_common`.

## Multi-device and multi-node

```bash
# Single node, N GPUs:
genie3 run -c <CFG> --num-devices N

# Multi-node sharding:
genie3 generate -c <CFG> --num-devices <PER_NODE> --shard-id <K> --num-shards <TOTAL>
genie3 evaluate -c <CFG> --num-devices <PER_NODE> --shard-id <K> --num-shards <TOTAL>
genie3 evaluate --reduce -c <CFG>

# Track progress and missing shards:
genie3 status -c <CFG>
```

## Outputs (per problem)

`<rootdir>/<PROBLEM_NAME>/results/`:

| File | Contents |
|------|----------|
| `info.csv` | Per-design metrics (one row per ColabFold output) |
| `log.txt` | Filter pass counts per stage |
| `v0_success/success_info.csv` | Designs passing **Version 0 Filters** |
| `v0_success/successful_incomplex_binders/` | Binder PDBs (chain A, extracted from complex) |
| `v0_success/successful_complexes/` | Full predicted complex PDBs (binder + target) |
| `v0_success/successful_incomplex_binders_cluster.csv` | FoldSeek clusters at TM 0.5/0.6/0.8 |

### `info.csv` columns (key ones)

| Column | Meaning |
|--------|---------|
| `domain` | Per-design ID (one per ColabFold output) |
| `name` | Sample ID (one per generated backbone — multiple `domain` per `name` if `num_seq>1` or `num_models>1`) |
| `len`, `binder_len`, `target_len` | Lengths |
| `binder_seq` | Designed sequence |
| `complex_scrmsd` | Cα RMSD between Genie 3 backbone and ColabFold-predicted complex |
| `complex_scrmsd_map`, `complex_scrmsd_mode` | Chain-to-chain alignment used to compute the RMSD |
| `binder_ptm` | Per-chain pTM for the binder chain |
| `min_interface_pae` | Minimum interface predicted aligned error (binder ↔ target) — **lower = higher confidence** |
| `target_hotspot_coverage` | Fraction of hotspots covered by the predicted binding interface |
| `pct_alpha_helix`, `pct_strand`, `pct_loop` | Secondary structure content |

### Version 0 success filters

A design passes V0 if **all three** hold:

1. **Model agreement**: `complex_scrmsd < 2.5Å`
2. **In-silico binder quality**: `binder_ptm > 0.8` AND `min_interface_pae < 1.5Å`
3. **Hotspot coverage**:
   - If problem has ≤ 3 hotspots: `target_hotspot_coverage == 1.0` (full coverage)
   - If problem has > 3 hotspots: `target_hotspot_coverage >= 0.8`

## Speed considerations

| Setting | Effect |
|---------|--------|
| `inverse_folding.num_seq: 1` | 8× fewer ColabFold calls; reasonable for screening |
| `folding.num_models: 1` (in `reward.reward.num_models`) | Beam-search only; per-checkpoint reward eval |
| `folding.num_recycles: 3` | Beam-search default; final eval still uses 20 |
| `compile: true` | Enables `torch.compile` on the denoiser; only meaningful with beam search |

For a single-problem 200-sample run on 4× L40S, expect ~30–60 min for generation + ~1–2 hr for ColabFold (template mode, 5 models, 20 recycles, num_seq=1). MSA mode is ~2× slower.

## Diagnostics

- **All designs fail `complex_scrmsd`** → backbone–prediction disagreement; reduce `direction_scale` to `-0.5` or below for harder targets, or switch to beam search.
- **`min_interface_pae` always high** → target interface conditioning isn't engaging the right residues; try `cond_strategy: extended` instead of `hotspot`.
- **Hotspot coverage low** → wrong hotspots. Check `data/.../problems/<key>.json`'s `target_interface_residues.hotspot` against your structural intuition.
- **ColabFold OOM** → reduce `evaluation.folding.num_models` to 1 or split shards across more nodes.
- **`Missing hotspots` error during prepare.py** → hotspot tags in `config.yaml` reference residues not present in the target PDB. The script exits with a list of unmatched tags. Fix the tags or the PDB.

## Linkage to other skills

- **`proteinmpnn`** — inverse folding model used by default (`evaluation.inverse_folding.model_name: proteinmpnn`)
- **`colabfold`** / **`alphafold`** — structure prediction back-end for evaluation
- **`foldseek`** — clusters successful binders for diversity analysis
- **`ipsae`** — alternative ranking score; used internally by the binder reducer (`compute_ipsae`)
- **`protein-qc`** — additional QC thresholds and biophysical filters not enforced by default V0 filters
- **`binder-design`** — high-level guidance on whether Genie 3 vs BindCraft / RFdiffusion / BoltzGen fits your campaign
