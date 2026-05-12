# Filtering and ranking

The filtering step is **fast** (~15 seconds) and **stateless** — it
reads `aggregate_metrics_analyze.csv` and writes a new
`final_ranked_designs/` directory. You will almost always run it more
than once on the same set of designs while tuning thresholds.

Two front ends:

1. **CLI** — `boltzgen run SPEC --steps filtering --output OUT …`
2. **Jupyter** — the bundled `filter.ipynb` at the repo root. Often the
   more convenient option because you can preview metric distributions
   inline.

## What filtering actually does

1. **Hard filters** — drop any design that fails:
   - the refolding-RMSD threshold (`--refolding_rmsd_threshold`)
   - amino-acid composition caps (if `--filter_biased true`)
   - any `--additional_filters` you specify
   - any cysteine filters (`filter_cysteine=true` under peptide / antibody /
     nanobody protocols)
2. **Rank by quality** — compute a multi-metric inverse-rank score over
   the survivors. Each metric `m` contributes `rank(m) / weight(m)`; lower
   total = better. You can re-weight or drop metrics via
   `--metrics_override`. The top `--top_budget` (default 10) make it
   into `intermediate_ranked_<N>_designs/`.
3. **Diversity selection** — from the quality-filtered survivors, pick
   `--budget` designs that trade off rank and sequence diversity via
   `--alpha`. `--alpha 0` = pure quality, `--alpha 1` = pure diversity.
   Default is 0.001 (or 0.01 for `peptide-anything`).
4. **Size buckets** — optionally enforce per-length caps with
   `--size_buckets MIN-MAX:N` (e.g. `--size_buckets 10-20:5 20-30:10`).
5. **Write outputs** — CIFs copied from `refold_cif/`, metrics CSVs,
   `results_overview.pdf` plots.

## Key flags

| Flag                              | Effect                                                                                       |
|-----------------------------------|----------------------------------------------------------------------------------------------|
| `--budget B`                      | Final diversity-optimized set size (default 30).                                              |
| `--alpha A`                       | Quality-vs-diversity (0=quality, 1=diversity).                                                |
| `--filter_biased {true,false}`    | Drop ALA/GLY/GLU/LEU/VAL composition outliers.                                                |
| `--metrics_override k=w …`        | Per-metric inverse weight; bigger weight = less important; `k=none` drops the metric.         |
| `--additional_filters 'k>v' …`    | Extra hard filters; `>` for higher-is-better, `<` for lower-is-better. **Single-quote!**       |
| `--size_buckets MIN-MAX:N …`      | Length-bucketed caps in the final set.                                                        |
| `--refolding_rmsd_threshold X`    | Filter on backbone refolding RMSD (lower better).                                              |

Also accepts hydra-style overrides via `--config filtering k=v`:

```bash
boltzgen run SPEC --steps filtering --output OUT \
  --config filtering filter_cysteine=true peptide_type=cyclic \
  --config filtering num_liability_plots=5 plot_seq_logos=true
```

## Common metrics you'll filter on

After the analysis step writes `aggregate_metrics_analyze.csv`, you have
columns like:

| Column                           | Higher / lower better | What it measures                                              |
|----------------------------------|-----------------------|---------------------------------------------------------------|
| `iptm`, `design_iptm`            | higher                | Interface confidence (Boltz-2 refold)                         |
| `design_residue_iptm`            | higher                | Interface confidence at *designed* residues only              |
| `design_to_target_iptm`          | higher                | Cross-chain confidence between binder and target              |
| `ptm`, `design_ptm`, `target_ptm`| higher                | Per-chain TM confidence                                        |
| `min_interaction_pae`            | lower                 | Best PAE at interface                                          |
| `min_design_to_target_pae`       | lower                 | Best cross-chain PAE                                           |
| `interaction_pae`                | lower                 | Mean interface PAE                                             |
| `refolding_rmsd`                 | lower                 | RMSD between design and Boltz-2 refold                         |
| `filter_rmsd_design`             | lower                 | RMSD between IF'd design and `design_folding` refold (binder-alone) |
| `plip_hbonds`, `plip_hbonds_refolded` | higher           | # PLIP hydrogen bonds at the interface                         |
| `plip_saltbridge*`               | higher                | # PLIP salt bridges                                            |
| `delta_sasa_original` / `_refolded` | higher             | Buried interface area                                          |
| `largest_hydrophobic_refolded`   | lower                 | Largest exposed hydrophobic patch (turn off for peptides)      |
| `design_ALA`, `design_GLY`, `design_GLU`, `design_LEU`, `design_VAL` | varies | Composition fractions (with `filter_biased=true`, caps are 0.20–0.30 typically). |
| `affinity_pred_value`            | lower                 | log10(IC50 µM) for small-molecule binders                      |
| `affinity_probability_binary`    | higher                | Probability ligand binds at all                                |

