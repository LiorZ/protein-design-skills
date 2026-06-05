# BindCraft examples

Two artefacts:

| File | What it is |
|------|-----------|
| `PDL1_target.json` | Drop-in target config based on the shipped PDL1 example. Adapt `design_path` and `starting_pdb` to local paths and submit. |
| `recipes.md` | Copy-paste snippets for the common campaigns (first attempt, warm-start, flexible target, peptide, no-filter diagnostic, SLURM submission, parallel campaigns, refilter without re-running). |

## The shape of a campaign

```bash
conda activate BindCraft
cd /path/to/bindcraft

# 1. Trim your target PDB to the smallest reasonable form (one or two chains, one domain).
# 2. Pick a hotspot patch (4–8 residues describing the epitope) — or use null to let AF2 choose.
# 3. Write a target JSON modeled on PDL1_target.json.

# 4. First run — default everything, 200–500 trajectories.
python -u ./bindcraft.py --settings ./settings_target/<your>.json

# 5. Check `<design_path>/failure_csv.csv`. Top column = your bottleneck.

# 6. Iterate: pick a preset that fixes it (see references/advanced-settings.md).

# 7. Re-run with the same --settings; it resumes.

# 8. When `Accepted/Ranked/` has 5–20 PDBs you'd order, validate the top picks
#    with an independent predictor (boltz / chai-lab / protenix / esm-biohub / fair-esm),
#    then send to the wet lab.
```

## Key things to remember

- **Trim the target.** Single biggest lever for GPU memory and design
  quality.
- **`number_of_final_designs` is what you trust to be enough.** The
  README recommends 100 accepted → order 5–20.
- **`Hotspot_RMSD` failures usually mean the hotspot is wrong, not the
  binder.** Inspect the trajectory PDBs in PyMOL — is the binder
  actually trying to bind where you asked it to?
- **`_hardtarget` rescues many runs.** When MPNN sequences keep failing
  reprediction but trajectories look good, switch to it.
- **Re-running is resuming.** Same `design_path` = continue. No special
  flag.
- **The pipeline already includes PyRosetta scoring and 5-model AF2
  reprediction.** You don't need to re-score externally before
  experimental hand-off — but you *should* cross-validate with an
  independent AF3-class predictor for the picks you order.

## See also

- `../SKILL.md` — full overview, JSON contract, output layout, gotchas.
- `../references/installation.md` — `install_bindcraft.sh` details, GPU sizing.
- `../references/inputs.md` — full schema for the three JSON files.
- `../references/advanced-settings.md` — every advanced setting + the preset matrix.
- `../references/filters.md` — full filter catalog + the five preset filter files.
- `../references/outputs.md` — output tree + CSV column reference.
- `../references/troubleshooting.md` — common failure modes + fixes.
