# Inputs — the three JSON files

Every BindCraft run is fully described by three JSONs. Two have defaults,
one is mandatory.

```bash
python bindcraft.py \
    --settings  ./settings_target/<your_target>.json     # required
    --filters   ./settings_filters/<preset>.json         # default: default_filters.json
    --advanced  ./settings_advanced/<preset>.json        # default: default_4stage_multimer.json
```

## 1. `--settings` — the target JSON (required)

Lives under `settings_target/`. Tiny — seven keys.

```json
{
  "design_path":              "/abs/path/to/output/dir/",
  "binder_name":              "PDL1",
  "starting_pdb":             "/abs/path/to/target.pdb",
  "chains":                   "A",
  "target_hotspot_residues":  "56",
  "lengths":                  [65, 150],
  "number_of_final_designs":  100
}
```

| Key | Type | Meaning |
|-----|------|---------|
| `design_path` | abs path (str) | Where every output dir + CSV is written. Should not exist or should be a previous BindCraft run (re-running with the same path **resumes** the campaign). |
| `binder_name` | str | Prefix for every design file: `<binder_name>_l<length>_s<seed>[_mpnn<n>][_model<m>].pdb` |
| `starting_pdb` | abs path (str) | The target PDB. **Trim it!** Bigger = more GPU + more deformed binders. |
| `chains` | str | Which chains in `starting_pdb` to keep as the target. Everything else is ignored. e.g. `"A"`, `"AB"`. |
| `target_hotspot_residues` | str / `null` | Where on the target the binder should bind. See the syntax table below. |
| `lengths` | `[min, max]` | Range of binder lengths to sample uniformly per trajectory. Typical: `[65, 150]` for mini-proteins, `[8, 25]` for peptides. |
| `number_of_final_designs` | int | The script stops when this many designs have been **Accepted**. The shipped PDL1 example targets 100; the README recommends 100 final → order 5–20. |

### `target_hotspot_residues` syntax

| Value | Effect |
|-------|--------|
| `null` | Let AF2 choose the binding site. Good for cryptic pockets / unknown epitopes; bad for surface targets with many false epitopes. |
| `"56"` | Single residue (defaults to the first kept chain). |
| `"1-20"` | Residue range on the first chain. |
| `"1,2-10"` | Mix of singletons and ranges. |
| `"A1-10,B1-20"` | Chain-prefixed: residues 1–10 of chain A *and* 1–20 of chain B. |
| `"A"` | All residues of chain A — same as bind-anywhere-on-A. |

**Picking a hotspot:** small patches > big ones. A 4–8 residue patch
defining the surface epitope is ideal. The bigger the hotspot, the more
the design search wanders.

## 2. `--filters` — the filter JSON

Lives under `settings_filters/`. The script will use
`./settings_filters/default_filters.json` if you omit `--filters`.

The structure is a flat dict of `{ "<metric>": { "threshold": <num|null>, "higher": <bool> } }`:

```json
{
  "Average_pLDDT":      { "threshold": 0.8,  "higher": true  },
  "1_pLDDT":            { "threshold": 0.8,  "higher": true  },
  "Average_i_pTM":      { "threshold": 0.5,  "higher": true  },
  "Average_dG":         { "threshold": 0,    "higher": false },
  "Average_ShapeComplementarity": { "threshold": 0.6, "higher": true },
  "Average_n_InterfaceHbonds":    { "threshold": 3,   "higher": true }
}
```

- `threshold: null` → disable that filter (still recorded, just not checked).
- `higher: true` → metric must be `≥ threshold` to pass.
- `higher: false` → metric must be `≤ threshold` to pass.

Each metric exists in 6 flavors: `Average_<metric>` (across the 5 AF2
models) and `1_<metric>` … `5_<metric>` (per model). Setting only models
1+2 with thresholds and leaving 3–5 `null` is the standard "two-model
agreement" pattern.

The special `InterfaceAAs` block is **per amino acid** — it caps how many
copies of a given AA may appear at the interface. The shipped defaults
cap K and M at 3 each across all 5 models. Disable by setting `threshold: null`.

`MPNN_score` and `MPNN_seq_recovery` are kept `null` in every preset —
they vary wildly with target size and aren't useful as hard filters.

Full metric catalog and which presets disable which → `filters.md`.

## 3. `--advanced` — the advanced JSON

Lives under `settings_advanced/`. Default if omitted:
`./settings_advanced/default_4stage_multimer.json`.

**Pick by composing**: one base × any subset of `_mpnn` / `_flexible` /
`_hardtarget` modifiers. The 20+ shipped presets cover all combinations.

| Base | When |
|------|------|
| `default_4stage_multimer` | First try. Mini-protein binder, AF2-multimer hallucination, gentle alpha bias (`weights_helicity: -0.3`), 4-stage algorithm. |
| `betasheet_4stage_multimer` | Target wants a β-sheet binder. Strong β bias (`weights_helicity: -2.0`), lower contact weights (`weights_con_*: 0.4–0.5`). |
| `peptide_3stage_multimer` | Short peptide binder (8–25 aa). Strong α bias (`weights_helicity: 0.95`), 3-stage algorithm, `force_reject_AA: true` to block Cys hard, looser acceptance monitoring (`acceptance_rate: 0.1`, `start_monitoring: 1000`). |

| Modifier | Sets |
|----------|------|
| `_mpnn` | `mpnn_fix_interface: false` (MPNN may redesign interface residues; otherwise they are frozen to what AF2 hallucinated). |
| `_flexible` | `rm_template_seq_design: true, rm_template_seq_predict: true` (target template sequence masked → backbone flexibility allowed). |
| `_hardtarget` | `predict_initial_guess: true` (warm-start the AF2 reprediction from the binder's hallucinated atom positions — rescues failures where the binder "evaporates" during repredict on rigid targets). |

Example combinations the repo ships:
- `default_4stage_multimer.json` — first attempt
- `default_4stage_multimer_mpnn.json` — let MPNN re-route the interface
- `default_4stage_multimer_flexible.json` — flexible target
- `default_4stage_multimer_hardtarget.json` — warm-start repredict
- `default_4stage_multimer_mpnn_flexible.json` — both
- `default_4stage_multimer_mpnn_flexible_hardtarget.json` — all three
- `default_4stage_multimer_hardtarget.json` — just warm-start
- … and all 8 combinations also exist under `betasheet_*` and 4 under `peptide_3stage_*`.

Full key-by-key meaning of every advanced setting → `advanced-settings.md`.

## Recommended starting flow

1. **Trim the target PDB** to the smallest reasonable form (one or two
   chains, one domain).
2. **Pick the hotspot** as a small patch (`"A56-63"` style). When in
   doubt, start with `null` and look at the WrongHotspot failure column
   after ~50 trajectories.
3. **Start with**:
   ```bash
   --settings  ./settings_target/<target>.json
   --filters   ./settings_filters/default_filters.json
   --advanced  ./settings_advanced/default_4stage_multimer.json
   ```
4. Run 200–500 trajectories. Check the failure CSV.
5. If acceptance is < 1% **and** the failure CSV is dominated by
   `i_pTM` / `Hotspot_RMSD` failures → switch to `_hardtarget`.
6. If the target is rigid / flat / polar → also try `_flexible`.
7. If the binder topology is wrong (lots of loop, no fold) → try the
   `betasheet_*` base if you want β, or tune `weights_helicity` /
   `weights_rg`.
8. If you still get nothing → drop to `relaxed_filters.json` to confirm
   the pipeline is producing *something* before tightening filters again.

Detailed per-setting tuning advice → `advanced-settings.md`.
