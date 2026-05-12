# Pipeline steps

`boltzgen run` executes a sequence of `PipelineStep` objects. Each step
is a Hydra-configured script run **as a subprocess** (so you can change
device count / precision per step), with its resolved config written to
`<OUTPUT>/config/<step_name>.yaml` and the manifest at
`<OUTPUT>/steps.yaml`.

The full step universe:

```
design  →  inverse_folding  →  folding  →  design_folding  →  affinity  →  analysis  →  filtering
```

Which steps actually run depends on the `--protocol` and `--steps` flags.

Each step's underlying entrypoint:

- **Design**: `src/boltzgen/task/predict/predict.py` (GPU)
- **Inverse-folding**: same (GPU)
- **Folding / design-folding / affinity**: same (GPU)
- **Analysis**: `src/boltzgen/task/analyze/analyze.py` (CPU, multi-process)
- **Filtering**: `src/boltzgen/task/filter/filter.py` (CPU, very fast)

## Step-by-step

### 1. `design` — diffusion sampling of backbones

| Topic                  | Detail                                                                                                  |
|------------------------|---------------------------------------------------------------------------------------------------------|
| Input                  | Design spec YAML(s) (`data.cfg.yaml_path`)                                                              |
| Output                 | `intermediate_designs/*.cif` (backbone-only) + `*.npz` (metadata)                                       |
| Checkpoint(s)          | `--design_checkpoints` (default: `boltzgen1_diverse.ckpt` + `boltzgen1_adherence.ckpt`, half each)      |
| Hydra config           | `src/boltzgen/resources/config/design.yaml`                                                             |
| Knobs                  | `--num_designs`, `--diffusion_batch_size`, `--step_scale`, `--noise_scale`, `--use_kernels`              |
| Skipped when           | `--only_inverse_fold` (replaced with a single inverse-fold-only pass)                                   |
| Notes                  | Sequence in the CIF is the diffusion-time best guess and will be replaced by inverse-folding next.       |

**Defaults** (`design.yaml`):
- `recycling_steps: 3`, `sampling_steps: 500`, `diffusion_samples: 1`
  (overridden per batch by `--diffusion_batch_size`)
- Step / noise schedule alternates between 1.8/2.0 and 0.95/0.88
- Dilated sampling schedule with `time_dilation: 2.667` from `t∈[0.6, 0.8]`

To use a single fixed step/noise scale (sometimes better for novel
chemistry):

```bash
boltzgen run spec.yaml --step_scale 1.8 --noise_scale 0.98 ...
```

### 2. `inverse_folding` — sequence design on the generated backbone

| Topic                  | Detail                                                                                                       |
|------------------------|--------------------------------------------------------------------------------------------------------------|
| Input                  | `intermediate_designs/`                                                                                       |
| Output                 | `intermediate_designs_inverse_folded/*.cif` (sidechains added) + `*.npz`                                      |
| Checkpoint             | `--inverse_fold_checkpoint` (default `boltzgen1_ifold.ckpt`)                                                  |
| Hydra config           | `src/boltzgen/resources/config/inverse_fold.yaml`                                                            |
| Knobs                  | `--inverse_fold_num_sequences`, `--inverse_fold_avoid`, `--skip_inverse_folding`                              |
| Notes                  | For designed residues, only backbone atoms have coordinates after this step; sidechains are placed by the model. |

The IF model is **autoregressive** and trained jointly with the diffusion
backbone — usually beats off-the-shelf ProteinMPNN on BoltzGen-shaped
designs, but you can replace it with another inverse folder via
`--skip_inverse_folding` and then bring in your own sequences before the
`folding` step.

Per-position residue constraints (`residue_constraints:` in YAML) are
applied here. So is `--inverse_fold_avoid LETTERS`.

### `--only_inverse_fold` (alternative flow)

If you already have a complete backbone (e.g., from RFdiffusion, from a
crystal structure, or from a prior BoltzGen run) you can skip diffusion
and run IF directly:

```bash
boltzgen run spec.yaml --only_inverse_fold \
  --inverse_fold_num_sequences 10
```

The spec must declare the full backbone via a `file` entity with `design:`
covering the residues to re-sequence. See
[`../examples/inverse_folding_only.yaml`](../examples/inverse_folding_only.yaml).

This uses the dedicated config `inverse_fold_only.yaml` (not
`inverse_fold.yaml`), which takes the YAML directly as input rather than
a directory of designs.

### 3. `folding` — refold the complex with Boltz-2

| Topic                  | Detail                                                                                                       |
|------------------------|--------------------------------------------------------------------------------------------------------------|
| Input                  | `intermediate_designs_inverse_folded/`                                                                        |
| Output                 | `intermediate_designs_inverse_folded/refold_cif/*.cif` (full atom complex)                                    |
| Checkpoint             | `--folding_checkpoint` (default `boltz2_conf_final.ckpt`)                                                    |
| Hydra config           | `src/boltzgen/resources/config/fold.yaml`                                                                    |
| Defaults               | `diffusion_samples: 5`, `recycling_steps: 3`, `sampling_steps: 200`                                            |
| Metric keys emitted    | `min_interaction_pae`, `min_design_to_target_pae`, `interaction_pae`, `ligand_iptm`, `protein_iptm`, `iptm`, `design_iptm`, `design_iiptm`, `design_to_target_iptm`, `design_residue_iptm`, `design_ptm`, `target_ptm`, `ptm` |

This step is the heaviest single GPU cost in the pipeline. It re-folds
the (target, designed binder) complex from scratch and compares the
result to the diffusion-generated structure — designs whose refold
diverges (high refolding RMSD) are weeded out at the filtering step.

