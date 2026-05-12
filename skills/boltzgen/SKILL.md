---
name: boltzgen
description: >
  Run BoltzGen, an open all-atom diffusion model for universal binder
  design — generates ranked, filtered binder candidates from a single YAML
  specification. Use this skill when:
  (1) De novo designing protein, peptide, cyclic-peptide, helicon, or
      stapled-peptide binders against a protein target,
  (2) Designing nanobody / VHH CDR loops against a target,
  (3) Designing antibody (Fab) CDR loops against a target,
  (4) De novo designing protein binders against a small-molecule ligand
      (SMILES or CCD), with built-in binding-affinity prediction,
  (5) Designing protein binders against DNA / RNA / nucleic-acid targets
      (e.g., de novo zinc fingers against DNA),
  (6) Designing against disordered regions or peptides shown as a fixed
      sequence with no structure,
  (7) Redesigning or optimizing residues on an existing complex
      (`protein-redesign` protocol — symmetric dimers, scaffold optimization),
  (8) Inverse-folding a fully specified backbone with BoltzGen's IF model
      (`--only_inverse_fold`) — replaces ProteinMPNN with a model trained
      jointly with the diffusion backbone,
  (9) Producing an experimentally-rankable filtered set with built-in
      analysis (refolding RMSD, PLIP H-bonds / salt bridges, iPTM, PAE,
      hydrophobic patch, SASA, sequence diversity / novelty),
  (10) Running large campaigns (10k–60k intermediate designs) on a single
       GPU, multiple GPUs (DDP), or a SLURM job array with merge + refilter.

  Covers installation (pip, source, Docker, conda), the seven-step pipeline
  (design → inverse_folding → folding → design_folding → affinity → analysis
  → filtering), all six protocols (protein-anything, peptide-anything,
  protein-small_molecule, antibody-anything, nanobody-anything,
  protein-redesign), the full YAML schema (entities: protein / ligand / file;
  sequence length ranges, secondary-structure conditioning, binding /
  not-binding residues, structure-group visibility, design / not_design
  masks, design_insertions, residue_constraints, cyclic, symmetric_group,
  reset_res_index, fuse, use_assembly, include_proximity), constraints
  (bond, total_len, leaving_atoms), antibody / nanobody scaffold libraries,
  small-molecule via CCD and SMILES with covalent constraints, the
  `boltzgen run / check / configure / execute / download / merge` CLI
  surface, output layout (intermediate_designs, refold_cif,
  final_ranked_designs, results_overview.pdf), filtering re-runs
  (`--steps filtering` and `filter.ipynb`), SLURM job arrays with
  `boltzgen merge`, and training the diffusion / inverse-folding models.

  Pairs with: `boltz` (Boltz-2 powers the refolding + affinity steps inside
  BoltzGen — use it standalone for further validation), `ipsae` (better
  ranking than the default ipTM-based scoring), `protein-qc` (post-pipeline
  QC thresholds, biophysical liabilities), `binder-design` (tool-selection
  guidance vs. RFdiffusion / BindCraft), `bindcraft` (hallucination-based
  alternative with built-in AF2 validation), `rfdiffusion` (backbone-only
  alternative, faster but less side-chain aware), `proteinmpnn` /
  `ligandmpnn` / `solublempnn` (alternative inverse folders), `chai` /
  `alphafold` (alternative structure predictors for downstream validation),
  `foldseek` (novelty / structural-cluster QC).
license: MIT
category: design-tools
tags: [protein-design, binder-design, peptide-design, antibody-design, nanobody-design, all-atom-diffusion, inverse-folding, small-molecule-binder, cyclic-peptide, foundation-model]
repo: https://github.com/HannesStark/boltzgen
preprint: https://hannes-stark.com/assets/boltzgen.pdf
biorxiv_doi: 10.1101/2025.11.20.689494
slack: https://boltz.bio/join-slack
pypi: https://pypi.org/project/boltzgen/
huggingface: https://huggingface.co/boltzgen
---

# BoltzGen — Universal All-Atom Binder Design

## What this is

