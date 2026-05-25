---
name: placer
description: >
  Run PLACER (Protein-Ligand Atomistic Conformational Ensemble Resolver,
  formerly ChemNet) — a Baker-lab graph neural network that operates entirely
  at the atomic level to denoise / rebuild small-molecule and protein-sidechain
  atom positions, and to generate stochastic ensembles that model conformational
  heterogeneity. Use this skill when:
  (1) Docking a ligand that is **already present** in an input PDB / mmCIF into
      its binding pocket and scoring pose confidence (the headline use case),
  (2) Predicting / rebuilding protein **side-chain** conformations around a
      ligand or in an apo pocket (sidechain repacking with confidence),
  (3) Generating a conformational **ensemble** (50-200 stochastic samples) of a
      ligand + pocket to study heterogeneity rather than a single pose,
  (4) Validating designed enzyme / heme-binder / metalloprotein active sites by
      checking whether PLACER re-resolves the intended ligand pose at low prmsd,
  (5) Co-predicting **multiple ligands** in one pocket (`--predict_multi`),
      keeping cofactors (e.g. heme) fixed while docking an inhibitor,
  (6) Refining atom typing / bond perception of a ligand via an SDF / MOL2
      reference so aromatic rings stay planar (`--ligand_file`),
  (7) Predicting with **non-canonical amino acids** or custom residues supplied
      as a residue JSON (added to the internal CCD library),
  (8) Mutating positions in silico (`--mutate`) and re-resolving the local
      structure, optionally with the small molecule removed (`--no-use_sm`),
  (9) Adding explicit inter-atomic **bonds** (`--bonds`) or steering the crop /
      corruption centers for refinement or (loose) global docking.

  This skill is written for running PLACER from an **Apptainer / Singularity
  SIF container** (the conda env is heavy: CUDA 12.1 + torch 2.3 + dgl 2.4 +
  openbabel + e3nn + NVIDIA SE3Transformer). It covers building the SIF from
  the provided `PLACER.def`, the `apptainer exec --nv` invocation pattern
  (binds, GPU, the relative-`--weights` gotcha), every `run_PLACER.py` CLI flag,
  the ligand-naming convention (`<chain>-<name3>-<resno>`), the Python API
  (`PLACER.PLACER` / `PLACERinput`), the output layout (`*_model.pdb` multimodel
  +  `*.csv` scores), and the confidence scores (prmsd / plddt / plddt_pde /
  fape / lddt / rmsd / kabsch) and how to rank with them.

  Limitations: ligands must already exist (with coordinates) in the input — you
  **cannot** dock from a bare SMILES/SDF against an apo protein; crop size is
  ~600 atoms; hydrogens are not predicted.

  Pairs with: `invrotzyme` / `foundry` (RFdiffusionAA) / `disco` / `boltzgen`
  (generate the enzyme / binder active sites that PLACER then validates),
  `boltz` / `chai-lab` (full-complex structure prediction — PLACER is the
  atomistic pocket / sidechain specialist, not a global folder), `protflow`
  (which wraps `run_PLACER.py` as a pipeline runner for sidechain repacking).
license: BSD-3-Clause
category: protein-design
tags: [protein-design, ligand-docking, sidechain-prediction, conformational-ensemble, graph-neural-network, all-atom, enzyme-design, heme, metalloprotein, apptainer, singularity, baker-lab]
repo: https://github.com/baker-laboratory/PLACER
biorxiv: https://www.biorxiv.org/content/10.1101/2024.09.25.614868v1
---

# PLACER — Protein-Ligand Atomistic Conformational Ensemble Resolver

## What this is

PLACER is a graph neural network in which **the nodes are atoms**. It was
trained to recover correct atom positions from partially corrupted input
structures (Cambridge Structural Database + PDB). Given the atom composition
and bonding of a small molecule plus the surrounding protein context, it
rebuilds the small molecule and nearby protein side chains. It is a fast,
**stochastic** denoiser — running it N times yields an *ensemble* of solutions,
which is how you both improve a pose and read off conformational heterogeneity.

Two things it is good at:
- **Ligand docking / pose scoring** given approximate knowledge of the binding
  site (the ligand must already be in the input structure with coordinates).
- **Side-chain prediction** around a ligand or in an apo pocket, with per-atom
  confidence written to the PDB b-factor column.

The upstream repo lives at `~/Repos/PLACER` and ships the model weights
(`weights/PLACER_model_1.pt`) inside the checkout.

> **Hard limitation, read first:** PLACER cannot take an apo protein + a
> separate SMILES/SDF and dock the ligand from scratch. The docked ligand must
> already be present, with coordinates, in the input PDB/mmCIF. The SDF/MOL2
> `--ligand_file` input only *refines atom typing/bonding* — coordinates are
> still read from the PDB/mmCIF. See `references/inputs.md`.

## When to use PLACER vs. alternatives

