# Advanced settings — every key explained

The `--advanced` JSON has 50+ keys. Most you never touch — pick a preset,
trust it. This page is the lookup when you do need to tune.

## Algorithm choice

| Key | Type | Notes |
|-----|------|-------|
| `design_algorithm` | one of `2stage` / `3stage` / `4stage` / `greedy` / `mcmc` | The hallucination schedule. **`4stage` is the default** for mini-proteins, `3stage` for peptides. |

| Algorithm | Schedule | Trade-off |
|-----------|----------|-----------|
| `2stage` | logits → pssm_semigreedy | Fastest, lowest quality |
| `3stage` | logits → softmax(logits) → one-hot | "Standard". Default for peptides. |
| `4stage` | logits → softmax(logits) → one-hot → pssm_semigreedy | Most extensive. Default. |
| `greedy` | Random mutations that decrease loss | Less GPU memory, slower, lower efficiency |
| `mcmc` | Random mutations à la Wicky et al. | Same memory profile as `greedy` |

`greedy` / `mcmc` are the GPU-memory escape hatch when `4stage` OOMs on
your target.

## AF2 model choice + recycles

| Key | Default | Notes |
|-----|---------|-------|
| `use_multimer_design` | `true` | If `true` → AF2-multimer for hallucination, AF2-ptm for reprediction (and vice-versa). Mixing model families is the cross-check. |
| `sample_models` | `true` | Sample random AF2 model params per trajectory to avoid overfitting. Recommended. |
| `num_recycles_design` | `1` | AF2 recycles during hallucination. |
| `num_recycles_validation` | `3` | AF2 recycles during reprediction. Larger = better predictions, slower. |

## Template handling (target flexibility)

| Key | Default | Effect when `true` |
|-----|---------|--------------------|
| `rm_template_seq_design` | `false` | Mask target sequence during hallucination → backbone allowed to move |
| `rm_template_seq_predict` | `false` | Mask target sequence during reprediction → reprediction can also re-arrange target |
| `rm_template_sc_design` | `false` | Strip target side chains during hallucination |
| `rm_template_sc_predict` | `false` | Strip target side chains during reprediction |

The `_flexible` modifier sets the first two `true`.

## Warm-start (rescue mode)

| Key | Default | Effect when `true` |
|-----|---------|--------------------|
| `predict_initial_guess` | `false` | Use the binder's hallucinated atom positions as the *starting* point for AF2 reprediction. Recommended whenever MPNN designs are looking good but failing the reprediction filter. |
| `predict_bigbang` | `false` | Push atom-position bias into AF2's structure module init. Use for large complexes (> ~600 aa total). |

The `_hardtarget` modifier sets `predict_initial_guess: true`.

## Hallucination iteration budget

| Key | Default | Notes |
|-----|---------|-------|
| `soft_iterations` | `75` | Soft logits — all 20 AAs at every position. The exploration phase. |
| `temporary_iterations` | `45` | Softmax — biased toward the top AA at each position. |
| `hard_iterations` | `5` | One-hot — single AA per position. The commitment phase. |
| `greedy_iterations` | `15` | Random PSSM mutations that decrease loss. |
| `greedy_percentage` | `1` | What % of binder length to mutate per greedy iteration. Set to `5` for the peptide preset. |

Doubling all four iteration budgets ≈ doubles trajectory wall-clock but
gives the optimizer more room. Use on stubborn targets after the easier
levers (`_mpnn`, `_hardtarget`, `_flexible`) failed.

## Design weights

These are the loss weights driving the hallucination. Higher = more
optimization pressure on that term.

| Key | Default | Meaning |
|-----|---------|---------|
| `weights_plddt` | `0.1` | Designed-chain pLDDT |
| `weights_pae_intra` | `0.4` | Within-binder PAE |
| `weights_pae_inter` | `0.1` | Binder ↔ target PAE (the interface) |
| `weights_con_intra` | `1.0` | Number of intra-binder contacts (compactness) |
| `weights_con_inter` | `1.0` | Number of binder ↔ target contacts (interface size) |
| `weights_iptm` | `0.05` | i_pTM (interface pTM) — gated by `use_i_ptm_loss` |
| `weights_rg` | `0.3` | Radius of gyration (compactness) — gated by `use_rg_loss` |
| `weights_helicity` | `-0.3` | + ⇒ helical, − ⇒ β-sheet, `0` = neutral. |
| `weights_termini_loss` | `0.1` | N–C terminal distance — gated by `use_termini_distance_loss`. Useful for grafting (force closed-loop binders) |

