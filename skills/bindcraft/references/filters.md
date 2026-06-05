# Filters — what counts as a hit

A filter JSON is a flat dict: `{ "<metric>": { "threshold": <num|null>, "higher": <bool> } }`.

```jsonc
{
  "Average_pLDDT":     { "threshold": 0.8, "higher": true  },  // pass if Average_pLDDT >= 0.8
  "Average_dG":        { "threshold": 0,   "higher": false },  // pass if Average_dG <= 0
  "Average_Binder_pLDDT": { "threshold": null, "higher": true }  // disabled
}
```

- `threshold: null` → disable that filter (the value is still recorded).
- `higher: true` → pass when `metric >= threshold`.
- `higher: false` → pass when `metric <= threshold`.

A design must pass **every non-null filter** to land in `Accepted/`.
Failing metrics are counted in `failure_csv.csv` so you can see which
filter is the bottleneck.

## Average vs. per-model

Every AF2 metric is computed for **each of the 5 AF2 models** during
reprediction, **and** averaged across them. So each metric appears in 6
flavors:

```
Average_<metric>      # the average over all 5 models
1_<metric>            # model 1
2_<metric>            # model 2
3_<metric>            # model 3 (commonly disabled in defaults)
4_<metric>            # model 4 (commonly disabled in defaults)
5_<metric>            # model 5 (commonly disabled in defaults)
```

The shipped defaults require **Average + model 1 + model 2** to pass —
"two-model agreement is the bar". The 3/4/5 model filters are mostly
left `null` to avoid over-rejecting.

## The metric catalog

### AF2 confidence (binder + target complex)

| Metric | Range | Default `threshold` | `higher` |
|--------|-------|---------------------|----------|
| `pLDDT` | 0–1 | 0.8 | true |
| `pTM` | 0–1 | 0.55 | true |
| `i_pTM` | 0–1 | 0.5 (relaxed: 0.4) | true |
| `pAE` | 0–1 (normalized by n/31) | null | false |
| `i_pAE` | 0–1 (normalized by n/31) | 0.35 (relaxed: 0.3) | false |
| `i_pLDDT` | 0–1 | null | true |
| `ss_pLDDT` | 0–1 | null | true |

`i_pTM` ≥ 0.5 (default) is the binary "this is probably a real binder" line.
`i_pTM` ≥ 0.85 generally indicates very confident interface.

### AF2 confidence (binder alone)

| Metric | Default `threshold` | `higher` |
|--------|---------------------|----------|
| `Binder_pLDDT` | 0.8 | true |
| `Binder_pTM` | null | true |
| `Binder_pAE` | null | false |
| `Binder_RMSD` | 3.5 (peptide: 2.5) | false |

`Binder_RMSD` is the RMSD between the binder predicted in isolation and
the binder as predicted in the complex — high values mean the binder
"only folds when bound", which is usually a red flag.

### Clashes

| Metric | Default `threshold` | `higher` |
|--------|---------------------|----------|
| `Unrelaxed_Clashes` | null | false |
| `Relaxed_Clashes` | null | false |

Default presets leave these `null` because PyRosetta relax usually fixes
clashes. If you skip relax (you should not), tighten these.

### PyRosetta interface scores

| Metric | Range | Default | `higher` |
|--------|-------|---------|----------|
| `Binder_Energy_Score` | REU | 0 | false |
| `Surface_Hydrophobicity` | 0–1 | 0.35 (relaxed: 0.5) | false |
| `ShapeComplementarity` | 0–1 | 0.6 / 0.55 | true |
| `PackStat` | 0–1 | null | true |
| `dG` | REU | 0 | false |
| `dSASA` | Å² | 1 (basically always passes; SC and dG are the actual quality bar) | true |
| `dG/dSASA` | REU/Å² | null | false |
| `Interface_SASA_%` | 0–100 | null | true |
| `Interface_Hydrophobicity` | 0–1 | null | true |
| `n_InterfaceResidues` | int | 7 (peptide: 4) | true |
| `n_InterfaceHbonds` | int | 3 (peptide: 1) | true |
| `InterfaceHbondsPercentage` | 0–1 | null | true |
| `n_InterfaceUnsatHbonds` | int | 4 (peptide: 3) | false |
| `InterfaceUnsatHbondsPercentage` | 0–1 | null | false |

`dG < 0` is the "energetically favourable interface" line. `SC > 0.6`
and `Unsat-Hbonds < 4` are the shape-quality lines.

### Secondary structure / topology

| Metric | Default | `higher` |
|--------|---------|----------|
| `Interface_Helix%` | null | true |
| `Interface_BetaSheet%` | null | true |
| `Interface_Loop%` | null | false |
| `Binder_Helix%` | null | true |
| `Binder_BetaSheet%` | null | true |
| `Binder_Loop%` | 90 | false |

`Binder_Loop% ≤ 90` (default) rejects designs that are basically random
loop — anything from a real fold will be well below 90% loop. Inverted
sense (`higher: false`) is correct here despite the name.

