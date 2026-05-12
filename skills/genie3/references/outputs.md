# Output Layout, CSV Schema, and Success Filters

After `genie3 evaluate --reduce`, results land under `<rootdir>/[<problem>/]results/`.
This page documents the directory layout, every column in `info.csv`, and the
filters that define "in-silico success" for each application.

## Common output layout

### Unconditional

```
<rootdir>/
  pdbs/                                    # raw generated backbones (pre-eval)
    sample_0.pdb
    sample_1.pdb
    ...
  results/
    info.csv
    successful_generation_info.csv
    successful_generations/                # passing PDBs
      sample_<id>.pdb
    successful_generations_cluster.csv     # FoldSeek clusters
    eval.done                              # sentinel; reduce complete
```

### Motif scaffolding

```
<rootdir>/
  <PROBLEM_NAME>/
    pdbs/
    results/
      info.csv
      successful_backbone_generation_info.csv
      successful_backbone_generations/
      successful_backbone_generations_cluster.csv
      successful_allatom_generation_info.csv
      successful_allatom_generations/
      successful_allatom_generations_cluster.csv
      successful_allatom_strict_generation_info.csv
      successful_allatom_strict_generations/
      successful_allatom_strict_generations_cluster.csv
      eval.done
```

### Binder design

```
<rootdir>/
  <PROBLEM_NAME>/
    pdbs/
    results/
      info.csv
      log.txt                              # per-filter pass counts
      v0_success/
        success_info.csv
        successful_incomplex_binders/      # binder chain only (extracted from complex)
          <design>.pdb
        successful_complexes/              # full predicted complex
          <design>.pdb
        successful_incomplex_binders_cluster.csv
      eval.done
```

## `info.csv` schema

Columns are application-specific. Common columns first; per-application columns below.

### Common (all applications)

| Column | Type | Meaning |
|--------|------|---------|
| `domain` | str | Per-prediction ID (one per ColabFold/ESMFold output) |
| `name`   | str | Per-sample ID (one per generated backbone) |
| `len`    | int | Total residue count |
| `model`  | str | Folding model used (`esmfold`, `colabfold`, `boltz2`) |
| `generation_filepath` | str | Path to original generated PDB |
| `pct_alpha_helix` | float | Fraction of residues in α-helix (DSSP) |
| `pct_strand` | float | Fraction in β-strand |
| `pct_loop` | float | Fraction in loop / coil |

When `inverse_folding.num_seq > 1` and/or folding `num_models > 1`, multiple `domain` rows share the same `name`.

### Unconditional + Motif scaffolding

| Column | Meaning |
|--------|---------|
| `seq` | Designed sequence (single chain) |
| `scrmsd` | Self-consistency RMSD: Cα RMSD between Genie 3 backbone and ESMFold/ColabFold model of the inverse-folded sequence |
| `avg_plddt` | Mean per-residue pLDDT of the predicted structure |

### Motif scaffolding (additional)

| Column | Meaning |
|--------|---------|
| `motif_ca_rmsd` | Cα RMSD of generated motif to target (max across multi-motif) |
| `motif_bb_rmsd` | Backbone-atom RMSD (N, CA, C, O) (max across multi-motif) |
| `motif_aa_rmsd` | All-heavy-atom RMSD (max across multi-motif) |

### Binder design (additional)

| Column | Meaning |
|--------|---------|
| `binder_seq` | Designed binder sequence (chain A) |
| `binder_len` | Binder residue count |
| `target_len` | Target residue count |
| `complex_scrmsd` | Cα RMSD between Genie 3 complex backbone and ColabFold-predicted complex |
| `complex_scrmsd_map` | Pipe-separated string of the chain-to-chain alignment used |
| `complex_scrmsd_mode` | Alignment mode (e.g. `binder_only`, `complex`) |
| `binder_ptm` | Per-chain pTM for chain A (binder) |
| `min_interaction_pae` | Minimum interaction PAE (binder ↔ target). **Lower = higher confidence in interface** |
| `target_hotspot_coverage` | Fraction of hotspots in the predicted binding interface |
| `ipsae`, `pdockq`, ... | Additional confidence metrics (computed by `compute_ipsae`) |

