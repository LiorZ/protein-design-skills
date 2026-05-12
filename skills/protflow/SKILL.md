---
name: protflow
description: >
  Build composable protein design pipelines with ProtFlow — a Python framework
  that wraps RFdiffusion, RFdiffusion3, LigandMPNN/ProteinMPNN/SolubleMPNN,
  ESMFold, ColabFold (AF2), AlphaFold3, Boltz, Caliby, Frame2Seq, ProteinGenerator,
  PLACER, AttnPacker, SigmaDock, Rosetta, GROMACS, DSSP, FPocket, Propka, TM-align,
  RMSD/biopython metrics, and more behind a single Poses + JobStarter + Runner API,
  with first-class SLURM array-job and local execution. Use this skill when:

  (1) Composing multi-step design pipelines (generate backbone → design sequence
      → predict structure → score → filter → iterate) without writing bespoke
      cluster-management code.
  (2) Running any of the supported tools on a SLURM cluster as array jobs, or
      locally as parallel subprocesses, behind a unified interface.
  (3) Managing a pandas-DataFrame-backed `Poses` object that carries all
      structures, sequences, scores, residue selections, and motifs through
      the pipeline, persisted as JSON/CSV/Pickle/Parquet/Feather.
  (4) Filtering / ranking / composite-scoring designs with `filter_poses_by_rank`,
      `filter_poses_by_value`, and `calculate_composite_score`.
  (5) Tracking residue motifs across generative steps (e.g. RFdiffusion
      contig → designed → predicted) using `ResidueSelection` and motif remapping.
  (6) Adding a new tool / runner to a pipeline by subclassing `Runner` and
      following the standard `run()` → DataFrame contract.
  (7) Wiring tool paths and Python environments via `~/.config/protflow/config.py`
      (the `protflow-init-config` / `protflow-set-config` / `protflow-check-config`
      CLI tools).
  (8) Debugging a runner crash by reading the captured stderr, the runner's
      score file, or the SLURM accounting via `get_SLURM_stats`.

  Covers the Poses/JobStarter/Runner architecture, the `prefix` convention,
  options vs `pose_options` vs `pose_opt_cols`, residue selections, the
  config.py system, the runner/metric catalog, SLURM vs local job starters,
  motif tracking through RFdiffusion, common pipeline patterns (de novo
  monomer, binder design with validation, ligand co-folding, enzyme design,
  redesign + relaxation), troubleshooting, and how to extend ProtFlow with a
  custom runner.

  Pairs with: `rfdiffusion`, `proteinmpnn`, `ligandmpnn`, `solublempnn`,
  `bindcraft`, `boltzgen`, `boltz`, `alphafold`, `chai`, `esm`, `protein-qc`,
  `ipsae`, `binder-design`, `protein-design-workflow`, `campaign-manager`.
license: MIT
category: pipeline-orchestration
tags: [orchestration, pipeline, slurm, protein-design, hpc, dataframe, rfdiffusion, ligandmpnn, alphafold3, boltz, esmfold, rosetta, gromacs, sigmadock, residue-selection, motif-tracking]
repo: https://github.com/mabr3112/ProtFlow
docs: https://protflow.readthedocs.io/en/latest/
ci: https://github.com/mabr3112/ProtFlow/actions/workflows/pytest.yaml
---

# ProtFlow — Protein Design Pipelines on SLURM (and Locally)

## What this is

ProtFlow is a Python package that runs protein design tools on SLURM clusters
behind a single, uniform API. You write a pipeline as a sequence of
`runner.run(poses, prefix=...)` calls; ProtFlow handles submission,
parallelisation, output collection, score-DataFrame merging, and intermediate
storage.

The framework is built around **three primary abstractions**:

| Abstraction       | What it is                                                              | Lives in                           |
|-------------------|-------------------------------------------------------------------------|------------------------------------|
| **`Poses`**       | A pandas DataFrame of structures/sequences/scores plus a `work_dir`.    | `protflow.poses`                   |
| **`JobStarter`**  | A submission backend: SLURM array (`SbatchArrayJobstarter`) or local.   | `protflow.jobstarters`             |
| **`Runner`**      | A wrapper around one external tool (RFdiffusion, ESMFold, ...).          | `protflow.tools.*`, `protflow.metrics.*` |