## Idiomatic filter re-runs

```bash
# Loosen the refolding-RMSD threshold and weight PLIP H-bonds less
boltzgen run spec.yaml --steps filtering --output OUT \
  --refolding_rmsd_threshold 3.0 \
  --metrics_override plip_hbonds_refolded=4 \
  --alpha 0.05

# Demand at least 4 H-bonds and a small hydrophobic patch
boltzgen run spec.yaml --steps filtering --output OUT \
  --additional_filters 'plip_hbonds_refolded>4' 'largest_hydrophobic_refolded<5'

# Cap ALA and GLY composition explicitly (in addition to defaults)
boltzgen run spec.yaml --steps filtering --output OUT \
  --additional_filters 'design_ALA<0.3' 'design_GLY<0.2'

# Drop a metric you don't care about
boltzgen run spec.yaml --steps filtering --output OUT \
  --metrics_override delta_sasa_refolded=none

# Per-length-bucket cap, e.g., for a peptide campaign
boltzgen run spec.yaml --steps filtering --output OUT \
  --size_buckets 5-9:5 10-14:10 15-19:10 20-25:5

# Diversity-emphasized final set
boltzgen run spec.yaml --steps filtering --output OUT \
  --alpha 0.2 --budget 50
```

## `filter.ipynb`

The bundled notebook is **the** recommended interface for tuning. It:

- Loads `aggregate_metrics_analyze.csv` and displays distributions.
- Lets you toggle filters interactively and preview the resulting set
  size before writing.
- Re-runs the same `Filter.run()` underlying the CLI.

Two reasons to prefer it: distribution histograms and instant feedback.
Two reasons not to: you can't easily script it from agents, and it
requires Jupyter installed.

## Filtering inside `protein-small_molecule`

The protocol pre-sets `use_affinity=true` in `filtering.yaml`, which:

- Switches the metric weights to favor affinity-aware rankings.
- Adds `affinity_pred_value` and `affinity_probability_binary` to the
  default metric set.

You can still override:

```bash
boltzgen run spec.yaml --steps filtering --output OUT \
  --protocol protein-small_molecule \
  --additional_filters 'affinity_pred_value<0.0' 'affinity_probability_binary>0.7'
```

## Filtering inside `protein-redesign`

The protocol replaces almost all default metric weights:

```python
metrics_override = {
  design_to_target_iptm: null, neg_min_design_to_target_pae: null,
  design_ptm: null, plip_hbonds_refolded: null,
  plip_saltbridge_refolded: null, delta_sasa_refolded: null,
  plip_hbonds: null, plip_saltbridge: null,
  delta_sasa_original: null,
  design_residue_iptm: 1, iptm: 2, ptm: 3, neg_filter_rmsd_design: 4
}
```

So you rank by `design_residue_iptm` → `iptm` → `ptm` →
`neg_filter_rmsd_design`. This makes sense because there is no
target/binder split in a redesign run.

## Merged filtering after parallel runs

If you ran a SLURM array of 20 jobs each making 1000 designs, do:

```bash
boltzgen merge task-* --output merged_run
boltzgen run spec.yaml --steps filtering --output merged_run \
  --protocol protein-anything --budget 60 --alpha 0.05
```

The `merge` command stitches all `intermediate_designs_inverse_folded/`
contents into one and renames any colliding design IDs.

## Reading `results_overview.pdf`

The PDF has, in order:

1. Per-metric distribution histograms for the all-designs and
   filtered-designs sets.
2. Scatter plots of pairs of metrics (`iptm` vs `refolding_rmsd`, etc.).
3. Length-distribution histogram of the final set.
4. (If `plot_seq_logos=true`) sequence-logo diagrams of the designed
   regions.
5. (If `num_liability_plots>0`) per-design liability annotations.

Use it for two things:

1. **Sanity check**: are the filters working? If every design landed at
   the floor of `refolding_rmsd`, the threshold is loose. If almost none
   survive, it's too tight.
2. **Campaign report**: ship the PDF + final CSV + final CIFs to whoever
   is screening / synthesizing.