## Success filters per application

### Unconditional

```
scrmsd < 2 Å
```

Output: `successful_generation_info.csv` and `successful_generations/`.

### Motif scaffolding (three nested criteria)

| Criterion | Definition |
|-----------|------------|
| Backbone | `scrmsd < 2 Å` AND `motif_ca_rmsd < 2 Å` |
| All-atom | `scrmsd < 2 Å` AND `motif_aa_rmsd < 2 Å` |
| All-atom strict | `scrmsd < 2 Å` AND `motif_aa_rmsd < 1 Å` |

Each criterion produces its own `successful_*_generation_info.csv`, `successful_*_generations/`, and FoldSeek cluster CSV. A design can pass multiple criteria.

### Binder design — Version 0 filters (V0)

A design passes V0 if **all three** hold:

1. **Model agreement**:
   ```
   complex_scrmsd < 2.5 Å
   ```
2. **In-silico binder quality**:
   ```
   binder_ptm > 0.8  AND  min_interface_pae < 1.5
   ```
3. **Hotspot coverage**:
   - `target_hotspot_coverage == 1.0` if `len(hotspots) <= 3`
   - `target_hotspot_coverage >= 0.8` if `len(hotspots) > 3`

`log.txt` records the per-filter pass counts (both at "design" granularity = unique `name`, and "generation" granularity = unique `domain`).

V0 thresholds were calibrated for the BinderBench targets shipped with the repo. For tighter filters (V1, exploratory), see [protein-qc skill](../../README.md) — the binder reducer leaves V1 outputs commented out by default.

## FoldSeek clustering

For each `successful_*` directory, `*_cluster.csv` lists cluster assignments at TM-score thresholds **0.5**, **0.6**, **0.8**:

| Column | Meaning |
|--------|---------|
| `domain` | Design ID |
| `cluster_tm_0_5` | Cluster ID at TM≥0.5 (loose; "same fold family") |
| `cluster_tm_0_6` | Cluster ID at TM≥0.6 (medium) |
| `cluster_tm_0_8` | Cluster ID at TM≥0.8 (tight; "near-identical structure") |

Diversity is reported as the count of unique clusters at each threshold. The evaluation summary log prints these as `unique @ tm_0_5` and `unique @ tm_0_6`.

## Per-stage log directories

```
logs/runs/
  <YYYYMMDD-HHMMSS>-<command>/
    run.log                          # parent log (full structured output)
    config.snapshot.yaml             # frozen copy of the config used
    workers/
      generate.0.log
      generate.1.log
      ...
      evaluate.0.log
      ...
```

Pass `--log-dir <DIR>` to relocate.

## Binder reducer summary log (`log.txt`)

Sample contents:

```
Number of generations with high model agreement:          145
Number of designs with high model agreement:              52
Number of generations with high in-silico binder quality: 87
Number of designs with high in-silico binder quality:     31
v0_success: 22 designs, 12 unique @ tm_0_5, 8 unique @ tm_0_6
```

"Generations" = total ColabFold predictions (multiple per design if `num_seq>1`).
"Designs" = unique generated backbones.

## Programmatic post-processing

Each per-design row in `info.csv` keys into the PDB filename:

- Unconditional: `pdbs/<name>.pdb` and `successful_generations/<name>.pdb`
- Motif: `<problem>/pdbs/<name>.pdb` and `<problem>/results/successful_*_generations/<name>.pdb`
- Binder: complex at `v0_success/successful_complexes/<domain>.pdb`, binder-only at `v0_success/successful_incomplex_binders/<domain>.pdb`

Load `info.csv` with pandas:

```python
import pandas as pd
df = pd.read_csv("out/binder_bhrf1/01_bhrf1/results/info.csv")
v0 = df[
    (df.complex_scrmsd < 2.5)
    & (df.binder_ptm > 0.8)
    & (df.min_interaction_pae < 1.5)
]
```