BoltzGen is an MIT-licensed (code + weights) all-atom diffusion model from
the Barzilay / Jaakkola groups at MIT for **universal binder design**.
A single YAML specification produces a ranked, filtered set of binders
covering an unusually broad design space:

| You design …                                          | Against …                                  | Protocol                  |
|-------------------------------------------------------|--------------------------------------------|---------------------------|
| Mini-proteins (~30 – 200 aa)                          | Protein, peptide, IDR, or disordered chain | `protein-anything`        |
| Linear / cyclic / disulfide / stapled peptides        | Anything                                   | `peptide-anything`        |
| Mini-proteins                                         | Small molecule (SMILES or CCD code)        | `protein-small_molecule`  |
| Nanobody / VHH CDR loops                              | Protein target                             | `nanobody-anything`       |
| Antibody Fab CDR loops (heavy + light)                | Protein target                             | `antibody-anything`       |
| Sequence redesign of an existing backbone             | Itself (symmetric, monomer, complex)       | `protein-redesign`        |

Other things BoltzGen can do that most "binder" tools cannot:
- Bind DNA / RNA (e.g., de novo zinc fingers against B-DNA).
- Condition on **specific binding residues** *and* **anti-binding residues**.
- Condition on **secondary structure** of designed regions (`H`/`E`/`L`).
- Insert variable-length **designed loops** into existing backbones
  (`design_insertions`), used heavily for antibody / nanobody scaffolding.
- Apply **per-position residue whitelists / blacklists**
  (`residue_constraints`).
- Sample **variable-length** designs in a single run
  (`sequence: 80..140` randomly samples the length).
- Honor arbitrary **covalent bonds** for staples, disulfides, head-to-tail
  cyclization, and covalent small-molecule chemistry (SG–CK, SG–CH, OG–C1, …).
- Use **antibody / nanobody scaffold libraries** as drop-in files.
- Optionally fold the binder **without** the target as an extra confidence
  check (`design_folding`, on by default for protein targets).
- Predict **small-molecule binding affinity** with Boltz-2 (`affinity` step,
  on by default for `protein-small_molecule`).
- Filter the result by **biophysical liabilities** (cysteines, ALA / GLY /
  GLU / LEU / VAL composition outliers, hydrophobic patches).
- **Diversity-optimize** the final set (`--alpha` between 0=quality only
  and 1=diversity only).
- **Rerun filtering** without redoing GPU work (`--steps filtering`,
  ~15 sec) or with the bundled `filter.ipynb`.

Underneath, BoltzGen ships **five** checkpoints that are downloaded on
first use (~6 GB total, into `~/.cache` or `$HF_HOME`):

| Checkpoint                  | Step                | Notes                                                      |
|-----------------------------|---------------------|------------------------------------------------------------|
| `boltzgen1_diverse.ckpt`    | `design`            | Diffusion backbone — diversity-tuned                       |
| `boltzgen1_adherence.ckpt`  | `design`            | Diffusion backbone — site-adherence-tuned                  |
| `boltzgen1_ifold.ckpt`      | `inverse_folding`   | Inverse-folding model trained jointly with diffusion        |
| `boltz2_conf_final.ckpt`    | `folding` (refold)  | Boltz-2 structure (binder + target re-prediction)          |
| `boltz2_aff.ckpt`           | `affinity`          | Boltz-2 affinity head (log10 IC50 + binder probability)    |

By default the design step **alternates** between the two diffusion
checkpoints (half each) — pass `--design_checkpoints <one.ckpt>` to use
only one, or list more.

## Prerequisites

| Requirement | Minimum                                    | Notes                                                                 |
|-------------|--------------------------------------------|-----------------------------------------------------------------------|
| OS          | Linux                                      | Docker image is `nvidia/cuda:12.2.2-cudnn8-devel-ubuntu22.04`         |
| Python      | **≥ 3.11** (`requires-python = ">=3.11"`)  | Project pins `numpy==2.0.2`, `numba==0.61.0` — use a fresh env        |
| GPU         | NVIDIA, CUDA 12.x, bfloat16                | A100 / H100 / L40S recommended; CUDA-capability ≥ 8 auto-enables `cuequivariance` kernels — older GPUs: `--use_kernels false` |
| VRAM        | ≥ 24 GB practical                          | OOMs go up roughly with target size + binder length + diffusion batch |
| Disk        | ~6 GB cache + design output                | Weights into `~/.cache` (override with `--cache` or `$HF_HOME`)       |
| Network     | First weight download + first moldir pull  | Then can run offline                                                  |

