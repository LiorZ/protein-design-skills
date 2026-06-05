# Outputs

Everything lands under `target_settings["design_path"]`. Re-running with
the same `design_path` **resumes** the campaign — existing trajectory PDBs
are skipped and the accepted-count is read from `Accepted/`.

## Directory tree

```text
<design_path>/
├── trajectory_stats.csv        # one row per trajectory that survived triage
├── mpnn_design_stats.csv       # one row per MPNN sequence (per trajectory × accepted MPNN sequences)
├── final_design_stats.csv      # one row per Accepted design, with Rank column
├── failure_csv.csv             # single-row counter: which filter killed how many designs
├── Trajectory/
│   ├── Relaxed/                # AF2-hallucinated + PyRosetta-relaxed binder PDBs (kept)
│   ├── LowConfidence/          # Trajectories AF2 flagged "LowConfidence"
│   ├── Clashing/               # Trajectories AF2 flagged "Clashing"
│   ├── Animation/              # GIF/HTML per trajectory (zipped at end → Trajectory_Animation.zip)
│   ├── Plots/                  # PNG metric plots (zipped at end → Trajectory_Plots.zip)
│   └── Pickle/                 # Full ColabDesign pickles — ONLY if save_trajectory_pickle=true
├── MPNN/
│   ├── Sequences/              # FASTA per MPNN sequence — ONLY if save_mpnn_fasta=true
│   ├── Relaxed/                # AF2-repredicted, PyRosetta-relaxed COMPLEX PDBs
│   └── Binder/                 # AF2-repredicted BINDER-ALONE PDBs (used for Binder_RMSD)
├── Accepted/                   # PDBs of designs passing every filter
│   ├── Ranked/                 # The same PDBs renamed: <rank>_<binder_name>_model<n>.pdb
│   ├── Animation/              # Copies of the trajectory animations of accepted designs
│   ├── Plots/                  # Copies of the trajectory plots of accepted designs
│   └── Pickle/                 # Copies of trajectory pickles (only if saving them)
└── Rejected/                   # AF2 prediction passed but a non-AF2 filter killed it
```

## Naming convention

```
<binder_name>_l<length>_s<seed>                          ← trajectory
<binder_name>_l<length>_s<seed>_mpnn<n>                  ← MPNN sequence
<binder_name>_l<length>_s<seed>_mpnn<n>_model<m>.pdb     ← AF2 model m (1..5) reprediction
<rank>_<binder_name>_l<length>_s<seed>_mpnn<n>_model<m>.pdb   ← in Accepted/Ranked/
```

`length` and `seed` come from the per-trajectory random sample; `n` is the
MPNN sequence index within that trajectory; `m ∈ {1, …, 5}` is the AF2
model number. The **best model per design** (highest pLDDT across the 5)
is what gets copied into `Accepted/` and then ranked.

## CSV files

### `trajectory_stats.csv` (one row per trajectory)

Written by `bindcraft.py` after PyRosetta relax of the hallucinated
binder. Columns (in order):

```
Design_name, Algorithm, Length, Seed, Helicity, Target_Hotspot, Sequence,
Interface_Residues,
pLDDT, pTM, i_pTM, pAE, i_pAE,
i_pLDDT, ss_pLDDT, Unrelaxed_Clashes, Relaxed_Clashes,
Binder_Energy_Score, Surface_Hydrophobicity, ShapeComplementarity, PackStat,
dG, dSASA, dG/dSASA, Interface_SASA_%, Interface_Hydrophobicity,
n_InterfaceResidues, n_InterfaceHbonds, InterfaceHbondsPercentage,
n_InterfaceUnsatHbonds, InterfaceUnsatHbondsPercentage,
Interface_Helix%, Interface_BetaSheet%, Interface_Loop%,
Binder_Helix%, Binder_BetaSheet%, Binder_Loop%,
InterfaceAAs, Target_RMSD,
TrajectoryTime, SeqNotes, Settings, Filters, AdvancedSettings
```

The trajectory step has **only one** AF2 prediction (the hallucination),
so there are no `Average_*` / `1_*` … `5_*` flavors here.

### `mpnn_design_stats.csv` (one row per MPNN sequence)