### 4. `design_folding` — refold the binder *alone*

| Topic                  | Detail                                                                                                       |
|------------------------|--------------------------------------------------------------------------------------------------------------|
| Input                  | `intermediate_designs_inverse_folded/`                                                                        |
| Output                 | `intermediate_designs_inverse_folded/refold_design_cif/*.cif`                                                 |
| Hydra config           | reuses `fold.yaml`                                                                                            |
| Active under           | `protein-anything`, `protein-small_molecule`, `protein-redesign`                                              |
| Skipped under          | `peptide-anything`, `nanobody-anything`, `antibody-anything` (the binder is too short / scaffolded for it to make sense) |

Used as an extra "does this thing fold *on its own*?" check. Adds the
metric set `filter_rmsd_design` and friends, which are referenced under
`--additional_filters 'filter_rmsd_design<2.5'` etc.

### 5. `affinity` — Boltz-2 affinity head (small molecule only)

| Topic                  | Detail                                                                                                       |
|------------------------|--------------------------------------------------------------------------------------------------------------|
| Input                  | `refold_cif/`                                                                                                 |
| Output                 | Per-design `affinity_*.json` written next to each refolded CIF                                                |
| Checkpoint             | `--affinity_checkpoint` (default `boltz2_aff.ckpt`)                                                          |
| Hydra config           | `src/boltzgen/resources/config/affinity.yaml`                                                                |
| Active under           | `protein-small_molecule` only (or any protocol if you pass `--steps affinity`)                                |

Outputs:

- `affinity_pred_value`: predicted `log10(IC50_µM)` — **lower = stronger binder**
- `affinity_probability_binary`: probability the ligand binds at all

Caps: ligand ≤ 128 heavy atoms (hard), ≤ 56 heavy atoms (training cap;
larger gets a `WARNING`).

### 6. `analysis` — CPU metrics computation

| Topic                  | Detail                                                                                                       |
|------------------------|--------------------------------------------------------------------------------------------------------------|
| Input                  | `refold_cif/` + `refold_design_cif/` + `intermediate_designs_inverse_folded/`                                  |
| Output                 | `aggregate_metrics_analyze.csv`, `per_target_metrics_analyze.csv`                                              |
| Hydra config           | `src/boltzgen/resources/config/analysis.yaml`                                                                |
| Knobs                  | `--config analysis num_processes=64`, `--config analysis liability_modality=peptide`, etc.                    |

Metrics computed include (see `analysis.yaml` for the full toggle list):

| Metric                       | Default | Meaning                                                              |
|------------------------------|---------|----------------------------------------------------------------------|
| `backbone_fold_metrics`      | on      | Refolding RMSD of binder backbone vs design.                          |
| `noncovalents_original`      | on      | PLIP non-covalents on the design structure.                            |
| `noncovalents_refolded`      | on      | PLIP non-covalents on the refolded complex.                            |
| `delta_sasa_original` /` _refolded` | on | Interface SASA (size of buried interface).                            |
| `largest_hydrophobic_refolded` | on    | Largest exposed hydrophobic patch (off for peptide / antibody / nanobody). |
| `liability_analysis`         | on      | Sequence liabilities: deamidation sites, oxidation sites, cleavage motifs, etc. |
| `run_clustering`             | off     | Hierarchical clustering of refold structures.                          |
| `diversity_*` / `novelty_*`  | off     | Cross-design diversity / novelty vs PDB.                              |
| `compute_lddts`              | off     | Per-residue lDDT (expensive).                                          |
| `sequence_recovery`          | off     | Only meaningful when `native:` is supplied (eval mode).               |
| `affinity_metrics`           | off     | On automatically under `protein-small_molecule`.                       |

You can switch the liability modality (`peptide` / `antibody`) and
peptide type (`linear` / `cyclic`):

```bash
boltzgen run spec.yaml \
  --config analysis liability_modality=antibody
```

### 7. `filtering` — rank, diversify, and write the final set

| Topic                  | Detail                                                                                                       |
|------------------------|--------------------------------------------------------------------------------------------------------------|
| Input                  | `aggregate_metrics_analyze.csv`                                                                               |
| Output                 | `final_ranked_designs/`                                                                                       |
| Hydra config           | `src/boltzgen/resources/config/filtering.yaml`                                                                |
| Wall time              | ~15 seconds. Re-run to your heart's content.                                                                  |

Outputs:

```
final_ranked_designs/
  intermediate_ranked_<N>_designs/      # top-N by quality only
  final_<budget>_designs/               # diversity-optimized via --alpha
  all_designs_metrics.csv               # all designs considered
  final_designs_metrics_<budget>.csv    # only the picked set
  results_overview.pdf                  # plots
```

See [`filtering.md`](filtering.md) for the full re-run / tune guide.

## Running only a subset of steps

```bash
# Just the design + IF steps (e.g., to evaluate IF separately)
boltzgen run spec.yaml --output OUT \
  --steps design inverse_folding --num_designs 2

# Refold only — assumes intermediate_designs_inverse_folded/ already exists
boltzgen run spec.yaml --output OUT --steps folding

# Filter only — recommended after every full run
boltzgen run spec.yaml --output OUT --steps filtering

# Filter only, with tuned knobs
boltzgen run spec.yaml --output OUT --steps filtering \
  --refolding_rmsd_threshold 3.0 \
  --filter_biased false \
  --additional_filters 'ALA_fraction<0.3' 'filter_rmsd_design<2.5' \
  --metrics_override plip_hbonds_refolded=4 \
  --alpha 0.2
```

`--steps` only restricts what gets *run*; it does not delete prior outputs.
Use the same `--output` directory across step-subsetted runs to chain them.