### `InterfaceAAs` — amino-acid composition caps

```json
"Average_InterfaceAAs": {
    "A": { "threshold": null, "higher": false },
    ...
    "K": { "threshold": 3,    "higher": false },   // ≤ 3 K's at interface
    "M": { "threshold": 3,    "higher": false },   // ≤ 3 M's at interface
    ...
}
```

`higher: false` here means *cap* (≤). Defaults limit K and M to ≤ 3 each
across all models — these are surrogates for "too many positive charges
clustered at the interface" (K) and "redox-prone interface" (M). To
disable, set the per-AA `threshold: null`.

### Geometry

| Metric | Default | `higher` |
|--------|---------|----------|
| `Hotspot_RMSD` | 6 (peptide: 3) | false |
| `Target_RMSD` | null | false |

`Hotspot_RMSD` is the unaligned RMSD of the **binder** between the
hallucinated trajectory and the AF2-repredicted complex — high values
mean the binder slid off the intended site during reprediction.

`Target_RMSD` is the RMSD of the **target** between the input PDB and
the AF2-repredicted complex — high values mean AF2 deformed the target,
which usually indicates the binder isn't really binding.

### MPNN

| Metric | Default | `higher` |
|--------|---------|----------|
| `MPNN_score` | null | false |
| `MPNN_seq_recovery` | null | false |

Always left `null` — MPNN scores depend heavily on protein size and aren't
useful as hard cutoffs.

## The five preset filter files

| Preset | i_pTM | i_pAE | SC | Hotspot_RMSD | Surface_Hydrophobicity | When to use |
|--------|-------|-------|----|--------------|------------------------|-------------|
| `default_filters.json` | 0.5 | 0.35 | 0.6 (avg) / 0.55 (per-model) | 6 | 0.35 | First attempt, mini-protein binders against ordinary targets |
| `relaxed_filters.json` | 0.45 | 0.4 | 0.55 / 0.5 | 8 | 0.4 | Difficult targets where `default_filters` accepts < 1% |
| `peptide_filters.json` | 0.4 | 0.3 | 0.55 / 0.5 | 3 | 0.5 | Peptide binders (smaller, tighter site, more compositional latitude) |
| `peptide_relaxed_filters.json` | 0.35 | 0.35 | 0.5 / 0.45 | 4 | 0.55 | Difficult peptide-binder targets |
| `no_filters.json` | every threshold `null` | — | — | — | — | Sanity check — see what AF2 actually produces before tightening |

(Approximate ranges — diff the JSONs for exact values.)

## Editing filters mid-campaign

Filters are read **at script start** and stored in
`failure_csv.csv` once. Editing the filter JSON mid-run will *not* update
the in-memory thresholds, but **will** affect the new failure-CSV created
on a fresh `design_path`. The accepted designs from before the edit
remain in `Accepted/`. Best practice:

- Stop the run.
- Move (don't delete) the current campaign to a snapshot dir.
- Start a fresh `design_path` with the new filters.

To **re-rank** an existing campaign without redesigning, write a small
script that re-checks `mpnn_design_stats.csv` against a new filter dict
and copies the passing rows into a new accepted folder. The repo does
not ship this — `examples/recipes.md` has a starter snippet.

## Failure CSV — your most useful diagnostic

`failure_csv.csv` is a single-row counter dictionary tracking how often
each metric killed a design. Columns include the seven trajectory-level
killers — `Trajectory_logits_pLDDT`, `Trajectory_softmax_pLDDT`,
`Trajectory_one-hot_pLDDT`, `Trajectory_final_pLDDT`, `Trajectory_Contacts`,
`Trajectory_Clashes`, `Trajectory_WrongHotspot` — plus every filter metric
without the model prefix.

After ~50 trajectories, look at which columns are dominating:

| Dominant column | Likely cause | Fix |
|-----------------|--------------|-----|
| `Trajectory_*_pLDDT` | Hallucination can't fold confidently | Raise iteration budget; try `_flexible`; try a different `weights_helicity` |
| `Trajectory_Clashes` | AF2 cramming a binder where it doesn't fit | Smaller `lengths`; trim target; smaller hotspot |
| `Trajectory_WrongHotspot` | AF2 keeps binding elsewhere | Narrower hotspot; or accept that this is the real binding site |
| `i_pTM` / `i_pAE` | MPNN sequences aren't predicted as binders | `_hardtarget` warm-start; raise `num_recycles_validation` |
| `Hotspot_RMSD` | Binder slides off during reprediction | `_hardtarget`; narrower hotspot |
| `ShapeComplementarity` | Loose interface | Raise `weights_con_inter`; lower `inter_contact_distance` |
| `n_InterfaceHbonds` | Hydrophobic, polar-poor interface | Hard to fix — usually a property of the target |
| `Binder_RMSD` | Binder only folds when bound | Lower `lengths` max; raise `weights_plddt` |
| `Binder_Loop%` | Designs aren't folded | Same as `Trajectory_*_pLDDT` — hallucination can't fold; tune weights / try a different topology bias |