| You want… | Use |
|-----------|-----|
| **Refine/score a ligand pose** already placed in a pocket; sidechain repacking | **PLACER** |
| Generate a ligand pose from scratch (apo + SMILES) | A docking tool (Vina/GNINA/SigmaDock) or a co-folding model — **not** PLACER |
| Full protein-ligand **complex** structure from sequence + ligand | `boltz`, `chai-lab` |
| **Design** an enzyme / binder active site (then validate with PLACER) | `invrotzyme` → `foundry` (RFdiffusionAA), `disco`, `boltzgen` |
| Sidechain repacking inside a managed **pipeline** (SLURM) | `protflow` (wraps `run_PLACER.py`) |

A common loop: design active sites (`invrotzyme`/`disco`/RFdiffusionAA) →
assign sequence (`foundry` LigandMPNN) → **PLACER** to check the ligand
re-resolves at low `prmsd` with high `plddt` → keep the survivors.

## Quickstart — run from an Apptainer SIF

PLACER's environment is heavy (CUDA 12.1, torch 2.3.1, dgl 2.4.0, openbabel,
e3nn, the NVIDIA SE3Transformer from git). Packaging it once into a SIF makes it
portable and reproducible across machines/clusters. The skill ships a definition
file at `examples/PLACER.def`.

### 1) Build the SIF (one-time)

```bash
# Needs apptainer (or singularity) with --fakeroot, plus network for the build.
apptainer build placer.sif \
  ~/.claude/skills/placer/examples/PLACER.def
```

The build clones PLACER into `/opt/PLACER` (weights included) and creates the
`placer_env_lite` conda environment inside the image. See
`references/installation.md` for `--fakeroot` vs. `sudo`, building on a cluster,
the CUDA-driver requirement, and bind-mounting a host checkout instead of
cloning.

### 2) Run a prediction (GPU)

```bash
apptainer exec --nv placer.sif \
  python /opt/PLACER/run_PLACER.py \
    --ifile 4dtz.cif \
    --odir out \
    -n 50 \
    --rerank prmsd \
    --predict_ligand D-LDP-501 \
    --suffix LDP \
    --weights /opt/PLACER/weights/PLACER_model_1.pt
```

- `--nv` exposes the host GPU (required for sane speed: ~1-3 s/model on GPU vs.
  ~7 min/model on 1 CPU core).
- Apptainer mounts `$PWD` and `$HOME` by default, so `--ifile 4dtz.cif` and
  `--odir out` resolve to the host working directory. Use `--bind /data:/data`
  for paths outside those. See `references/installation.md`.
- **The `--weights` gotcha:** `run_PLACER.py`'s default `weights/PLACER_model_1.pt`
  is resolved relative to the *current working directory*, not the script. From
  an arbitrary host cwd it won't be found — always pass the absolute in-container
  path `--weights /opt/PLACER/weights/PLACER_model_1.pt` (exported in the image
  as `$PLACER_WEIGHTS`), or add `--pwd /opt/PLACER`.

### 3) Read the output

Two files per input, prefixed by `<odir>/<input_stem>[ _<suffix>]`:
- `*_model.pdb` — a **multimodel** PDB, one MODEL per sample, reranked best→worst
  by `--rerank`. Per-atom `prmsd` is in the b-factor column.
- `*.csv` — one row per sample with the confidence scores.

Pick the top ~10% by `prmsd` for docking analysis. Full layout +
score definitions in `references/outputs.md`.

## CLI at a glance

`run_PLACER.py` is the entry point. The flags you will use most:

| Flag | Purpose |
|------|---------|
| `-f/--ifile` | Single PDB/mmCIF, or a text file listing many (mmCIF must be RCSB-formatted) |
| `-i/--idir` | Folder of `*.pdb` to batch |
| `-o/--odir` | Output folder (default `./`) |
| `-n/--nsamples` | Ensemble size — **50** for sidechains, **50-100+** for docking |
| `--rerank {prmsd,plddt,plddt_pde}` | Sort output models + CSV best→worst |
| `--predict_ligand <chain-name3-resno> …` | Ligand(s) to predict; all others auto-fixed |
| `--predict_multi` | Predict/score *all* allowed ligands (respects fixed/predict) |
| `--fixed_ligand <…>` | Keep these ligand(s) fixed (e.g. heme) |
| `--ligand_file XXX:lig.sdf` | Refine atom typing/bonding from SDF/MOL2 (or `XXX:CCD`) |
| `--target_res <chain-resno>` | Crop center — **required when input has no ligand** (apo sidechains) |
| `--mutate 128A:75I …` | Mutate positions before predicting |
| `--residue_json file.json` | Register non-canonical residues into the CCD library |
| `--use_sm` / `--no-use_sm` | Predict with (holo, default) / without (apo) the small molecule |
| `--suffix` | Appended to output filenames |
| `--cautious` | Skip inputs whose output CSV already exists |
| `--weights` | `.pt` checkpoint (pass the absolute in-container path) |