The `betasheet_*` presets push `weights_helicity` to `-2.0` for a hard β
bias.

| Toggle | Default | Effect |
|--------|---------|--------|
| `use_i_ptm_loss` | `true` | Adds `weights_iptm × (1 − i_pTM)` to the loss |
| `use_rg_loss` | `true` | Penalize loose / extended binders |
| `use_termini_distance_loss` | `false` | Push N– and C-termini together. Only when you specifically want graftable binders. |
| `random_helicity` | `false` | Sample `weights_helicity` ∈ [−1, 1] per trajectory. Use when target topology preference is unclear. |

## Contact geometry

| Key | Default | Meaning |
|-----|---------|---------|
| `intra_contact_distance` | `14.0` | Cβ–Cβ cutoff for intra-binder contacts (Å) |
| `inter_contact_distance` | `20.0` | Cβ–Cβ cutoff for binder–target contacts (Å) |
| `intra_contact_number` | `2` | Each "contact residue" should make this many intra contacts (excluding neighbours) |
| `inter_contact_number` | `2` | Same, for inter (interface) contacts |

Raising the inter distance makes the script consider a broader interface;
lowering forces tighter packing.

## β-sheet rescue

| Key | Default | Meaning |
|-----|---------|---------|
| `optimise_beta` | `true` | If trajectory ends with ≥ 15% β content, run the β-rescue settings below. |
| `optimise_beta_extra_soft` | `0` | Extra soft iterations to add |
| `optimise_beta_extra_temp` | `0` | Extra temporary iterations to add |
| `optimise_beta_recycles_design` | `3` | AF2 recycles during the β-rescue design |
| `optimise_beta_recycles_valid` | `3` | AF2 recycles during the β-rescue reprediction |

Costs wall-clock; rescues fragile β designs.

## Amino-acid restrictions

| Key | Default | Meaning |
|-----|---------|---------|
| `omit_AAs` | `"C"` | Comma-separated AAs to exclude. Defaults block cysteine (no accidental disulfides). |
| `force_reject_AA` | `false` | If `true`, designs containing any `omit_AAs` are **rejected outright** after MPNN. If `false`, MPNN may keep them when no alternative exists. The peptide preset turns this on. |

## MPNN

| Key | Default | Meaning |
|-----|---------|---------|
| `enable_mpnn` | `true` | Run ProteinMPNN at all. Set `false` for AF2-only design (rare, much worse). |
| `mpnn_fix_interface` | `true` | Freeze interface residues from the hallucinated trajectory; MPNN only redesigns non-interface residues. The `_mpnn` modifier flips this to `false`. |
| `num_seqs` | `20` (`10` for peptide) | MPNN sequences sampled per trajectory. |
| `max_mpnn_sequences` | `2` | Maximum accepted MPNN sequences per trajectory to save (caps how many designs from one good backbone can survive). |
| `sampling_temp` | `0.1` | MPNN sampling temperature. `0.0` = argmax (no diversity); `0.5+` = high diversity. |
| `backbone_noise` | `0.00` | Backbone noise during MPNN sampling. `0.00–0.02` typical. |
| `model_path` | `"v_48_020"` | ProteinMPNN checkpoint. Leave as-is unless you have a custom checkpoint. |
| `mpnn_weights` | `"soluble"` | `"original"` ProteinMPNN or `"soluble"` (SolubleMPNN). Soluble is the default and is biased away from membrane / hydrophobic surfaces. |
| `save_mpnn_fasta` | `false` | Write FASTA per MPNN sequence (the sequences are already in `mpnn_design_stats.csv`). |

## Run-control / monitoring

