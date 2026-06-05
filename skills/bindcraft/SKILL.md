---
name: bindcraft
description: >
  Run BindCraft — a hallucination-based de novo binder design pipeline that
  couples **AF2 backpropagation** (ColabDesign), **ProteinMPNN** redesign,
  **AF2 reprediction**, and a full **PyRosetta** interface-score filter pass
  against a single target PDB. One `bindcraft.py` (or `sbatch
  bindcraft.slurm`) call runs an endless trajectory loop until the requested
  number of designs that pass every filter is reached. Use this skill when:
  (1) De novo designing **mini-protein binders** (~65–150 aa) against a
      protein target — the canonical BindCraft use case,
  (2) Designing **peptide binders** (≤ ~25 aa) using the dedicated
      `peptide_3stage_multimer` advanced preset + `peptide_filters`,
  (3) Designing for a **β-sheet-rich** target or a target where the binder
      *should* be β-sheet (`betasheet_4stage_multimer` preset),
  (4) Selecting a **hotspot patch** (`target_hotspot_residues`: `"56"`,
      `"A1-10,B1-20"`, `"A"`, or `null`) to focus AF2 on a specific epitope,
  (5) Producing AF2-validated designs ranked by **interface ipTM / pLDDT
      / pAE / Rosetta dG / ShapeComplementarity / unsat-Hbonds** with
      per-model and average-across-models filters,
  (6) Choosing the right **modifier preset** for the campaign:
      `_mpnn` (let MPNN redesign the interface), `_flexible` (mask target
      template seq → flexible target backbone), `_hardtarget` (warm-start
      reprediction from binder atom positions → rescues failures on rigid
      targets),
  (7) **Relaxing filters** for hard targets via `relaxed_filters.json` /
      `peptide_relaxed_filters.json` or going `no_filters.json` to see what
      AF2 is producing before tightening,
  (8) Tuning **design weights** (`weights_plddt`, `weights_pae_inter`,
      `weights_con_inter`, `weights_iptm`, `weights_helicity`, `weights_rg`,
      `weights_termini_loss`) and **design iterations** (soft / temporary /
      hard / greedy) for difficult targets,
  (9) Diagnosing **trajectory failure modes** (low confidence, clashes,
      wrong hotspot, deformed binder, low MPNN acceptance rate) and
      adjusting the script via `acceptance_rate` / `start_monitoring` /
      `enable_rejection_check` so it auto-aborts if nothing is working.

  Covers installation (`install_bindcraft.sh --cuda 12.4 --pkg_manager
  conda` → BindCraft conda env + ColabDesign + PyRosetta + AF2 weights),
  hardware requirements (CUDA Nvidia, ≥32 GB GPU memory recommended), the
  **3-JSON contract** (`settings_target/*.json` + `settings_filters/*.json`
  + `settings_advanced/*.json`), the **20+ preset advanced configs**
  (default / betasheet / peptide × `_mpnn`/`_flexible`/`_hardtarget`
  modifiers), the **5 design algorithms** (`2stage`, `3stage`, `4stage`,
  `greedy`, `mcmc`), the **5 filter presets** (default / relaxed /
  peptide / peptide_relaxed / no), the **output tree**
  (`Trajectory/Relaxed`, `Trajectory/LowConfidence`, `Trajectory/Clashing`,
  `MPNN/Relaxed`, `Accepted/Ranked`, `Rejected`, four CSV stats files),
  the **trajectory loop** (sample length + seed + helicity → AF2
  hallucinate → PyRosetta relax → MPNN redesign → AF2 repredict per
  sequence → interface scoring → filter → accept/reject), and how it
  composes in the larger campaign.

  Pairs with: `boltzgen` (diffusion-based all-atom alternative — BindCraft
  is the hallucination camp, boltzgen is the diffusion camp; cross-validate
  with both), `chai-lab` / `boltz` / `protenix` / `esm-biohub` /
  `fair-esm` (independent AF3-class structure prediction of accepted
  BindCraft designs for orthogonal validation), `foundry` (RFdiffusion3 +
  MPNN / SolubleMPNN — backbone-first alternative; BindCraft already
  bundles ProteinMPNN internally so you usually don't double-up), `placer`
  (refine and score interface side chains / ligand poses for hits),
  `biotite` (parse the per-trajectory CIF/PDB outputs, compute extra
  metrics — e.g. lDDT vs other predictors — or cluster accepted designs),
  `protflow` (drive BindCraft as one runner in a larger multi-target
  campaign with SLURM arrays and a Poses DataFrame).
license: MIT
category: protein-design
tags: [protein-design, binder-design, peptide-design, hallucination, alphafold2, proteinmpnn, pyrosetta, colabdesign, af2-backprop, interface-design, slurm]
repo: https://github.com/martinpacesa/BindCraft
biorxiv: https://www.biorxiv.org/content/10.1101/2024.09.30.615802
wiki: https://github.com/martinpacesa/BindCraft/wiki/De-novo-binder-design-with-BindCraft
colab: https://colab.research.google.com/github/martinpacesa/BindCraft/blob/main/notebooks/BindCraft.ipynb
---

# BindCraft — hallucination-based de novo binder design

## What this is

BindCraft is an **endless trajectory loop** that designs de novo binders
for a target protein and **stops only when it has the requested number of
designs passing every filter** (or hits `max_trajectories`, or the
auto-acceptance-rate monitor decides nothing is working). It is the
hallucination camp's reference pipeline — the inverse of diffusion tools
like RFdiffusion3 / BoltzGen / Genie 3 / DISCO.

The pipeline per trajectory is fixed:

| Step | What runs | Output dir |
|------|-----------|-----------|
| 1. Sample | random `length ∈ [min, max]`, random `seed`, sample `helicity` from the prior | — |
| 2. **Hallucinate** | AF2 backprop with the `design_algorithm` (`2stage` / `3stage` / `4stage` / `greedy` / `mcmc`) | `Trajectory/` |
| 3. **Triage** | trajectory tagged as low-confidence, clashing, or kept | `Trajectory/LowConfidence` · `Trajectory/Clashing` · `Trajectory/Relaxed` |
| 4. **Relax** | PyRosetta FastRelax of the AF2 trajectory PDB | `Trajectory/Relaxed/` |
| 5. **Score** | PyRosetta interface metrics (dG, dSASA, SC, PackStat, H-bonds, unsat-Hbonds, hydrophobicity, secondary structure, clashes) + RMSDs | row in `trajectory_stats.csv` |
| 6. **MPNN redesign** | ProteinMPNN (or SolubleMPNN) generates `num_seqs` sequences for the binder chain (interface optionally fixed) | — |
| 7. **AF2 repredict** | every passing MPNN sequence is re-predicted as a complex (5 AF2 models) **and** as a binder monomer | `MPNN/`, `MPNN/Relaxed/`, `MPNN/Binder/` |
| 8. **Filter** | per-model + average filters checked against the filter JSON; H-bond, dG, SC, ipTM, pLDDT, etc. | `Accepted/` or `Rejected/` |
| 9. **Loop** | if `accepted_designs ≥ number_of_final_designs` → rank `Accepted` PDBs and stop; otherwise next trajectory | — |

The whole thing is steered by **three JSON files**:

```text
--settings  ./settings_target/<your_target>.json      # required: PDB, chains, hotspot, lengths
--filters   ./settings_filters/<preset>.json          # default: default_filters.json
--advanced  ./settings_advanced/<preset>.json         # default: default_4stage_multimer.json
```

`--filters` and `--advanced` are optional; omitting them falls back to the
defaults above. The script writes everything under
`target_settings["design_path"]`.

> **Top rule of thumb (from the upstream README):**
> *Always trim the input target PDB to the smallest size possible.*
> GPU memory blows up with target size, and bigger targets mean more
> deformed-binder trajectories. Strip everything outside the targeted
> chains / patch / domain.

## When to use BindCraft vs. alternatives

| You want… | Use |
|-----------|-----|
| De novo **mini-protein binder** against a protein, hallucination-based, fully AF2-validated, with a battery of biophysical filters | **BindCraft** |
| **Diffusion**-based all-atom binder against protein / peptide / small-molecule / DNA / RNA, with ipSAE / affinity / refold filters | `boltzgen` |
| **Backbone-only** diffusion (then plug your own MPNN + validation) | `foundry` (RFdiffusion3) / `genie3` |
| **Sequence + structure co-design** conditioned on a small molecule / metal / DNA / RNA | `disco` |
| **Peptide binder** specifically, with helical / cyclic / disulfide / stapled / cyclotide forms | `boltzgen` (`peptide-anything`) — BindCraft can do linear peptides via the `peptide_3stage_multimer` preset but not cyclic / stapled |
| **Antibody / nanobody** design | `boltzgen` (`antibody-anything` / `nanobody-anything`) — BindCraft is not antibody-aware |
| **Small-molecule** binder | `boltzgen` (`protein-small_molecule`) — BindCraft has no ligand mode |
| Validate accepted designs with an **independent** structure predictor | `chai-lab` / `boltz` / `protenix` / `esm-biohub` (ESMFold2) / `fair-esm` (ESMFold) |
| **Cluster / score** the accepted set | `biotite` (parse, compute metrics) + `foldseek` (external) |
| Wrap the campaign on SLURM with per-target arrays | `protflow` |

## Installation (one-shot)

```bash
git clone https://github.com/martinpacesa/BindCraft  /path/to/bindcraft
cd /path/to/bindcraft
bash install_bindcraft.sh --cuda '12.4' --pkg_manager 'conda'   # or 'mamba'
```

That single script creates a `BindCraft` conda env (Python 3.10, JAX +
CUDA, NumPy < 2, Biopython, PyRosetta, ColabDesign), then downloads and
extracts the **AF2 weights** (~5.3 GB) into `./params/` *inside the
install directory*. After it finishes:

```bash
conda activate BindCraft
python -c "import colabdesign, pyrosetta; print('ok')"
```

Requirements:
- **CUDA-capable Nvidia GPU** (no CPU fallback for the AF2 step).
- ≥ **32 GB** GPU memory recommended for larger target+binder complexes.
- ~ **2 MB** code + ~ **5.3 GB** AF2 weights on disk.
- **PyRosetta license** is required for commercial use (gratis for
  non-commercial / academic).

Full details, GPU sizing, and per-machine setups → `references/installation.md`.

## The three input JSONs

### `settings_target/*.json` — what to design

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

`target_hotspot_residues` syntax: `null` (let AF2 pick the site), a single
residue (`"56"`), a range (`"1-20"`), comma-separated mix (`"1,2-10"`),
chain-prefixed (`"A1-10,B1-20"`), or whole chains (`"A"`). When in doubt,
pick a small patch — it dramatically reduces search space.

`lengths` is a `[min, max]` range; each trajectory samples uniformly.

### `settings_filters/*.json` — what counts as a hit

Five built-in presets:
- `default_filters.json` — tight, recommended starting point.
- `relaxed_filters.json` — loosen i_pTM / i_pAE / ShapeComplementarity / unsat-Hbonds / Hotspot_RMSD for difficult targets.
- `peptide_filters.json` — tuned for peptide binders (lower i_pTM bar, looser Hotspot_RMSD).
- `peptide_relaxed_filters.json` — peptide + relaxed.
- `no_filters.json` — every threshold `null` → see what AF2 produces.

Each filter row is `{ "threshold": <number|null>, "higher": <bool> }`. Set
`threshold: null` to disable that filter. Each metric is checked per AF2
model (`1_<metric>`…`5_<metric>`) and as an `Average_<metric>` — disabling
individual models lets you require, say, only model 1 + model 2 to pass.

Full list of metrics and recommended ranges → `references/filters.md`.

### `settings_advanced/*.json` — how to design

Combine **one** base flavor with optional modifiers:

| Base | Use when | `weights_helicity` | `design_algorithm` | `force_reject_AA` |
|------|----------|--------------------|---------------------|-------------------|
| `default_4stage_multimer` | typical alpha-helix-biased mini-protein binder | -0.3 | 4stage | false |
| `betasheet_4stage_multimer` | binder should be β-sheet rich (e.g. β-barrel scaffold target) | -2.0 (strong β bias) | 4stage | false |
| `peptide_3stage_multimer` | short peptide binders, fully helical bias | +0.95 | 3stage | true (block C) |

Modifiers (composable, e.g. `default_4stage_multimer_mpnn_flexible_hardtarget`):

| Suffix | Changes vs base | When to use |
|--------|-----------------|-------------|
| `_mpnn` | `mpnn_fix_interface=false` → MPNN can redesign interface residues | When the hallucinated interface is suboptimal and you want MPNN free to re-route |
| `_flexible` | `rm_template_seq_design=true, rm_template_seq_predict=true` → mask target sequence in template | When the target backbone should be allowed to move (cryptic pockets, flexible loops) |
| `_hardtarget` | `predict_initial_guess=true` → warm-start AF2 reprediction from binder atom positions | When designs are good in trajectory but fail reprediction (rigid targets where AF2 reprediction "forgets" the binder) |

All 20+ shipped presets are described in `references/advanced-settings.md`.

## Run it

### Local (no SLURM)

```bash
conda activate BindCraft
cd /path/to/bindcraft
python -u ./bindcraft.py \
    --settings  ./settings_target/PDL1.json \
    --filters   ./settings_filters/default_filters.json \
    --advanced  ./settings_advanced/default_4stage_multimer.json
```

### SLURM

```bash
sbatch ./bindcraft.slurm \
    --settings  ./settings_target/PDL1.json \
    --filters   ./settings_filters/default_filters.json \
    --advanced  ./settings_advanced/default_4stage_multimer.json
```

The shipped SLURM script asks for 1 GPU, 42 GB RAM, 72 h walltime, and a
`bindcraft_<jobid>.log` log file. Adjust the `#SBATCH` header for your
cluster.

The script is **resumable** — re-running with the same `design_path`
continues from where it left off. Existing trajectory PDBs are detected
and skipped; the accepted-count is read off the `Accepted/` folder.

## Output layout

Everything lands under `target_settings["design_path"]`:

```text
<design_path>/
├── trajectory_stats.csv        # one row per trajectory
├── mpnn_design_stats.csv       # one row per MPNN sequence (per trajectory × num_seqs)
├── final_design_stats.csv      # one row per Accepted design, with Rank column
├── failure_csv.csv             # filter-failure counts (which threshold killed how many)
├── Trajectory/
│   ├── Relaxed/                # AF2-hallucinated + PyRosetta-relaxed binder PDBs (kept)
│   ├── LowConfidence/          # AF2 termination signal "LowConfidence"
│   ├── Clashing/               # AF2 termination signal "Clashing"
│   ├── Animation/              # GIF/HTML of the design trajectory (zipped at end)
│   ├── Plots/                  # PNG of trajectory metrics (zipped at end)
│   └── Pickle/                 # full ColabDesign pickle (only if save_trajectory_pickle=true)
├── MPNN/
│   ├── Sequences/              # FASTA per MPNN design (only if save_mpnn_fasta=true)
│   ├── Relaxed/                # AF2-repredicted, PyRosetta-relaxed complex PDBs
│   └── Binder/                 # AF2-repredicted binder monomer PDBs (used for Binder_RMSD)
├── Accepted/                   # PDBs of designs passing every filter
│   ├── Ranked/                 # same PDBs renamed with <rank>_<name>_model<n>.pdb
│   ├── Animation/              # trajectory animations copied for accepted designs
│   ├── Plots/                  # trajectory plots copied for accepted designs
│   └── Pickle/                 # trajectory pickles copied for accepted designs (if enabled)
└── Rejected/                   # AF2 prediction passed but a non-AF2 filter killed it
```

The `Ranked/` folder is what you hand off — sort by `final_design_stats.csv`,
pick the top 5–20 by hand for ordering. **The README explicitly recommends
~100 final designs and ordering 5–20 of them** for experimental
characterisation; ipTM is a good binary binding predictor but not an
affinity ranker.

Full CSV column reference and dir semantics → `references/outputs.md`.

## Key gotchas

1. **Trim the target PDB.** Bigger target = quadratic GPU memory growth +
   more deformed-binder trajectories. Strip everything outside the
   targeted chains / patch / domain.
2. **AF2 sees only the target, not the rest of the asymmetric unit.** If
   the binding site is at a crystal contact, AF2 has no idea — strip
   neighbouring chains or pick a different epitope.
3. **Expect 100s–1000s of trajectories per target.** Difficult targets
   (large, flat, polar, β-sheet) may take 1000–3000+. The auto rejection
   monitor (`acceptance_rate` × `start_monitoring`) will abort the run if
   no designs pass; raise `start_monitoring` or lower `acceptance_rate`
   before assuming it's "stuck".
4. **`omit_AAs: "C"` is on by default.** Designs cannot contain cysteine
   (no disulfides) unless you change it. `force_reject_AA: true` makes
   this hard; default `false` lets MPNN keep Cys if it's the only viable
   choice. The peptide preset turns it on hard.
5. **The "Loop" filter is inverted vs. helices.** `Binder_Loop% > 90` is
   a *rejection* threshold (`higher: false`) — too much loop = bad. If
   you accidentally set `higher: true`, you require ≥ 90% loop content
   (i.e., nothing will ever pass).
6. **Hotspot is a hint, not a hard constraint.** AF2 may pick a nearby
   site instead. Use `Hotspot_RMSD` and `WrongHotspot` in the failure CSV
   to see how often this is happening. Selecting `null` lets AF2 choose
   the site entirely — useful for cryptic pockets.
7. **Multimer vs. ptm AF2.** `use_multimer_design: true` uses
   AF2-multimer for hallucination and AF2-ptm for reprediction
   validation (and vice-versa). Mixing both as a cross-check is the
   whole point — don't disable it lightly.
8. **`predict_initial_guess` rescues many failed designs.** If MPNN
   sequences are repeatedly failing the AF2 reprediction step but the
   hallucinated trajectory looked good, switch to the `_hardtarget`
   variant. For large complexes (>600 aa total), additionally enable
   `predict_bigbang`.
9. **β-sheet trajectories are slower.** `optimise_beta: true` (on in
   most presets) triggers extra recycles when ≥ 15% β content is
   detected — costs time but rescues fragile β designs.
10. **Resume is free.** Same `design_path` = continue. There is no
    `--resume` flag; the loop simply skips already-present trajectory
    PDBs and reads accepted-count from disk.

## Reference index

- `references/installation.md` — `install_bindcraft.sh` details, GPU sizing, AF2 weights layout, license notes
- `references/inputs.md` — full schema and syntax for the three JSON files
- `references/advanced-settings.md` — every advanced setting explained + which preset to pick
- `references/filters.md` — full filter dictionary + the five preset filter JSONs compared
- `references/outputs.md` — directory layout + CSV columns + how `Accepted/Ranked` is built
- `references/troubleshooting.md` — common failure modes + fixes
- `examples/PDL1_target.json` — drop-in target config (adapt paths)
- `examples/recipes.md` — copy-paste snippets for the common campaigns

## Citation

> Pacesa, M., Nickel, L., Schellhaas, C., Schmidt, J., Pyatova, E., Kissling, L.,
> Barendse, P., Choudhury, J., Kapoor, S., Ghosh, A., Romero, E.O., Mu, S., Dauparas, J.,
> Mahdavi-Amiri, Y., Goverde, C.A., Khare, S.D., Kothiwale, S., Roush, W., Tate, A.J.,
> Cho, Y., Hill, A., Goverde, C., Eberhardt, J., Aebersold, R., Levin, A., Ovchinnikov, S.,
> Correia, B.E. (2024). *BindCraft: one-shot design of functional protein binders.*
> bioRxiv 2024.09.30.615802. https://doi.org/10.1101/2024.09.30.615802