CPU-only is technically possible but pointless for production runs —
treat that as unit-test mode only.

## Three-step quick start

### 1) Install

```bash
# Recommended — fresh conda env with Python 3.12
conda create -n bg python=3.12 -y
conda activate bg
pip install boltzgen

# Or editable install from a clone
git clone https://github.com/HannesStark/boltzgen
cd boltzgen && pip install -e .

# Or Docker
docker build -t boltzgen .
docker run --rm --gpus all \
  -v "$(realpath workdir)":/workdir \
  -v "$(realpath cache)":/cache \
  -v "$(realpath example)":/example \
  boltzgen boltzgen run /example/vanilla_protein/1g13prot.yaml \
    --output /workdir/test --protocol protein-anything --num_designs 2
```

A `boltzgen` console script is installed with five subcommands:
`run`, `configure`, `execute`, `download`, `check`, `merge`.

### 2) Write a `.yaml` spec and verify it

```yaml
# binder.yaml — design a ~100-aa mini-protein against chain A of 1g13.cif
entities:
  - protein:
      id: B
      sequence: 80..140         # random length in [80, 140]
  - file:
      path: 1g13.cif            # relative to *this* yaml's directory
      include:
        - chain:
            id: A
```

```bash
# Validate the spec and visualize the constraints
boltzgen check binder.yaml
# (open the resulting *.cif in https://molstar.org/viewer/ —
#  the binding-site / design regions are colored differently)
```

### 3) Run the full pipeline

```bash
boltzgen run binder.yaml \
  --output workbench/test_run \
  --protocol protein-anything \
  --num_designs 50      # use 10,000 – 60,000 for a real campaign
# Output → workbench/test_run/final_ranked_designs/{intermediate_ranked_N_designs, final_<budget>_designs, results_overview.pdf}
```

If the run is interrupted, restart with `--reuse` — no GPU work is lost.

If you only want to retune filters after generation: `boltzgen run binder.yaml --steps filtering --output workbench/test_run ...` (~15 sec).

## ⚠️ The single rule that catches almost everyone

> **All residue indices are 1-based and use the canonical mmCIF
> `label_asym_id`, NOT the author chain ID / residue number.**
> Verify in Molstar: hover over a residue and read the index on the
> bottom right. The author IDs *will* mislead you if you trust PyMOL,
> ChimeraX, or your downloaded PDB blindly.

And the one that gets everyone *next*:

> **File references inside a YAML are resolved relative to the YAML
> file's directory, not your CWD.**

## CLI at a glance

| Subcommand              | Purpose                                                                                                             |
|-------------------------|---------------------------------------------------------------------------------------------------------------------|
| `boltzgen run SPEC …`   | Run the full design → IF → folding → analysis → filtering pipeline. The main entry point.                            |
| `boltzgen check SPEC …` | Validate one or more `.yaml` specs and write a colored mmCIF you can open in Molstar to sanity-check binding sites.  |
| `boltzgen configure SPEC …` | Generate resolved Hydra step configs in `--output` *without* executing them (so you can hand-edit and then `execute`). |
| `boltzgen execute DIR`  | Run a pipeline from a pre-configured directory produced by `configure`.                                              |
| `boltzgen download …`   | Pre-fetch checkpoints / moldir into `--cache` (not normally needed — `run` lazily downloads).                        |
| `boltzgen merge DIRS… --output …` | Combine outputs from multiple parallel runs (e.g., SLURM array tasks) before running `--steps filtering` on the merged set. |

Most-used `run` flags:

| Flag                              | Effect                                                                                                  |
|-----------------------------------|---------------------------------------------------------------------------------------------------------|
| `--protocol P`                    | One of `protein-anything` (default), `peptide-anything`, `protein-small_molecule`, `antibody-anything`, `nanobody-anything`, `protein-redesign`. |
| `--num_designs N`                 | Total intermediate designs to generate (defaults 10000; aim for 10k–60k for real campaigns).             |
| `--budget B`                      | Size of the diversity-optimized final set produced by filtering (default 30).                            |
| `--alpha A`                       | Quality-vs-diversity knob for filtering (0=quality, 1=diversity; default 0.001, or 0.01 for peptide).    |
| `--steps STEPS…`                  | Run only specific steps from `{design, inverse_folding, design_folding, folding, affinity, analysis, filtering}`. |
| `--reuse`                         | Re-attach to an existing `--output` and only generate the missing designs.                               |
| `--devices N`                     | GPUs to use; multi-GPU within a step works via Lightning DDP.                                            |
| `--cache PATH`                    | Where to download / cache weights (defaults to `~/.cache`; same as `$HF_HOME`).                          |
| `--diffusion_batch_size N`        | Per-trunk diffusion batch (auto-set to 1 if `num_designs<100`, else 10; large batches sample fewer lengths). |
| `--design_checkpoints A.ckpt B.ckpt …` | Use a custom or single checkpoint (defaults to both `diverse` and `adherence`).                     |
| `--inverse_fold_num_sequences K`  | Sequences sampled per generated backbone (default 1; raise to e.g. 5 if `--num_designs` is small).       |
| `--skip_inverse_folding`          | Use the diffusion sequence directly without IF.                                                          |
| `--only_inverse_fold`             | Skip diffusion — IF an existing structure end-to-end (replaces ProteinMPNN).                             |
| `--inverse_fold_avoid LETTERS`    | Disallowed residues, e.g. `KEC`; default is none for protein, `C` for peptide / antibody / nanobody.     |
| `--step_scale X` / `--noise_scale X` | Replace the diffusion sampling schedule with a constant (1.8 / 0.98 are typical hand-set values).     |
| `--filter_biased true/false`      | Default ALA/GLY/GLU/LEU/VAL composition caps; turn off if you genuinely want biased designs.              |
| `--additional_filters 'X>0.3' 'Y<2.5'` | Hard filters on any analyzed metric; **single-quote** because of `<`/`>`.                            |
| `--metrics_override k=w …`        | Re-weight ranking — larger weight = less important; `k=none` removes a metric entirely.                  |
| `--size_buckets 10-20:5 20-30:10` | Cap the number of designs per length bucket in the final set.                                            |
| `--refolding_rmsd_threshold X`    | RMSD threshold for "design folds as predicted" hard filter (lower is better).                            |
| `--use_kernels {auto,true,false}` | cuEquivariance kernels. `auto` enables on capability ≥ 8. Use `false` on old GPUs.                       |
| `--no_subprocess`                 | Run steps in-process — required for some debugging, but breaks `devices>1`.                              |

Full flag list per subcommand is in [references/cli.md](references/cli.md).

## Choosing the right reference doc

| You want to…                                                                  | Read                                                          |
|-------------------------------------------------------------------------------|---------------------------------------------------------------|
| Install (pip / conda / Docker / dev), configure cache, fetch weights manually | [references/installation.md](references/installation.md)      |
| See every CLI flag for `run`, `configure`, `execute`, `download`, `check`, `merge` | [references/cli.md](references/cli.md)                   |
| Author the YAML (entities, sequence ranges, binding, structure groups, design / not_design, insertions, residue constraints, scaffolds, file include / exclude / proximity / assembly / fuse / reset_res_index) | [references/yaml-spec.md](references/yaml-spec.md) |
| Pick a protocol and understand its per-step config differences                | [references/protocols.md](references/protocols.md)            |
| Understand each pipeline step (what runs, what it writes, when to skip it)    | [references/pipeline.md](references/pipeline.md)              |
| Tune filtering / ranking, rerun in the Jupyter notebook, use `--metrics_override`, `--additional_filters`, `--alpha`, `--size_buckets` | [references/filtering.md](references/filtering.md) |
| Read the output directory (CIF, NPZ, refold_cif, refold_design_cif, metrics CSVs, `results_overview.pdf`) | [references/outputs.md](references/outputs.md) |
| Run on SLURM as a job array + `boltzgen merge` + refilter                     | [references/slurm.md](references/slurm.md)                    |
| Train BoltzGen / inverse-fold from scratch on your own data                   | [references/training.md](references/training.md)              |
| Diagnose OOMs, weight-download / HF auth issues, kernel errors, MSA fallbacks, wrong residue indices, etc. | [references/troubleshooting.md](references/troubleshooting.md) |