| Key | Default | Meaning |
|-----|---------|---------|
| `max_trajectories` | `false` | Cap total trajectories. `false` = unlimited. Used mostly for benchmarking. |
| `enable_rejection_check` | `true` | If `true`, after `start_monitoring` trajectories, compute `accepted_designs / trajectory_n` and abort if it's below `acceptance_rate`. Save you from week-long futile runs. |
| `acceptance_rate` | `0.01` (peptide: `0.1`) | The minimum fraction of trajectories that must yield an accepted design once monitoring kicks in. |
| `start_monitoring` | `600` (peptide: `1000`; `_hardtarget`: `300`) | After this many trajectories, start checking acceptance rate. Do not set too low — early trajectories may legitimately fail more often. |

## Disk-saving toggles

(Defaults are sensible — only change if you want to keep more.)

| Key | Default | Meaning |
|-----|---------|---------|
| `remove_unrelaxed_trajectory` | `true` | Delete the unrelaxed Trajectory PDB after PyRosetta relax. |
| `remove_unrelaxed_complex` | `true` | Delete unrelaxed MPNN complex PDB after scoring. |
| `remove_binder_monomer` | `true` | Delete binder-only repredictions after extracting `Binder_RMSD`. |
| `zip_animations` | `true` | Gzip `Trajectory/Animation/` at end of run. |
| `zip_plots` | `true` | Gzip `Trajectory/Plots/` at end of run. |
| `save_trajectory_pickle` | `false` | Save raw ColabDesign pickle per trajectory. Each is hundreds of MB. |
| `save_design_animations` | `true` | Generate the trajectory animation HTML. |
| `save_design_trajectory_plots` | `true` | Generate the trajectory metric plot PNGs. |

## Auto-discovered paths

These are filled in by `perform_advanced_settings_check` at script start;
leave them empty in your JSON.

| Key | Default | Meaning |
|-----|---------|---------|
| `af_params_dir` | `""` (auto → `<install>/params/`) | AF2 weights directory. |
| `dssp_path` | `""` (auto → `<install>/functions/dssp`) | DSSP binary. |
| `dalphaball_path` | `""` (auto → `<install>/functions/DAlphaBall.gcc`) | DAlphaBall binary (used by PyRosetta `-holes:dalphaball`). |

## Preset matrix at a glance

```text
                   base                     +mpnn   +flexible   +hardtarget
                   ─────────────────────────────────────────────────────────
default_4stage     mini-protein binder      MPNN     target      warm-start
                   (alpha bias -0.3)        free    flexible    reprediction
                                            ifc     (mask seq)
betasheet_4stage   beta-sheet binder        ...     ...          ...
                   (helicity -2.0,
                    weights_con -)
peptide_3stage     peptide binder           ...     ...          (no _hardtarget)
                   (helix bias +0.95,
                    force_reject_AA,
                    3stage, num_seqs 10)
```

Pick a row + any subset of columns. The naming convention concatenates
the modifiers in this fixed order: `<base>_<mpnn>_<flexible>_<hardtarget>`.

## Tuning playbook

| Symptom | Lever |
|---------|-------|
| OOM during hallucination | Trim target PDB; switch to `greedy` algorithm. |
| 0 trajectories pass `LowConfidence` triage | Raise `soft_iterations` / `temporary_iterations`. Try `_flexible`. |
| Trajectories pass triage but MPNN reprediction fails on i_pTM | Switch to `_hardtarget`; raise `num_recycles_validation` to `5–8`. |
| Trajectories pass everything except `Hotspot_RMSD` | Hotspot is wrong / too big. Narrow it, or try `null`. |
| All accepted designs are alpha-helical but you want diversity | `random_helicity: true` for one campaign; or split into a `default_*` and `betasheet_*` run. |
| All designs are too floppy / long | Raise `weights_rg` (e.g. `0.6`); lower `lengths` max. |
| All accepted designs cluster too tightly | Raise `sampling_temp` (`0.2–0.3`); raise `num_seqs`; relax `intra_contact_*`. |
| Auto-abort fires too early | Raise `start_monitoring` (e.g. `1500`); lower `acceptance_rate` (e.g. `0.005`); or disable the check entirely with `enable_rejection_check: false`. |