Ligand / residue selectors use `<name3>`, `<name3-resno>`, or
`<chain-name3-resno>` (e.g. `HEM`, `LDP-501`, `D-LDP-501`). Full flag reference
with semantics: `references/cli.md`. Input conventions and the residue-JSON
schema: `references/inputs.md`.

## Confidence scores — which to trust

PLACER emits several scores per model (CSV columns); for **docking**, rank by
`prmsd` (predicted RMS of atomic-position deviations of the ligand — a true
*confidence*, not a comparison to ground truth):

- `prmsd < 2.0` → trustworthy. `< 4.0` can be acceptable if it's the best you
  get *and* `plddt`/`plddt_pde` are good (`> 0.8`).
- `plddt` / `plddt_pde` — predicted lDDT over ligand atoms (1D / 2D track).
- `fape`, `lddt`, `rmsd`, `kabsch` — these compare to the **input** structure
  (ground-truth-relative), useful when the input pose is known/trusted.

Definitions and ranking guidance: `references/outputs.md`.

## Python API (inside the SIF)

```python
import sys; sys.path.append("/opt/PLACER")
import PLACER

placer = PLACER.PLACER()                       # loads default checkpoint
inp = PLACER.PLACERinput()
inp.cif("4dtz.cif")                            # or .pdb(path/string)
inp.name("p450_dopamine")
inp.predict_ligand([("D", "LDP", 501)])        # fixes all other ligands
inp.ligand_reference({"HEM": "CCD", "LDP": "CCD"})
outputs = placer.run(inp, 50)                  # dict of N models
PLACER.protocol.dump_output(outputs, "out/p450_dopamine", rerank="prmsd")
```

Run it as `apptainer exec --nv placer.sif python my_script.py`. Every
`PLACERinput` setter (`fixed_ligand`, `bonds`, `mutate`, `add_custom_residues`,
`corruption_centers`, `crop_centers`, …) is documented in
`references/python-api.md`.

## Gotchas (read before you debug)

1. **Ligand must be in the input with coordinates.** No SMILES→pose. No
   apo+SDF docking. `--ligand_file` only fixes atom typing/bonding.
2. **`--weights` is cwd-relative.** Pass `/opt/PLACER/weights/PLACER_model_1.pt`.
3. **Ligand and protein must not share a chain letter** for PDB inputs — this
   raises an AssertionError. RCSB mmCIF parses cleanly because it handles ligand
   chains differently (see the API example with `3rgk.pdb` vs `3rgk.cif`).
4. **Apo runs need a crop center.** With no ligand, pass `--target_res` (and
   usually `--no-use_sm`).
5. **Non-planar aromatic rings** → supply `--ligand_file LIG:lig.sdf` so bonds/
   hybridization are read correctly.
6. **Crop > ~600 atoms is out of distribution** — confidence degrades.
7. **Hydrogens are not predicted**; use `--ignore_ligand_hydrogens` if your
   PDB/SDF protonation states disagree.
8. **Outputs of other predictors** (AF/Boltz/Chai mmCIF) often parse poorly
   (missing H, formatting) — prefer RCSB mmCIF or Rosetta PDB.
9. **`--nv` is required** for GPU; without it PLACER silently runs on CPU
   (minutes per model).
10. **mmCIF must be RCSB-formatted** for the CIF parser; arbitrary mmCIF may
    fail. PDB is the safer general input.

More failure modes and fixes: `references/troubleshooting.md`.

## Reference index

- `references/installation.md` — building/using the SIF (`PLACER.def`, fakeroot,
  cluster builds, GPU/driver, binds, bind-a-checkout, conda fallback).
- `references/cli.md` — every `run_PLACER.py` flag with semantics + examples.
- `references/inputs.md` — input formats, ligand/residue selector syntax,
  `--ligand_file`, residue-JSON schema for non-canonicals.
- `references/python-api.md` — `PLACER` / `PLACERinput` / `protocol.dump_output`.
- `references/outputs.md` — file layout + every score and how to rank.
- `references/troubleshooting.md` — build and runtime errors.
- `examples/PLACER.def` — the Apptainer/Singularity definition file.
- `examples/commandline_examples.sh` — copy-paste container invocations.

## Installing this skill

```bash
# Symlink (recommended — picks up edits live)
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/placer
# Or copy:
cp -R . ~/.claude/skills/placer
```

After that, an agent invokes it via `Skill(skill="placer")`.

## Citation

PLACER (formerly ChemNet), Baker Lab / Institute for Protein Design.
BSD 3-Clause (code + weights), © 2025 University of Washington.

```
Anishchenko, Kalvet, Krishna et al.
Modeling protein-small molecule conformational ensembles with PLACER.
bioRxiv 2024.09.25.614868.
https://www.biorxiv.org/content/10.1101/2024.09.25.614868v1
```