Everything else — residue selections, motif tracking, composite scoring,
filtering, plotting — is built on top.

> **Key contract:** every `runner.run(poses, prefix="foo", ...)` call **mutates
> and returns the same `Poses` object** (it both updates `poses.df` in place
> and returns it for chaining). Output files land under
> `poses.work_dir/foo/` and a score file `foo_scores.<storage_format>` is
> created there. Every new column added to `poses.df` is prefixed with
> `foo_` to prevent name collisions across runs.

## When to reach for this skill

Reach for ProtFlow when the user wants to:

- Chain multiple design tools (e.g. RFdiffusion → LigandMPNN → ESMFold → RMSD).
- Run any of the supported tools across a SLURM cluster *without* writing
  sbatch scripts or polling logic.
- Iterate on designs while keeping all metadata in one DataFrame they can
  filter, plot, and export.
- Add a new external tool to an existing pipeline without bespoke glue code.

Do **not** reach for this skill when the user wants to:

- Run a single one-shot inference of one tool (just call that tool directly,
  or use that tool's own skill — `rfdiffusion`, `bindcraft`, `boltz`, etc.).
- Replace a SLURM-aware Snakemake/Nextflow pipeline (ProtFlow is Python-only,
  in-process orchestration; no DAG engine, no resume-from-checkpoint other
  than score-file caching).

## Prerequisites

| Requirement | Recommended                                  | Notes |
|-------------|----------------------------------------------|-------|
| OS          | Linux                                        | Tested on cluster login + compute nodes. macOS works for `LocalJobStarter` only. |
| Python      | ≥ 3.11                                       | Hard requirement; `pyproject.toml` enforces this. |
| SLURM       | Recent SLURM with `sbatch`/`squeue`/`sacct`  | Required only for `SbatchArrayJobstarter`. `LocalJobStarter` works anywhere. |
| Environments | One conda/mamba env per tool                | RFdiffusion, ESMFold, LigandMPNN, AF2/AF3, Boltz, etc. each want their own — config.py points at the right Python binary per tool. |
| Disk        | A shared scratch / project directory         | Every run writes a `work_dir/<prefix>/` subtree. Plan for tens to hundreds of GB on a real campaign. |

## Installation (three steps)

```bash
# 1) Clone and install (editable; package is under active development)
git clone https://github.com/mabr3112/ProtFlow.git
cd ProtFlow
conda create -n protflow python=3.11 -y
conda activate protflow
pip install -e .

# 2) Initialise config.py (writes ~/.config/protflow/config.py)
protflow-init-config

# 3) (Optional) point at a custom config.py — useful on shared clusters:
protflow-set-config /shared/protflow/config.py
protflow-check-config        # confirms which file is in use
protflow-set-config --unset  # revert to the default search path
```

The config search order is **(0)** the pointer file saved by
`protflow-set-config`, **(1)** `$PROTFLOW_CONFIG`, **(2)**
`$XDG_CONFIG_HOME/protflow/config.py` (default
`~/.config/protflow/config.py`), **(3)** the bundled
`protflow/config.py`. See `references/config.md` for the full schema —
which env-var-style constants each runner expects to find, what they should
point to, and what `*_PRE_CMD` is for.

## The thirty-second example

```python
from protflow.poses import Poses
from protflow.jobstarters import SbatchArrayJobstarter
from protflow.tools.rfdiffusion import RFdiffusion
from protflow.tools.ligandmpnn import LigandMPNN
from protflow.tools.esmfold import ESMFold
from protflow.metrics.rmsd import BackboneRMSD

gpu = SbatchArrayJobstarter(max_cores=10, gpus=1)

poses = Poses(poses=None, work_dir="./demo_run", jobstarter=gpu, storage_format="pickle")

# 1) De novo 70mers
poses = RFdiffusion().run(poses, prefix="diff", num_diffusions=5,
                          options="'contigmap.contigs=[70-70]'")

# 2) 8 sequences per backbone with SolubleMPNN
poses = LigandMPNN().run(poses, prefix="mpnn", nseq=8, model_type="soluble_mpnn")

# 3) Predict structures with ESMFold
poses = ESMFold().run(poses, prefix="esm")

# 4) Backbone RMSD vs the original RFdiffusion structure
poses = BackboneRMSD(ref_col="diff_location").run(poses, prefix="rmsd")

# 5) Filter to ≤2 Å self-consistent designs, top-50 by predicted pLDDT
poses.filter_poses_by_value(score_col="rmsd_rmsd", value=2.0, operator="<=")
poses.filter_poses_by_rank(score_col="esm_plddt", n=50, ascending=False)
poses.save_scores()
poses.save_poses(out_path="./demo_run/final_designs/")
```

Everything in this snippet is *already standard ProtFlow*: no SLURM template,
no custom argparse, no manual score parsing. The `Poses` object grows columns
`diff_*`, `mpnn_*`, `esm_*`, `rmsd_*` as it goes, and the on-disk layout is
predictable (`./demo_run/diff/`, `./demo_run/mpnn/`, `./demo_run/esm/`, …).

## The Poses object — what it does

`Poses` is the *single source of truth* for a campaign. It is a thin wrapper
around `poses.df: pd.DataFrame` plus directory management.

| You want to ...                                  | Use ...                                              |
|--------------------------------------------------|------------------------------------------------------|
| Load PDBs from a directory                       | `Poses(poses="some/dir/", glob_suffix="*.pdb")`     |
| Load from a saved score file                     | `Poses(poses="prev_run_scores.json")` *or* `load_poses(path)` |
| Set the work directory after construction        | `poses.set_work_dir("./run/")`                     |
| Filter to top-N by a score                       | `poses.filter_poses_by_rank(n=50, score_col=..., ascending=False)` |
| Filter by value                                  | `poses.filter_poses_by_value(score_col=..., value=2.0, operator="<=")` |
| Build a composite ranking score                  | `poses.calculate_composite_score(name=..., scoreterms=[...], weights=[...])` |
| Aggregate scores across pose groups              | `poses.calculate_mean_score(...)` / `_median_` / `_max_` / `_min_` / `_std_` |
| Persist to disk between steps                    | `poses.save_scores()` (auto-named in `work_dir`)    |
| Copy final PDBs out                              | `poses.save_poses("./final_pdbs/")`                |
| Replicate each pose N× (e.g. for sequence design)| `poses.duplicate_poses("./multiplexed/", n_duplicates=N)` |
| Reset poses to the original inputs               | `poses.reset_poses()`                              |
| Build a `Bio.PDB.Structure` for inspection       | `poses.get_pose("pose_description")`               |
| Rebuild the index after merges                   | `poses.reindex_poses(prefix=..., remove_layers=1)` |

`poses.df` always carries three mandatory columns:

- `input_poses` — original input path (never overwritten)
- `poses` — current "active" pose path; this is what runners read from
- `poses_description` — basename without extension; used to merge scores back

Runner outputs append `{prefix}_location`, `{prefix}_description`, and
score columns named `{prefix}_<scoreterm>`.

See `references/poses.md` for the full method list with semantics.

## JobStarters — local vs SLURM

`JobStarter` decides *how* a runner's commands are executed.

```python
from protflow.jobstarters import LocalJobStarter, SbatchArrayJobstarter

local      = LocalJobStarter(max_cores=4)
slurm_cpu  = SbatchArrayJobstarter(max_cores=50, gpus=False)
slurm_gpu  = SbatchArrayJobstarter(max_cores=10, gpus=1, options="--time=08:00:00 --partition=gpu")
```

Resolution priority when a runner runs is

```
runner.run(jobstarter=...)  >  Runner(jobstarter=...)  >  Poses(jobstarter=...)
```

so a per-run override always wins, then the runner's default, then the Poses
default. This is exactly what you want when most of the pipeline is one
backend but a single step needs different resources (e.g. CPU LigandMPNN
inside an otherwise GPU pipeline).

Notes worth knowing:

- `SbatchArrayJobstarter` chunks commands into SLURM job arrays, capping
  concurrent tasks at `max_cores`. Arrays longer than 1000 are split.
- `batch_cmds=N` (constructor or `.start()` arg) merges short commands into
  N composite array tasks via `;`-joining. Use this when you have thousands
  of fast commands.
- `options="..."` is appended verbatim to every `sbatch`. Use for
  `--time`, `--partition`, `--qos`, `--mem`, etc.
- `gpus=1` adds `--gpus-per-node 1`. Set `gpus=False` for CPU partitions.
- `wait=True` (the default) blocks until the array drains. ProtFlow uses
  this so the next step in your script can rely on outputs being on disk.
- `get_SLURM_stats(job_name, start_time=...)` queries `sacct` for elapsed
  / CPU / state aggregates — useful for cost tracking. Must be called on a
  login node where `sacct` is available.

See `references/jobstarters.md` for the full table and `references/slurm.md`
for cluster-side caveats (array limits, sacct quirks, error log layout).

## The Runner contract

Every Runner exposes the same call shape:

```python
runner = SomeRunner(jobstarter=..., **constructor_kwargs)   # optional config overrides
poses  = runner.run(
    poses,
    prefix="step_name",            # mandatory; namespaces output columns & dir
    jobstarter=...,                # optional per-call override
    options=...,                   # global options (string in tool's native format)
    pose_options=...,              # per-row options: a list or a poses.df column name
    overwrite=False,               # if True, blow away previous results
    **tool_specific_kwargs,
)
```

What happens inside, every time:

1. The runner validates that `prefix` isn't already a column in `poses.df`
   (so you can't accidentally clobber a previous step).
2. It picks a jobstarter using the priority chain above.
3. It creates `poses.work_dir/<prefix>/` and writes intermediate files there.
4. It checks for an existing `<prefix>_scores.<storage_format>` and — if
   present and `overwrite=False` — short-circuits, merging cached scores
   back into `poses.df` without re-running the tool. This is how you can
   re-run the same pipeline script after fixing a downstream step.
5. It builds one command per pose (or per batch), launches them through the
   jobstarter, waits for completion.
6. It collects results into a DataFrame with `description` + `location` +
   score columns, persists it to the score file, and merges into `poses.df`
   via `RunnerOutput`.

The base class auto-wraps every subclass's `run()` so that if score
collection crashes, the exception is re-raised as `Runner.CrashError`
*with the tail of the SLURM/local stderr appended* — this is the single
most useful debugging affordance ProtFlow provides. Always read the
appended log block when a runner fails.

`references/runners-pattern.md` walks through the contract in detail and shows
how to subclass `Runner` for a new tool.

## options vs pose_options vs pose_opt_cols

Three flavours, all valid simultaneously:

| Form               | Scope        | How to pass it                                  | Example                                                                 |
|--------------------|--------------|--------------------------------------------------|-------------------------------------------------------------------------|
| `options`          | Every pose   | A string in the tool's native CLI syntax        | `options="--temperature 0.05 --seed 1"`                                |
| `pose_options`     | Per-pose     | A list (same length as poses) OR the name of a poses.df column whose cells are strings | `poses.df["my_opts"] = [...]; runner.run(..., pose_options="my_opts")` |
| `pose_opt_cols`    | Per-pose, structured | A dict mapping the tool's option name → poses.df column whose cells are values (often `ResidueSelection`s, lists, paths) | `pose_opt_cols={"fixed_residues": "active_site"}` (LigandMPNN) |

Pose-specific values **override** global values where they conflict. Use
`options` for everything that's constant across the campaign, and reserve
`pose_options` / `pose_opt_cols` for things that legitimately vary per design
(input motifs, contigs, hotspots, fixed residues, …).

`references/options-and-pose-options.md` lists the exact syntax accepted by
each runner.

## Residue selections and motif tracking

`protflow.residues.ResidueSelection` is the canonical way to talk about
"which residues" inside a pose. It survives serialization through JSON / CSV
/ pickle and can be re-mapped after a generative step.

```python
from protflow.residues import ResidueSelection, from_contig, from_dict

motif = ResidueSelection("A12,A34,A56-A60")     # string form
motif = from_contig("A12-A20, B5")              # contig form
motif = from_dict({"A": [12, 13, 14], "B": [5]}) # dict form

motif.to_string()          # 'A12,A13,A14,B5'
motif.to_list()            # ['A12','A13','A14','B5']
motif.to_dict()            # {'A':[12,13,14], 'B':[5]}
motif.to_rfdiffusion_contig()  # for handing to RFdiffusion as a contigmap
```

Store a `ResidueSelection` in a `poses.df` column to carry it through the
pipeline. After RFdiffusion (where residue indices change), call
`rfdiff.run(..., update_motifs=["my_motif_col"])` and the column is
remapped to the new indices automatically using RFdiffusion's
`con_ref_pdb_idx`/`con_hal_pdb_idx` outputs.

For *computing* residue selections from a pose, ProtFlow provides four
**selectors** in `protflow.tools.residue_selectors`:

- `ChainSelector(chain=...)` / `ChainSelector(chains=[...])`
- `TrueSelector()` — every residue
- `NotSelector(residue_selection=..., contig=...)` — complement
- `DistanceSelector(center=..., distance=..., operator=..., center_atoms=..., noncenter_atoms=..., include_center=...)` — atom-distance-based, useful for pocket / interface definitions

Each selector's `.select(prefix=...)` writes a new column
`{prefix}_residue_selection` of `ResidueSelection` objects to `poses.df`.

There is also `AtomSelection` (in `protflow.residues`) for atom-level
operations including `from_rfd3_input_spec` to parse Foundry/RFD3
specifications.

See `references/residue-selection.md` for the full reference.

## Runner catalog

The catalog below lists every Runner shipped with ProtFlow as of master.
Each row has: import path, what it does, GPU/CPU, and the config.py path
variable it expects. Constructor signatures all accept
`(*, jobstarter=None)` plus tool-specific overrides; `.run()` always
takes `poses, prefix, ...` and returns the updated `Poses`.

### Backbone generation

| Runner                                           | Tool                       | GPU? | Config keys                                                                              |
|--------------------------------------------------|----------------------------|------|------------------------------------------------------------------------------------------|
| `protflow.tools.rfdiffusion.RFdiffusion`         | RFdiffusion                | yes  | `RFDIFFUSION_SCRIPT_PATH`, `RFDIFFUSION_PYTHON_PATH`, `RFDIFFUSION_PRE_CMD`             |
| `protflow.tools.rfdiffusion3.RFdiffusion3`       | RFdiffusion3 / Foundry RFD3 | yes  | `RFDIFFUSION3_BIN_PATH`, `RFDIFFUSION3_PYTHON_PATH`, `RFDIFFUSION3_MODEL_DIR`, `RFDIFFUSION3_PRE_CMD` |
| `protflow.tools.protein_generator.ProteinGenerator` | protein-generator       | yes  | `PROTEIN_GENERATOR_SCRIPT_PATH`, `PROTEIN_GENERATOR_PYTHON_PATH`                         |

### Sequence design (inverse folding)

| Runner                                                | Tool                                | GPU? | Config keys                                                              |
|-------------------------------------------------------|-------------------------------------|------|--------------------------------------------------------------------------|
| `protflow.tools.ligandmpnn.LigandMPNN`                | LigandMPNN / ProteinMPNN / SolubleMPNN / Membrane MPNN — `model_type` selects | yes  | `LIGANDMPNN_SCRIPT_PATH`, `LIGANDMPNN_PYTHON_PATH`, `LIGANDMPNN_PRE_CMD`  |
| `protflow.tools.frame2seqdesign.Frame2SeqDesign`      | Frame2Seq design                   | yes  | `FRAME2SEQ_PYTHON_PATH`, `FRAME2SEQ_PRE_CMD`                              |
| `protflow.tools.caliby.CalibySequenceDesign`          | Caliby sequence design             | yes  | (Caliby paths)                                                            |
| `protflow.tools.caliby.CalibyEnsembleSeqDesign`       | Caliby ensemble-aware design        | yes  | (Caliby paths)                                                            |

### Structure prediction / validation

| Runner                                            | Tool                  | GPU? | Config keys                                            |
|---------------------------------------------------|-----------------------|------|--------------------------------------------------------|
| `protflow.tools.esmfold.ESMFold`                  | ESMFold (single-chain) | yes  | `ESMFOLD_PYTHON_PATH`, `ESMFOLD_PRE_CMD`              |
| `protflow.tools.esm.ESM`                          | ESM2 embeddings / PLLs| yes  | `ESM_PYTHON_PATH`, `ESM_PRE_CMD`                       |
| `protflow.tools.colabfold.Colabfold`              | LocalColabFold (AF2)  | yes  | `COLABFOLD_SCRIPT_PATH`, `COLABFOLD_PRE_CMD`           |
| `protflow.tools.alphafold3.AlphaFold3`            | AlphaFold 3           | yes  | `ALPHAFOLD3_SCRIPT_PATH`, `ALPHAFOLD3_PYTHON_PATH`, `ALPHAFOLD3_PRE_CMD` |
| `protflow.tools.boltz.Boltz`                      | Boltz-1 / Boltz-2     | yes  | `BOLTZ_PATH`, `BOLTZ_PYTHON`, `BOLTZ_PRE_CMD`           |
| `protflow.tools.minifold.Minifold`                | Minifold              | yes  | `MINIFOLD_SCRIPT_PATH`, `MINIFOLD_PYTHON_PATH`, `MINIFOLD_PRE_CMD` |
| `protflow.tools.caliby.CalibyEnsembleGenerator`   | Caliby ensemble structures | yes | (Caliby paths)                                       |

### Refinement / repacking / docking

| Runner                                       | Tool                           | GPU? | Config keys                                                  |
|----------------------------------------------|--------------------------------|------|--------------------------------------------------------------|
| `protflow.tools.rosetta.Rosetta`             | Rosetta (any application: relax, scripts, fixbb, ...) | cpu  | `ROSETTA_BIN_PATH`, `ROSETTA_PRE_CMD`                       |
| `protflow.tools.attnpacker.AttnPacker`       | AttnPacker (sidechain packing) | yes  | `ATTNPACKER_PYTHON_PATH`, `ATTNPACKER_DIR_PATH`, `ATTNPACKER_PRE_CMD` |
| `protflow.tools.placer.PLACER`               | PLACER (sidechain repacking)   | yes  | `PLACER_SCRIPT_PATH`, `PLACER_PYTHON_PATH`, `PLACER_PRE_CMD`  |
| `protflow.tools.gnina.GNINA`                 | GNINA docking                  | yes  | (GNINA paths)                                                |
| `protflow.tools.sigmadock.SigmaDock`         | SigmaDock                      | yes  | `SIGMADOCK_SCRIPT_PATH`, `SIGMADOCK_PYTHON_PATH`, `SIGMADOCK_CKPT_PATH`, `SIGMADOCK_PRE_CMD` |
| `protflow.tools.gromacs.Gromacs`             | GROMACS MD                     | cpu (or GPU) | `GROMACS_PATH`                                       |
| `protflow.tools.gromacs.MDAnalysis`          | MDAnalysis post-processing     | cpu  | (auxiliary script)                                            |

### Edits / utilities (`protflow.tools.protein_edits`)

| Runner            | What it does                                      |
|-------------------|---------------------------------------------------|
| `ChainAdder`      | Add a chain (from another pose / sequence)         |
| `ChainRemover`    | Remove chains by ID, or keep only listed chains    |
| `SequenceAdder`   | Insert a sequence into one or more chains          |
| `SequenceRemover` | Strip residue ranges from one or more chains       |

### Metrics (`protflow.metrics.*`)

These are Runners, not just functions — they obey the same `prefix` /
`work_dir` discipline, and emit columns like every other runner.

| Runner                                                    | What it computes                                    | Config keys      |
|-----------------------------------------------------------|-----------------------------------------------------|------------------|
| `protflow.metrics.rmsd.BackboneRMSD`                      | CA / backbone RMSD vs a reference column            | —                |
| `protflow.metrics.rmsd.AtomRMSD`                          | RMSD over arbitrary atom selections                  | —                |
| `protflow.metrics.rmsd.MotifRMSD`                         | RMSD between two motif selections                    | —                |
| `protflow.metrics.tmscore.TMalign` / `TMscore`            | TM-score / TM-align                                  | `TMALIGN_PATH`*  |
| `protflow.metrics.dssp.DSSP`                              | DSSP secondary-structure assignment                  | `DSSP_PATH`      |
| `protflow.metrics.fpocket.FPocket`                        | Pocket detection / volume / druggability             | `FPOCKET_PATH`   |
| `protflow.metrics.propka.Propka`                          | pKa / electrostatics                                 | `PROPKA_PATH`*   |
| `protflow.metrics.protparam.ProtParam`                    | Biopython ProtParam (pI, instability, GRAVY, MW, εₐ) | —                |
| `protflow.metrics.frame2seqscore.Frame2SeqScore`          | Frame2Seq sequence-given-structure score             | `FRAME2SEQ_PYTHON_PATH` |
| `protflow.metrics.selection_identity.SelectionIdentity`   | One-letter / three-letter identity of a selection    | —                |
| `protflow.metrics.ligand.LigandClashes`                   | Heavy-atom clashes between a chain and the rest      | —                |
| `protflow.metrics.ligand.LigandContacts`                  | Heavy-atom contacts (with optional element filters)  | —                |
| `protflow.metrics.biopython_metrics.BiopythonMetricRunner`| Run a list of biopython metrics (Distance, Angle, …)| —                |
| `protflow.metrics.generic_metric_runner.GenericMetric`    | Run **any** Python module/function as a metric        | —                |

\* Some paths fall back to PATH lookup if not set; see the per-runner docstring.

`references/runners-catalog.md` documents every runner's `run()`
signature, expected score columns, and the typical `options` strings.

## Pipeline patterns

The five canonical pipelines below are written out fully under
`examples/`. Pick the closest match and adapt.

| Pattern                                                    | Example script                                |
|------------------------------------------------------------|-----------------------------------------------|
| Minimal "load pdbs → score → filter"                        | `examples/minimal_pipeline.py`                |
| De novo monomer: RFdiffusion → MPNN → ESMFold → BB RMSD     | `examples/rfdiffusion_mpnn_esm.py`            |
| Binder design with validation: RFdiff (hotspots) → LigandMPNN → AF2/AF3 → ipTM filter | `examples/binder_design_rfdiff_validate.py` |
| Ligand co-folding: load fastas → AlphaFold3 with SMILES     | `examples/predict_protein_ligand.py`          |
| Enzyme redesign: load pocket → LigandMPNN (fixed catalytic) → Rosetta relax → metrics | `examples/enzyme_redesign.py` |

The general recipe in every case is:

```python
poses = Poses(...).set_jobstarter(...)              # 1. Load inputs
poses = backbone_gen.run(poses, prefix="bb", ...)    # 2. Generate / load backbones
poses = seq_design.run(poses, prefix="seq", ...)     # 3. Sequence design
poses = predictor.run(poses, prefix="pred", ...)     # 4. Structure prediction / validation
poses = metric.run(poses, prefix="m", ...)           # 5. Quantitative scoring
poses.filter_poses_by_value(...)                     # 6. Filter
poses.filter_poses_by_rank(...)                      # 6.
poses.calculate_composite_score(...)                 # 7. (Optional) composite ranking
poses.save_scores(); poses.save_poses("out/")       # 8. Persist
```

When you re-run the script after a crash, ProtFlow short-circuits any step
whose `<prefix>_scores.<storage_format>` file already exists — so debugging
is "fix the broken step, re-run the script, watch only the broken step
re-execute".

## Troubleshooting

The single most common failure mode is a runner failing inside
`collect_scores()`. ProtFlow's auto-wrapper appends the tail of the SLURM /
local stderr to the exception. **Read the appended log first** — it is
almost always the real error (CUDA OOM, missing input file, malformed
contig, etc.), not the Python traceback above it.

Other failure modes and fixes:

| Symptom                                              | Likely cause                                                    | Fix |
|------------------------------------------------------|------------------------------------------------------------------|-----|
| `MissingConfigError` at import / first runner build  | No `config.py` resolvable                                       | `protflow-init-config` (or set `$PROTFLOW_CONFIG`). |
| `ProtFlowConfigError: Missing parameter ... in config.py` | A required key isn't in `config.py`                       | Copy the matching line from `config_template.py` into your `config.py` and fill it in. |
| `MissingConfigSettingError: Variable ... not specified` | Key exists but the value is `""`                            | Set the value (path to script / python / pre_cmd). |
| `FileNotFoundError: Path set for X does not exist`   | The path in `config.py` points somewhere invalid                | Fix the path. Use `protflow-check-config` to identify which file you're editing. |
| `KeyError: Column prefix already taken in poses.df`  | You re-used a `prefix` across two `.run()` calls                | Pick a unique `prefix`. ProtFlow refuses to overwrite. |
| Runner returns "Found existing scorefile ... returning N poses without running" but you expected a fresh run | Cached score file from a previous run | Pass `overwrite=True` (or delete `<work_dir>/<prefix>/<prefix>_scores.*`). |
| SLURM jobs run forever / never appear in `squeue`    | Bad `options` (e.g. invalid `--partition`)                       | Check `<work_dir>/<prefix>/<jobname>_slurm.err` and `_jobstarter.log`. |
| `RuntimeError: Number of output poses is smaller than ...` | Some array tasks crashed                                  | Inspect the appended stderr block in the exception; rerun with `overwrite=False` after fixing the crashed inputs. |
| `KeyError: Could not find <col> in poses dataframe!` | Referenced a column that wasn't created                          | Run the step that produces that column, or fix the column name. |
| ProtFlow ignores a `pose_options` column             | Passed a literal list with wrong length, or wrong column name    | Length must equal `len(poses)`; spelling must match `poses.df` exactly. |

`references/troubleshooting.md` has the long-form walkthrough.

## Extending ProtFlow with a custom runner

Every runner is a subclass of `protflow.runners.Runner` with three methods:

```python
from protflow.runners import Runner, RunnerOutput
from protflow.poses import Poses
from protflow.jobstarters import JobStarter

class MyTool(Runner):
    def __init__(self, jobstarter: JobStarter = None):
        self.jobstarter = jobstarter
        self.index_layers = 1   # how many '_N' suffixes the tool appends per pose

    def __str__(self):
        return "mytool"

    def run(self, poses: Poses, prefix: str, jobstarter: JobStarter = None,
            options: str = None, overwrite: bool = False) -> Poses:
        # 1) Standard setup
        work_dir, jobstarter = self.generic_run_setup(
            poses=poses, prefix=prefix,
            jobstarters=[jobstarter, self.jobstarter, poses.default_jobstarter]
        )

        # 2) Cache-hit short-circuit
        scorefile = f"{work_dir}/{prefix}_scores.{poses.storage_format}"
        if (scores := self.check_for_existing_scorefile(scorefile, overwrite)) is not None:
            return RunnerOutput(poses=poses, results=scores, prefix=prefix,
                                index_layers=self.index_layers).return_poses()

        # 3) Build cmds (one per pose, or batched)
        cmds = [f"mytool --in {p} --out {work_dir}/{d}.out"
                for p, d in zip(poses.poses_list(), poses.df['poses_description'])]

        # 4) Submit & wait
        jobstarter.start(cmds=cmds, jobname="mytool", wait=True, output_path=work_dir)

        # 5) Collect into a DataFrame with mandatory 'description' + 'location'
        scores = my_collect_function(work_dir)
        self.save_runner_scorefile(scores=scores, scorefile=scorefile)

        # 6) Merge back into poses
        return RunnerOutput(poses=poses, results=scores, prefix=prefix,
                            index_layers=self.index_layers).return_poses()
```

That's the entire contract. The base class's `__init_subclass__` will
auto-wrap your `run()` to attach stderr context on crash.

`references/runners-pattern.md` shows three real subclasses
(`ESMFold` end-to-end, `LigandMPNN` with `pose_opt_cols`, `BackboneRMSD`
as a non-jobstarter local Runner) annotated line-by-line.

## Where to look next

- `references/installation.md` — full installation matrix and pin notes.
- `references/config.md` — every `*_PATH` / `*_PYTHON_PATH` / `*_PRE_CMD` key.
- `references/poses.md` — every `Poses` method with semantics and gotchas.
- `references/jobstarters.md` — local vs SLURM, batching, error capture, sacct.
- `references/slurm.md` — cluster-side tips (`squeue -n`, array limits, `--open-mode`).
- `references/runners-pattern.md` — the Runner contract, annotated examples.
- `references/runners-catalog.md` — every runner's `run()` signature.
- `references/options-and-pose-options.md` — `options` / `pose_options` / `pose_opt_cols` syntax per runner.
- `references/residue-selection.md` — `ResidueSelection`, `AtomSelection`, the four selectors.
- `references/motif-tracking.md` — how `update_motifs` works through RFdiffusion.
- `references/filtering-and-scoring.md` — `filter_poses_by_*` and `calculate_*_score`.
- `references/metrics.md` — every metric runner with output columns.
- `references/troubleshooting.md` — failure modes and fixes.
- `references/cli-tools.md` — `protflow-init-config`, `protflow-set-config`, `protflow-check-config`.
- `examples/` — full runnable scripts.