## Example library

Each example in [`examples/`](examples/) is a self-contained, fully
commented YAML you can drop into a `boltzgen run` invocation. Coverage:

| File                              | Use case                                                                                  |
|-----------------------------------|-------------------------------------------------------------------------------------------|
| `vanilla_protein_binder.yaml`     | Minimal protein binder against a target chain, no binding site specified                  |
| `protein_with_binding_site.yaml`  | Same, but conditioning on specific binding-site residues                                  |
| `peptide_with_binding_site.yaml`  | Linear peptide binder with a binding-site spec                                            |
| `cyclic_peptide.yaml`             | Head-to-tail cyclic peptide                                                               |
| `disulfide_peptide.yaml`          | Multi-disulfide-stapled peptide + secondary-structure conditioning                        |
| `helicon_with_staple.yaml`        | Helical peptide stapled with the small-molecule WHL "staple" via two covalent bonds       |
| `cyclotide.yaml`                  | Cyclic peptide with three disulfide bridges (e.g., 3IVQ)                                  |
| `nanobody.yaml`                   | Nanobody CDR design using a library of scaffolds                                          |
| `nanobody_scaffold.yaml`          | A single nanobody scaffold YAML (referenced from `nanobody.yaml`)                         |
| `antibody_fab.yaml`               | Fab CDR design against a target with a scaffold library                                   |
| `antibody_fab_scaffold.yaml`      | A single Fab scaffold YAML                                                                |
| `protein_against_small_molecule.yaml` | Protein binder against a SMILES ligand (de novo small-molecule binder)                |
| `small_molecule_via_ccd.yaml`     | Protein binder against a ligand specified by CCD code (e.g., TSA chorismite)              |
| `covalent_small_molecule.yaml`    | Covalent small-molecule chemistry — bonds from both CCD and SMILES atoms                  |
| `zinc_finger_against_dna.yaml`    | De novo zinc finger redesigned against DNA (uses `design`, `not_design`, `design_insertions`, `reset_res_index`) |
| `disordered_target.yaml`          | Bind a disordered region (target shown as fixed sequence, no structure)                   |
| `disordered_peptide_as_string.yaml` | Bind a fixed peptide given as a sequence (no CIF needed)                                |
| `flexible_target_assembly.yaml`   | Use `use_assembly: true` and `structure_groups` to hide flexible loops of the target      |
| `redesign_symmetric_dimer.yaml`   | `protein-redesign` protocol with `symmetric_group` to tie chains during inverse folding   |
| `inverse_folding_only.yaml`       | `--only_inverse_fold` — IF an existing complex from a CIF                                 |
| `residue_constraints.yaml`        | Per-position whitelist / blacklist of amino acids                                         |
| `design_spec_kitchen_sink.yaml`   | One file demonstrating every feature listed in YAML reference                             |

## Quick decision tree

- **I have a target protein and want a binder. Nothing fancy.**
  → `protein-anything`. Spec: one designed protein with a length range,
  one `file` entity for the target. See `examples/vanilla_protein_binder.yaml`.

- **I want the binder to hit a *specific* pocket.**
  → Same protocol, add `binding_types: - chain: id: A: binding: 5..7,13`
  to the target entity. Run `boltzgen check` first and visualize.

- **I want a peptide (not a mini-protein).**
  → `peptide-anything`. By default no cysteines are inverse-folded
  (`--inverse_fold_avoid C`) and `design_folding` is skipped.
  Set `cyclic: true` on the protein entity for head-to-tail cyclization.
  Add explicit Cys positions in the sequence string and `bond:` constraints
  for disulfides or staples.

