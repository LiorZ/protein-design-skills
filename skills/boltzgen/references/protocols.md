# Protocols

`--protocol` is BoltzGen's main "preset" knob. It selects:

1. Which pipeline steps run by default.
2. Per-step config overrides for analysis + filtering.
3. The default `--inverse_fold_avoid` letters (Cys is excluded for
   peptide / antibody / nanobody by default).

The full table:

| Protocol                  | Designs                       | Targets                                      | Steps included         | Inverse-fold avoid | Notes                                                       |
|---------------------------|-------------------------------|----------------------------------------------|------------------------|--------------------|-------------------------------------------------------------|
| `protein-anything`        | Mini-proteins                 | Anything (protein / peptide / IDR / DNA / RNA) | All seven, including `design_folding` | none | The default. `design_folding` re-folds the binder without the target as a confidence check. |
| `peptide-anything`        | (Cyclic) peptides             | Anything                                     | All except `design_folding`            | `C`                | Cysteines disallowed in IF. Largest-hydrophobic-patch metric off. Tighter `refolding_rmsd_threshold=2`, higher diversity `alpha=0.01`. |
| `protein-small_molecule`  | Mini-proteins                 | Small molecule (CCD or SMILES)               | All seven, including `affinity`        | none               | `affinity` step on (Boltz-2). Filtering uses affinity-aware metrics. |
| `nanobody-anything`       | Nanobody / VHH CDR loops      | Protein                                      | All except `design_folding`            | `C`                | CDR design with scaffold libraries; largest-hydrophobic-patch off. |
| `antibody-anything`       | Fab CDR loops (heavy + light) | Protein                                      | All except `design_folding`            | `C`                | Same settings as nanobody-anything; you typically pass *paired* scaffolds. |
| `protein-redesign`        | Sequence redesign of existing | Itself (symmetric dimer / monomer / etc.)    | Custom — skips `design_folding`, uses `design_mask` for target/template | none | For optimizing existing complexes. Filtering metrics replaced with iptm/ptm/iiptm/etc. |

All other behavior (number of designs, filtering budget / alpha, kernels,
checkpoints) is independent of protocol and controlled by flags.

## What each protocol actually overrides

Verbatim from `protocol_configs` in `src/boltzgen/cli/boltzgen.py`:

### `protein-anything`

```python
{}    # the base config IS protein-anything
```

### `peptide-anything`

```python
{
  "analysis": ["largest_hydrophobic=false", "largest_hydrophobic_refolded=false"],
  "filtering": [
    "filter_cysteine=true",
    "alpha=0.01",
    "refolding_rmsd_threshold=2",
  ],
}
```

Plus the default `--inverse_fold_avoid` becomes `C`, and the
`design_folding` step is removed.

### `protein-small_molecule`

```python
{
  "analysis": ["affinity_metrics=true"],
  "filtering": ["use_affinity=true"],
}
```

The `affinity` step runs with Boltz-2's affinity head and outputs a
predicted log10(IC50) and binder probability per design.

### `nanobody-anything` and `antibody-anything`

```python
{
  "analysis": ["largest_hydrophobic=false", "largest_hydrophobic_refolded=false"],
  "filtering": ["filter_cysteine=true"],
}
```

Same `--inverse_fold_avoid C` as peptides; `design_folding` removed.

### `protein-redesign`

```python
{
  "folding": ["data.design_mask_templates=true"],
  "analysis": ["use_design_mask_for_target=true"],
  "filtering": [
    "metrics_override={design_to_target_iptm: null, neg_min_design_to_target_pae: null, design_ptm: null, plip_hbonds_refolded: null, plip_saltbridge_refolded: null, delta_sasa_refolded: null, plip_hbonds: null, plip_saltbridge: null, delta_sasa_original: null, design_residue_iptm: 1, iptm: 2, ptm: 3, neg_filter_rmsd_design: 4}",
  ],
}
```

Drops binder-vs-target metrics (there isn't a clean target/binder
split) and ranks by `design_residue_iptm` → `iptm` → `ptm` →
`neg_filter_rmsd_design`. Uses `design_mask` rather than the
target/template chain split.

## Choosing a protocol — quick decisions

| Question                                                                | Answer                                  |
|-------------------------------------------------------------------------|------------------------------------------|
| Target is a protein, want a mini-protein binder, no chemistry           | `protein-anything`                       |
| Target is a small molecule (SMILES or CCD)                              | `protein-small_molecule`                 |
| Want a peptide (any topology — linear, cyclic, disulfide, stapled)      | `peptide-anything`                       |
| Want nanobody CDR loops                                                 | `nanobody-anything`                      |
| Want Fab CDR loops (paired heavy + light)                               | `antibody-anything`                      |
| Want to redesign an existing complex (monomer, dimer, fusion, scaffold) | `protein-redesign`                       |
| Bind DNA / RNA / nucleic acid                                           | `protein-anything` (works on any target) |
| Bind a disordered peptide (sequence only, no structure)                 | `protein-anything`                       |
| Just IF an existing structure (no diffusion)                            | Any protocol + `--only_inverse_fold`     |

## Protocol gotchas

- **Protocols are not symmetric across `--steps`.** `peptide-anything`
  removes `design_folding` from the *default* step list. If you pass
  `--steps design_folding`, it will run, but the `analysis` config will
  have already been tuned for the no-`design_folding` flow.
- **`--inverse_fold_avoid ""` brings back cysteines** for the peptide /
  antibody / nanobody flows. Required if you want to add new disulfide
  chemistry that BoltzGen doesn't already see from `constraints`.
- **`protein-small_molecule` only makes sense with at least one `ligand`
  entity** (CCD or SMILES). Otherwise the affinity head has nothing to
  score.
- **`protein-redesign` requires explicit `design:` blocks** inside the
  `file` entity. Without them no residues are flagged designable and the
  step does nothing.
- **Overriding protocol defaults** is always allowed via `--config STEP
  k=v` — your override wins. E.g.:

```bash
boltzgen run spec.yaml \
  --protocol peptide-anything \
  --config filtering refolding_rmsd_threshold=3.0 alpha=0.05
```

is fine, even though the protocol default would have been 2.0 and 0.01.