Written after each MPNN sequence is repredicted, scored, and filter-checked.
Per-metric columns appear with an `Average_` flavor and then `1_…5_` (one
per AF2 model). Roughly:

```
Design_name, Algorithm, Length, Seed, Helicity, Target_Hotspot,
Sequence, Interface_Residues, MPNN_score, MPNN_seq_recovery,
Average_pLDDT, 1_pLDDT, 2_pLDDT, 3_pLDDT, 4_pLDDT, 5_pLDDT,
Average_pTM, 1_pTM, …,
Average_i_pTM, …,
Average_pAE, …,
Average_i_pAE, …,
Average_i_pLDDT, …,
Average_ss_pLDDT, …,
Average_Unrelaxed_Clashes, …,
Average_Relaxed_Clashes, …,
Average_Binder_Energy_Score, …,
Average_Surface_Hydrophobicity, …,
Average_ShapeComplementarity, …,
Average_PackStat, …,
Average_dG, …, Average_dSASA, …, Average_dG/dSASA, …,
Average_Interface_SASA_%, …,
Average_Interface_Hydrophobicity, …,
Average_n_InterfaceResidues, …,
Average_n_InterfaceHbonds, …,
Average_InterfaceHbondsPercentage, …,
Average_n_InterfaceUnsatHbonds, …,
Average_InterfaceUnsatHbondsPercentage, …,
Average_Interface_Helix%, …, Average_Interface_BetaSheet%, …, Average_Interface_Loop%, …,
Average_Binder_Helix%, …, Average_Binder_BetaSheet%, …, Average_Binder_Loop%, …,
Average_InterfaceAAs, 1_InterfaceAAs, …,
Average_Hotspot_RMSD, …, Average_Target_RMSD, …,
Average_Binder_pLDDT, …, Average_Binder_pTM, …, Average_Binder_pAE, …,
Average_Binder_RMSD, 1_Binder_RMSD, …,
MpnnTime, SeqNotes, Settings, Filters, AdvancedSettings
```

This is what you load with pandas to do downstream analysis.

### `final_design_stats.csv` (one row per Accepted design)

Same columns as `mpnn_design_stats.csv` but prefixed with a `Rank`
column. The Rank is recomputed each time the script reaches
`number_of_final_designs` — it sorts by `Average_i_pTM` descending. The
PDBs in `Accepted/Ranked/` are renamed to match.

### `failure_csv.csv` (single-row counter)

Tracks how many designs failed each filter. Columns include:

```
Trajectory_logits_pLDDT, Trajectory_softmax_pLDDT, Trajectory_one-hot_pLDDT,
Trajectory_final_pLDDT, Trajectory_Contacts, Trajectory_Clashes,
Trajectory_WrongHotspot,
<every filter metric without the Average_/N_ prefix>,
InterfaceAAs_A, InterfaceAAs_C, …, InterfaceAAs_Y
```

Read with pandas, sort descending — the dominant column tells you what
to fix. See `references/filters.md` for the "which column → which lever"
table.

## What to look at first

After ~50 trajectories on a new target:

1. `failure_csv.csv` — which threshold is killing the most designs?
2. Count of files in `Trajectory/Relaxed/` vs. `Trajectory/LowConfidence/` + `Trajectory/Clashing/` — is hallucination even getting through? If most trajectories are LowConfidence, the issue is the hallucination step, not the filters.
3. Count of files in `Accepted/` vs. `Rejected/` — how often does a passing trajectory turn into an accepted design?
4. If `Accepted/` is empty after 500–1000 trajectories: switch to `relaxed_filters.json` (or `no_filters.json`) to verify the pipeline is producing *anything*, then re-tighten incrementally.

## Hand-off

For experimental ordering:

1. `final_design_stats.csv` sorted by `Average_i_pTM` (or your preferred composite).
2. Pick 5–20 from `Accepted/Ranked/`.
3. Cross-validate the top picks with an **independent** structure predictor: `boltz`, `chai-lab`, `protenix`, `esm-biohub` (ESMFold2), or `fair-esm` (ESMFold). Two AF3-class agreement is a strong signal.
4. For each pick: run `placer` to refine the interface side chains and double-check the score.
5. For diversity, optionally cluster `Accepted/Ranked/*.pdb` with foldseek before ordering — ipTM is a binding predictor, not a diversity ranker.