- **I want a stapled peptide using WHL (or any chemistry).**
  → Declare the staple as a `ligand: ccd: WHL` (or SMILES), add two `bond:`
  constraints between designed Cys SG atoms and the staple atom names. See
  `examples/helicon_with_staple.yaml`.

- **I want a nanobody / antibody.**
  → `nanobody-anything` / `antibody-anything`. Use the scaffold libraries
  in `example/nanobody_scaffolds/` and `example/fab_scaffolds/` from the
  upstream repo as inspiration. The pattern is: include + design (the CDRs)
  + structure_groups visibility 0 over the CDRs + exclude + design_insertions
  + reset_res_index. CDRs get random insertion lengths.

- **Small-molecule binder.**
  → `protein-small_molecule`. Spec: designed protein + ligand (`ccd` or
  `smiles`). Affinity prediction is automatically on. For covalent
  inhibitors add `bond:` constraints to the ligand.

- **Bind DNA or RNA.**
  → Treat the nucleic acid as a `file` entity (CIF or PDB). For new zinc
  fingers see `examples/zinc_finger_against_dna.yaml`.

- **Bind a disordered peptide / region.**
  → Two options: (a) provide a CIF for the target and hide structure with
  `structure_groups: visibility: 0`, OR (b) declare the target as a
  `protein` entity with a fixed sequence string (no structure at all).
  See `examples/disordered_*.yaml`.

- **Redesign sequences on an existing backbone (no diffusion).**
  → `--only_inverse_fold` (one diffusion-free call to the IF model). For
  symmetric multimers use the `protein-redesign` protocol and tag chains
  with `symmetric_group: 1`.

- **Resume an interrupted run.**
  → Same command + `--reuse`. Already-finished designs are kept.

- **I generated designs and want to tune filters / ranking only.**
  → `boltzgen run SPEC --steps filtering --output OLD_OUT …` (~15 s) or
  open the bundled `filter.ipynb`.

- **I want to run a 60,000-design campaign across many GPUs.**
  → SLURM job array of `boltzgen run … --num_designs 1000` tasks +
  `boltzgen merge task-*` + `boltzgen run … --steps filtering`. See
  `references/slurm.md`.

- **I want to validate my picks further.**
  → Re-fold the final binders with Boltz-2 directly (`boltz` skill,
  `--use_msa_server`), or with Chai-1 / AF-Multimer; then re-rank with
  `ipsae` for a much stronger binder-quality score than ipTM alone.

If BoltzGen is not the right tool:
- **RFdiffusion** (`rfdiffusion` skill) — fast backbone-only diffusion;
  pair with ProteinMPNN. Less side-chain aware but cheaper.
- **BindCraft** (`bindcraft` skill) — AF2-hallucination with built-in
  validation; high empirical success on protein targets, less flexible
  on chemistry.
- **DiscoDiff / Disco** (`disco` skill), **Genie3** (`genie3` skill),
  **Chroma**, **Proteus** — other diffusion backbone generators.

## Hard rules / gotchas

1. **1-indexed, label-asym residues everywhere.** `sequence`, `res_index`,
   `bond.atom1`, `bond.atom2`, `binding`, `not_binding`, `design`,
   `not_design`, `design_insertions.res_index`, etc. Check in Molstar.

2. **Relative paths.** Any `path: file.cif` inside a YAML is resolved
   relative to the *YAML's* directory, not your CWD. `path:` can also be a
   *list* of YAML files (for scaffold libraries — each scaffold is itself
   a `file`-shaped YAML).

3. **Bond atom names are CCD-standard, case-sensitive.** `SG`, `CK`, `CH`,
   `OG`, `C1`, `N`, … For a SMILES ligand `D`, atom names are element +
   index, e.g. `C6` is the 6th carbon as written in the SMILES.

4. **Sequence length ranges sample once per diffusion batch.**
   `sequence: 80..140` with `--diffusion_batch_size 10` and only 10
   intermediate designs gives you 10 designs all of the *same* length.
   For balanced sampling across lengths, keep batch size small *or*
   `num_designs` large.

5. **`--num_designs` is *intermediate* designs, before filtering.** The
   final set has `--budget` designs. Typical ratio is 10000 : 30.

