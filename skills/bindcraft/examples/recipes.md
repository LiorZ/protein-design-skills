# BindCraft recipes

Copy-paste snippets for the common campaigns. Assumes `cd
/path/to/bindcraft && conda activate BindCraft` and that
`./settings_target/<your_target>.json` is your target JSON (see
`PDL1_target.json` for the shape).

## First attempt — mini-protein binder, default everything

```bash
python -u ./bindcraft.py \
    --settings  ./settings_target/<your_target>.json \
    --filters   ./settings_filters/default_filters.json \
    --advanced  ./settings_advanced/default_4stage_multimer.json
```

After 200–500 trajectories check `failure_csv.csv` to see which
filter is dominating, then iterate. Re-running with the same
`design_path` resumes.

## Rigid target, designs failing reprediction → warm-start

```bash
python -u ./bindcraft.py \
    --settings  ./settings_target/<your_target>.json \
    --filters   ./settings_filters/default_filters.json \
    --advanced  ./settings_advanced/default_4stage_multimer_hardtarget.json
```

## Flexible / cryptic-pocket target

```bash
python -u ./bindcraft.py \
    --settings  ./settings_target/<your_target>.json \
    --filters   ./settings_filters/default_filters.json \
    --advanced  ./settings_advanced/default_4stage_multimer_flexible.json
```

## Both — rescue mode

```bash
python -u ./bindcraft.py \
    --settings  ./settings_target/<your_target>.json \
    --filters   ./settings_filters/default_filters.json \
    --advanced  ./settings_advanced/default_4stage_multimer_mpnn_flexible_hardtarget.json
```

## β-sheet binder

```bash
python -u ./bindcraft.py \
    --settings  ./settings_target/<your_target>.json \
    --filters   ./settings_filters/default_filters.json \
    --advanced  ./settings_advanced/betasheet_4stage_multimer.json
```

## Peptide binder (8–25 aa)

```jsonc
// settings_target/<your_target>.json
{
    "design_path":              "/path/to/output/BindCraft_peptide_TARGET/",
    "binder_name":              "TARGETp",
    "starting_pdb":             "/path/to/target.pdb",
    "chains":                   "A",
    "target_hotspot_residues":  "A23-30",
    "lengths":                  [8, 25],
    "number_of_final_designs":  50
}
```

```bash
python -u ./bindcraft.py \
    --settings  ./settings_target/<your_target>.json \
    --filters   ./settings_filters/peptide_filters.json \
    --advanced  ./settings_advanced/peptide_3stage_multimer.json
```

## Diagnostic — see what AF2 produces with no filters

When nothing accepts after 1000 trajectories and you suspect the
filters are the issue:

```bash
python -u ./bindcraft.py \
    --settings  ./settings_target/<your_target>.json \
    --filters   ./settings_filters/no_filters.json \
    --advanced  ./settings_advanced/default_4stage_multimer.json
```

Inspect `Accepted/` after a few trajectories. If designs look reasonable
in PyMOL, retighten filters incrementally; if they look like junk, the
advanced settings (not the filters) are the issue.

## SLURM submission

```bash
sbatch ./bindcraft.slurm \
    --settings  ./settings_target/<your_target>.json \
    --filters   ./settings_filters/default_filters.json \
    --advanced  ./settings_advanced/default_4stage_multimer.json
```

Adjust the `#SBATCH` header at the top of `bindcraft.slurm` for your
cluster (partition, qos, GPU type, walltime).

## Parallel campaigns on the same target (different topologies)

Bring two folders, two `design_path`s:

```bash
# helical bias campaign
python -u ./bindcraft.py \
    --settings  ./settings_target/TARGET_helical.json \
    --advanced  ./settings_advanced/default_4stage_multimer.json &

# beta-sheet bias campaign
python -u ./bindcraft.py \
    --settings  ./settings_target/TARGET_beta.json \
    --advanced  ./settings_advanced/betasheet_4stage_multimer.json &
```

Each needs its own `design_path` (in the target JSONs). Merge the
`Accepted/` PDBs at the end for downstream selection.

## Quick failure-mode triage

```python
import pandas as pd

design_path = "/path/to/output/BindCraft_TARGET"
fail = pd.read_csv(f"{design_path}/failure_csv.csv").T.reset_index()
fail.columns = ["metric", "count"]
print(fail.sort_values("count", ascending=False).head(15))
```

## Loading + plotting the trajectory metrics

```python
import pandas as pd
import matplotlib.pyplot as plt

traj = pd.read_csv(f"{design_path}/trajectory_stats.csv")
print(f"{len(traj)} trajectories survived triage")
traj[["i_pTM", "pLDDT", "dG", "ShapeComplementarity"]].hist(bins=40)
plt.tight_layout(); plt.show()

mpnn = pd.read_csv(f"{design_path}/mpnn_design_stats.csv")
print(f"{len(mpnn)} MPNN designs predicted")
print(mpnn[["Average_i_pTM", "Average_pLDDT", "Average_dG",
            "Average_ShapeComplementarity"]].describe())
```

## Cross-validating accepted designs with another AF3-class predictor

After BindCraft finishes, hand the top-ranked accepted designs to an
independent predictor — two AF3-class predictors agreeing is a stronger
signal than ipTM alone.

```python
# Pseudocode — actual run depends on which skill
# top_pdbs = sorted_accepted_pdbs(design_path)[:10]
# for pdb in top_pdbs:
#     seq_binder = extract_chain_sequence(pdb, "B")
#     seq_target = extract_chain_sequence(pdb, "A")
#     # Run boltz, chai-lab, protenix on (seq_target, seq_binder)
#     # Compare i_pTM, plDDT, interface lDDT
```

See the `boltz`, `chai-lab`, `protenix`, `esm-biohub`, `fair-esm` skills
for the actual one-liner each requires.

## Refiltering an existing campaign (no GPU re-run)

`mpnn_design_stats.csv` has every metric computed — you can re-apply
different thresholds without redesigning.

```python
import pandas as pd, json, shutil, os

design_path = "/path/to/output/BindCraft_TARGET"
new_filters = json.load(open("/path/to/relaxed_filters.json"))
mpnn = pd.read_csv(f"{design_path}/mpnn_design_stats.csv")

def passes(row, filters):
    for key, spec in filters.items():
        if spec["threshold"] is None or key == "InterfaceAAs": continue
        if key.endswith("AAs"): continue
        if key not in mpnn.columns: continue
        v = row[key]
        if pd.isna(v): return False
        if spec["higher"]:
            if v < spec["threshold"]: return False
        else:
            if v > spec["threshold"]: return False
    return True

mask = mpnn.apply(passes, filters=new_filters, axis=1)
print(f"{mask.sum()} designs pass the new filter set")
# To re-rank: pick the best AF2 model per design, copy out of MPNN/Relaxed/
```

(This is a starter — the real script needs to also pick the best AF2
model per design and copy the matching PDB from `MPNN/Relaxed/`.)