6. **Inverse folding avoids Cys by default for peptide / antibody /
   nanobody protocols.** Override with `--inverse_fold_avoid ""` if you
   want them back (e.g., for new disulfide chemistry).

7. **Visibility hides structure, not residues.** `structure_groups:
   visibility: 0` for a residue range tells the model the structure of
   those residues is *unknown* (they still exist as sequence). Useful for
   flexible loops, disordered tails, and "use this peptide but don't
   anchor its position".

8. **`include_proximity`** crops the target to residues within `radius`
   Å of a reference selection. Indispensable for large targets to keep
   GPU memory / accuracy reasonable.

9. **`use_assembly: true`** instantiates biological assemblies in a CIF
   (chains get suffix numbers like `A1`, `B1`, `A2`, …). Use it when the
   functional unit is a multimer and the asymmetric unit isn't.

10. **`reset_res_index`** renumbers chain residues consecutively from 1
    after `include` / `exclude` operations. Critical for antibody /
    nanobody scaffolds where you cut out the CDRs (`exclude`) and then
    insert design loops back in (`design_insertions`).

11. **`design`** marks residues for redesign on a `file`-loaded chain;
    `not_design` *removes* residues from `design`. Useful when an entire
    chain should be redesigned *except* for catalytic / structural ones.

12. **`fuse: A`** on a `file` entity grafts the included segment onto a
    sibling `protein` entity with the same chain id — handy for splicing
    fixed N-terminal anchors onto a designed body.

13. **Filtering is fast and cheap.** Always plan to run it 2–5 times with
    different `--metrics_override`, `--additional_filters`, `--alpha`,
    `--refolding_rmsd_threshold` settings (or just use `filter.ipynb`).

14. **The output directory is intentionally reusable.** Pass `--reuse`
    to top up an existing run; pass `--steps filtering` to refilter only.
    To re-generate designs from scratch, point `--output` somewhere new
    or delete the existing `intermediate_designs/`.

15. **`--devices > 1` requires `--no_subprocess` to be OFF (the default).**
    `--no_subprocess` keeps everything in the main process — only useful
    for single-GPU debugging.

16. **Large `--diffusion_batch_size` × small `--num_designs`** trades
    coverage of the length range for speed. Default heuristic
    (1 if `num_designs<100`, else 10) is reasonable; raise to 16–32 on
    H100s if VRAM permits and you have many designs to generate.

17. **For protein targets with no MSA available**, BoltzGen still runs
    (the design step does not call ColabFold) — the folding step uses
    Boltz-2 with target features built from the input CIF directly.
    There is no `--use_msa_server` flag (unlike Boltz standalone).

## Installing this skill

```bash
# Symlink (recommended — picks up edits live)
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/boltzgen

# Or copy
cp -R . ~/.claude/skills/boltzgen
```

After that, an agent can invoke it via `Skill(skill="boltzgen")`.

## Citation

```bibtex
@article{stark2025boltzgen,
  author  = {Stark, Hannes and Faltings, Felix and Choi, MinGyu and Xie, Yuxin and Hur, Eunsu and O'Donnell, Timothy John and Bushuiev, Anton and Uçar, Talip and Passaro, Saro and Mao, Weian and Reveiz, Mateo and Bushuiev, Roman and Pluskal, Tomáš and Sivic, Josef and Kreis, Karsten and Vahdat, Arash and Ray, Shamayeeta and Goldstein, Jonathan T. and Savinov, Andrew and Hambalek, Jacob A. and Gupta, Anshika and Taquiri-Diaz, Diego A. and Zhang, Yaotian and Hatstat, A. Katherine and Arada, Angelika and Kim, Nam Hyeong and Tackie-Yarboi, Ethel and Boselli, Dylan and Schnaider, Lee and Liu, Chang C. and Li, Gene-Wei and Hnisz, Denes and Sabatini, David M. and DeGrado, William F. and Wohlwend, Jeremy and Corso, Gabriele and Barzilay, Regina and Jaakkola, Tommi},
  title   = {BoltzGen: Toward Universal Binder Design},
  year    = {2025},
  doi     = {10.1101/2025.11.20.689494},
  journal = {bioRxiv}
}
```
