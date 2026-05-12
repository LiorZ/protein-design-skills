---
name: invrotzyme
description: >
  Build inverse-rotamer active-site assemblies from a Rosetta matcher/enzdes
  constraint (CST) file using PyRosetta. Use this skill when:
  (1) Constructing theozyme / active-site stubs (catalytic sidechains placed
      around a ligand) as starting points for de novo enzyme design,
  (2) Preparing inputs for **RFdiffusion All-Atom** (RFdiffusionAA) enzyme
      design pipelines — outputs include `REMARK 666` enzdes records so
      they drop straight into the published heme-binder-diffusion workflow,
  (3) Exhaustively enumerating clash-free combinations of catalytic
      rotamers + small idealized helix/strand backbone stubs around a
      small-molecule substrate / cofactor,
  (4) Hosting one catalytic residue inside an externally-provided **motif
      PDB** (e.g. a CYS loop from a cytochrome P450) while still
      enumerating the other CST residues as inverse rotamers,
  (5) Filtering rotamers by Dunbrack cumulative probability (per-CST or
      global), per-CST secondary structure, and per-CST random subsampling
      to control combinatorial explosion,
  (6) Enabling Rosetta-style extra-χ sub-sampling (`-ex1`..`-ex4`-equivalent)
      per CST block to widen rotamer search at controlled cost,
  (7) Pinning a specific HIS tautomer (`HIS` vs `HIS_D`) per CST,
  (8) `--tip_atom` mode: skipping pairwise clash analysis and outputting
      assemblies based purely on unique geometric placement of catalytic
      tip atoms (much faster, looser).

  Covers the CST-file requirements, every CLI flag, the per-CST argument
  convention, the `--motif_for_cst` format, parallelization model
  (Python multiprocessing, SLURM-aware), output PDB structure (one
  `REMARK 666` line per catalytic residue), and the typical role of
  this tool inside a larger enzyme-design pipeline.

  Pairs with: `rfdiffusion` (specifically RFdiffusionAA — invrotzyme
  outputs are designed to be its inputs), `ligandmpnn` (sequence design
  on the resulting backbones), `chai` / `boltz` / `alphafold` (refold
  validation), `protein-qc` (QC thresholds), `bindcraft` (alternative
  end-to-end binder route — not enzyme-design).
license: MIT
category: protein-design
tags: [enzyme-design, theozyme, inverse-rotamer, rosetta, enzdes, matcher, rfdiffusion-aa, active-site, pyrosetta]
repo: https://github.com/ikalvet/invrotzyme
related_pipeline: https://github.com/ikalvet/heme_binder_diffusion
---

# InvrotZyme — Inverse-Rotamer Assemblies from Rosetta CST Files

## What this is

InvrotZyme is a **single-script** PyRosetta tool that takes a
Rosetta matcher / enzdes constraint file (CST) and emits PDB files
containing all clash-free combinations of catalytic side-chain rotamers
placed around a ligand, each rotamer optionally embedded in a short
idealized α-helix or β-strand backbone stub.

Each output PDB contains:

- The catalytic ligand as `chain X`, residue `0` (when only one ligand).
- One short backbone stub per catalytic residue, each on its own chain.
- A `REMARK 666 MATCH TEMPLATE … MATCH MOTIF …` header line per
  catalytic residue — the **enzdes constraint header** that downstream
  Rosetta / RFdiffusionAA pipelines need to re-instate the constraint.

These PDBs are designed to be fed straight into the published
[heme_binder_diffusion](https://github.com/ikalvet/heme_binder_diffusion)
RFdiffusion-All-Atom enzyme-design pipeline, but they're also usable
as `match` outputs or Rosetta enzdes inputs.

The codebase is small (3 files: `invrotzyme.py`, `protocol.py`,
`utils.py`, plus a `utils/` subpackage with the Dunbrack-rotlib loader
and a Kabsch aligner) and depends only on **pyrosetta**, **numpy**,
**pandas**, **scipy**.

## When to use this vs alternatives

| You want… | Use |
|----------|-----|
| Clash-free **theozyme** / inverse-rotamer assemblies from a CST + params | **invrotzyme** |
| End-to-end binder against a *protein* target (no ligand) | `bindcraft`, `rfdiffusion`, `genie3` |
| Backbone generation around invrotzyme outputs (RFdiffusion **All-Atom**) | `rfdiffusion` (AA variant) — invrotzyme is its standard input |
| Sequence design on backbones that host a ligand | `ligandmpnn` |
| Joint sequence + structure co-design around a ligand (no CST file) | `disco`, `boltzgen` |
| Refold / validate the resulting enzyme designs | `chai`, `boltz`, `alphafold` |
| QC filtering of designed enzymes | `protein-qc` |

The headline use case is **stage 1** of an enzyme-design pipeline:
generate many small (~10 res) catalytic assemblies → RFdiffusionAA
scaffolds → LigandMPNN sequences → AF/Chai/Boltz refold → QC.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **PyRosetta** | Must be installed and licensed. Provides the Dunbrack rotamer DB (`bbdep02.May.sortlib-correct.12.2010` is loaded from `<pyrosetta>/database/rotamer/`). |
| numpy, pandas, scipy | Standard scientific stack. |
| Rosetta `.params` for ligand | One `.params` file per non-canonical residue or small-molecule ligand referenced in the CST. |
| **CST file** | All six DOFs (distance, two angles, three torsions) defined per constraint block. See *CST file requirements* below. |
| CPU cores | The script is multiprocess and CPU-only (no GPU). Reads `SLURM_CPUS_ON_NODE` when running under SLURM, else defaults to `os.cpu_count()`. |

There is no GPU dependency and no model weights to download.

## Three-step quickstart

### 1) Clone (one-time)

```bash
git clone https://github.com/ikalvet/invrotzyme.git ~/Repos/invrotzyme
```

The script imports `protocol`, `utils`, `dunbrack_rotlib`, and
`align_pdbs` from its own directory — **run it from anywhere as long
as `invrotzyme.py` is invoked by its full or relative path** (it adds
its own directory and `utils/` to `sys.path`).

### 2) Prepare inputs

You need:

- A **`.cst` file** with one `CST::BEGIN … CST::END` block per catalytic
  interaction, each defining all six DOFs. Group alternative residues
  (e.g. SER/THR/TYR/ASN/GLN at the oxyanion hole) under
  `VARIABLE_CST::BEGIN … VARIABLE_CST::END`. See
  [references/cst-file.md](references/cst-file.md).
- A **`.params` file** for every non-canonical residue / ligand
  (e.g. `BIO.params` for benzisoxazole in the Kemp example).
- *(Optional)* a **motif PDB** if you want a specific catalytic
  residue to come from a pre-existing scaffold (e.g. P450 CYS loop)
  instead of an enumerated rotamer.

### 3) Run

Kemp eliminase (HIS-ED dyad + oxyanion hole, ~10s on 32 cores):

```bash
cd examples/Kemp_eliminase
python ../../invrotzyme.py \
  --cstfile inputs/BIO_His_ED_oxy_nosample.cst \
  --params  inputs/BIO.params \
  --dunbrack_prob 0.6 \
  --frac_random_rotamers_per_cst 0.5 0.5 0.5 0.5 \
  --secstruct_per_cst H H E \
  --prefix outputs/ \
  --suffix HHE
```

P450 with external motif holding the CYS:

```bash
cd examples/P450
python ../../invrotzyme.py \
  --cstfile inputs/HBA_CYS_P450_nosample.cst \
  --params  inputs/HBA_unique.params \
  --motif_for_cst 1:3:inputs/P450_motif.pdb \
  --frac_random_rotamers 0.1 \
  --prefix outputs/
```

Inspect any output PDB — it should start with one
`REMARK 666 MATCH TEMPLATE … MATCH MOTIF …` line per catalytic CST.

See [examples/](examples/) for full annotated invocations.

## CLI flags — full reference

The script is one positional-free `argparse` interface. All flags are
optional except `--cstfile`. Per-CST flags accept one value per CST
block (in CST order); the ligand-bearing CST 1 is **typically** included
in the per-CST list with a placeholder value (see *Per-CST argument
convention* below).

### Required

| Flag | Description |
|------|-------------|
| `--cstfile PATH` | Rosetta matcher/enzdes CST file. **All six DOFs must be defined per block.** |

### Inputs

| Flag | Description |
|------|-------------|
| `--params PATH [PATH ...]` | One or more `.params` files for non-canonical residues / ligands. Passed to PyRosetta as `-extra_res_fa`. |
| `--motif_for_cst CSTNO:RESNO_IN_MOTIF:FILEPATH [...]` | Use a residue from an external PDB instead of enumerating rotamers for that CST. **Currently only `CSTNO=1` is supported.** |

### Rotamer filtering

| Flag | Default | Description |
|------|---------|-------------|
| `--dunbrack_prob FLOAT` | `0.85` | Cumulative Dunbrack probability cutoff (same semantics as Rosetta `-packing:dunbrack_prob_…`). Lower = stricter (fewer rotamers). |
| `--dunbrack_prob_per_cst F [F ...]` | — | Per-CST override. One value per CST block (excluding the ligand). |
| `--keep_his_tautomer 'CST:HIS,CST:HIS_D,...'` | — | Pin a HIS tautomer per CST. Allowed values: `HIS`, `HIS_D`. |
| `--use_best_rotamer_cstids N [N ...]` | `[]` | For these CST IDs, only the single best rotamer per secondary-structure bin is kept (numbering starts at **1**). |

### Random subsampling (control combinatorial explosion)

These are the workhorses for keeping the run tractable on a CPU.

| Flag | Description |
|------|-------------|
| `--max_random_rotamers N` | Cap each residue's rotamer count to N (recommended < 20 for quick sampling). |
| `--max_random_rotamers_per_cst N0 N1 N2 ...` | Per-CST cap. **First value is for the ligand.** |
| `--frac_random_rotamers FLOAT` | Random fraction (0–1) of rotamers kept per residue. |
| `--frac_random_rotamers_per_cst F0 F1 F2 ...` | Per-CST fraction. **First value is for the ligand.** |
| `--prune_ligand_rotamers FLOAT` | RMSD cutoff (Å) for ligand-rotamer dedup. `0.0` disables. |

### Backbone stub generation

| Flag | Default | Description |
|------|---------|-------------|
| `--secstruct H\|E` | `H` | Idealized secondary structure of the stub built around each rotamer. |
| `--secstruct_per_cst S [S ...]` | — | Per-CST override (`E`, `H`, or `-`). |
| `--N_len N` | `4` | Number of residues added N-terminal of each catalytic residue. |
| `--C_len N` | `5` | Number of residues added C-terminal of each catalytic residue. |
| `--N_len_per_cst N [N ...]` | — | Per-CST override. |
| `--C_len_per_cst N [N ...]` | — | Per-CST override. |

### Extra χ sub-sampling

| Flag | Description |
|------|-------------|
| `--extra_chi 'chi:level,chi2:level2'` | Enable Rosetta-style χ sub-sampling for all CSTs. Format: `CHI:LEVEL` pairs comma-joined. |
| `--extra_chi_per_cst 'CSTNO-chi:level' [...]` | Per-CST extra-χ sub-sampling. |

Sampling levels (per the script's `calculate_samplings` docstring):

| Level | Samples |
|-------|---------|
| 0 | original only — equivalent to disabling |
| 1 | ± 1 σ — 3 samples |
| 2 | ± 0.5 σ — 3 samples |
| 3 | ± 1 σ, 2 σ — 5 samples |
| 4 | ± 0.5 σ, 1 σ — 5 samples |
| 5 | ± 0.5, 1, 1.5, 2 σ — 9 samples |
| 6 | ± 0.33, 0.67, 1 σ — 7 samples |
| 7 | ± 0.25, 0.5, 0.75, 1, 1.25, 1.5 σ — 13 samples |

### Output / runtime

| Flag | Default | Description |
|------|---------|-------------|
| `--prefix STR` | `""` | Prefix prepended to every output PDB filename (a path prefix works, e.g. `outputs/`). |
| `--suffix STR` | `""` | Suffix appended to every output PDB filename (before `.pdb`). |
| `--tip_atom` | off | Skip the full pairwise clash analysis; pre-select rotamers purely by *unique placement of catalytic tip atoms*. Much faster, much looser. |
| `--nproc N` | `os.cpu_count()` | CPU cores. Auto-overridden by `SLURM_CPUS_ON_NODE` if set. Forced to `1` under `--debug`. |
| `--max_outputs N` | — | Early-stop after N successful assemblies have been written. |
| `--debug` | off | Single-threaded, verbose. |

## Per-CST argument convention

Per-CST flags follow one of two conventions depending on the flag:

- **Rotamer-count flags** (`*_random_rotamers_per_cst`) take **one value per CST block plus one for the ligand**, ligand-first.
  *Example:* `--frac_random_rotamers_per_cst 0.5 0.5 0.5 0.5` for 3 CST blocks means
  `[0.5(ligand), 0.5(CST1), 0.5(CST2), 0.5(CST3)]`.
- **Geometry flags** (`secstruct_per_cst`, `N_len_per_cst`, `C_len_per_cst`, `dunbrack_prob_per_cst`)
  take **one value per CST block, ligand-excluded**.
  *Example:* `--secstruct_per_cst H H E` for 3 CST blocks.

Mixing these up will assert at startup — read the error message
carefully, it tells you the expected length.

## Output layout

Per successful rotamer combination, one PDB file is written:

```
<prefix><rotamer-letters>_<set>_<i><suffix>.pdb
```

Filename components are appended residue-by-residue:

- canonical AAs as their one-letter code (`H`, `E`, `S`, `Y`, …)
- ligands / non-canonicals as their three-letter `name3()`
- motif residues use the basename of the motif PDB (without `.pdb`)

`<set>` is the non-redundant rotamer-set index (1-based) and `<i>` is
the index within that set's `itertools.product` enumeration.

Inside each PDB:

- One `REMARK 666 MATCH TEMPLATE X <LIG> 0 MATCH MOTIF <chain> <RES> <resno> <cst#> <mcfi#>`
  line per catalytic residue (except the ligand itself).
- Each catalytic residue on its own chain (the result of building the
  idealized stub independently per residue and concatenating with
  `append_subpose_to_pose(new_chain=True)`).
- The ligand as the **last** chain (or `chain X residue 0` semantics in
  the REMARK when only one ligand is present).

A console line is emitted per successful build:

```
Found good rotamer: <prefix>H_E_S_<...>_<set>_<i><suffix>
```

For invalid rotamers, the rotamer ID is added to a per-CST
`bad_rotamers` list and skipped on subsequent combinations — this
cheap memoization is what keeps long enumerations tractable.

## CST file requirements

The CST file is the **standard Rosetta matcher / enzdes constraint
format**. Full reference:
<https://docs.rosettacommons.org/docs/latest/rosetta_basics/file_types/match-cstfile-format>.

InvrotZyme-specific requirements:

1. **All six DOFs must be defined** for every constraint block:
   `distanceAB`, `angle_A`, `angle_B`, `torsion_A`, `torsion_AB`,
   `torsion_B`. PyRosetta's `TheozymeInvrotTree.generate_targets_and_inverse_rotamers()`
   requires this to enumerate inverse rotamers.
2. **Keep in-CST conformational sampling minimal** — every additional
   sample multiplies the combinatorial space. Prefer to widen with
   `--extra_chi*` (deterministic, controllable) over CST-level samples.
3. **Variable CSTs** (`VARIABLE_CST::BEGIN … VARIABLE_CST::END`) work
   as expected — multiple alternative residue types share the same
   slot in the assembly.
4. **`SECONDARY_MATCH`** algorithm directives are respected. The
   `create_remark_lines` function walks `UPSTREAM_CST N` / `DOWNSTREAM`
   to pick the correct downstream residue when emitting `REMARK 666`.

See [references/cst-file.md](references/cst-file.md) for an annotated
walkthrough of the Kemp-eliminase CST.

## How the pipeline runs (mental model)

```
CST file ──► EnzConstraintIO ──► MCFI per block ──► restypes per block
                                                                │
            Dunbrack DB ─┐                                       ▼
                          ├──► find_good_rotamers(prob, secstruct)
                          │                                      │
                          ▼                                      ▼
             per-CST rotamer pool ◄── prune (proton-chi, ligand RMSD,
                                              extra-χ subsample)
                                                                │
                          itertools.product over per-CST pools ─┘
                                                                │
                          multiprocessing.Pool workers ─────────┤
                                                                ▼
                          per combination:
                            1) extend each rotamer into an SS stub
                            2) attach ligand and clash-check
                            3) assemble full pose; clash-check ignoring
                               (catalytic ↔ ligand) pairs
                            4) emit REMARK 666 lines per catalytic res
                            5) write PDB if all REMARKs computable
```

Workers share a `bad_rotamers` `manager.dict()` so each per-residue
clash-failure invalidates that rotamer for **all** future combinations.

## Hard rules / gotchas

1. **CST blocks must define all six DOFs.** The script will not run
   otherwise.
2. **Per-CST `*_random_rotamers_per_cst` lists are ligand-first** —
   the first entry is for the ligand pool, then one entry per CST.
   Geometry lists (`secstruct_per_cst`, `N_len_per_cst`, …) are
   ligand-excluded. Read the assertion errors carefully.
3. **`--motif_for_cst` only supports `CSTNO=1` right now.** The
   `parse_motif_input` function explicitly `sys.exit`s for any other
   CST. Format: `cst_no:resno_in_motif:filepath` (colons, no spaces).
4. **Combinatorial explosion is the #1 failure mode.** With 4 CSTs and
   100 rotamers each you have 10⁸ combinations. Use
   `--dunbrack_prob ≤ 0.6`, `--frac_random_rotamers_per_cst`, or
   `--use_best_rotamer_cstids` aggressively. The Kemp example uses
   `0.6` Dunbrack + `0.5` random fraction per CST.
5. **`--tip_atom` skips pairwise clash analysis.** Output volume goes
   up, but most assemblies will clash in any downstream step.
6. **Outputs include `REMARK 666` lines** — they are required by
   Rosetta enzdes downstream. If `create_remark_lines` cannot
   reconstruct all lines for an assembly, the PDB is **not** written.
7. **Files are overwritten silently** if the same `prefix`/`suffix`/
   indices match (the script tries an `a.pdb` suffix on collision, but
   the rename is buggy — `str.replace` returns a new string that is
   discarded; if duplicate names matter, vary `--suffix`).
8. **Bad rotamers are cached per-run**. A rotamer that fails the
   stub-extension clash check on its first appearance is blacklisted
   for the rest of the run. Re-running the script does **not** persist
   this cache.
9. **SLURM-aware nproc**: the script *unconditionally* overrides
   `--nproc` with `SLURM_CPUS_ON_NODE` if that env var is set. To
   pin a smaller value under SLURM, unset the env var first.
10. **PyRosetta init flags**: the script calls
    `pyrosetta.init("<-extra_res_fa> -run:preserve_header")` — if you
    need additional flags, edit `invrotzyme.py:269` (no CLI passthrough).
11. **External motif residue must be the right type.** The motif's
    `pose.residue(motif_resno).name3()` must appear in the CST's
    allowed restypes for that block, or the script asserts.
12. **Single-ligand REMARK shortcut.** When there is exactly one ligand,
    the `REMARK 666` line uses `chain X residue 0` for the ligand;
    multi-ligand cases use the in-pose chain/seqpos. Downstream parsers
    must handle both forms.

## Where outputs are used downstream

The intended downstream consumer is **RFdiffusion All-Atom**
(via the published [`heme_binder_diffusion`](https://github.com/ikalvet/heme_binder_diffusion)
pipeline). That pipeline:

1. Takes an invrotzyme PDB.
2. Diffuses a protein backbone that hosts all catalytic residues.
3. Sequence-designs the backbone (often **LigandMPNN** — see the
   `ligandmpnn` skill).
4. Refolds with AF2 / Chai / Boltz and filters by interface metrics
   and ligand-pocket geometry.

If you want to skip RFdiffusionAA and go straight to **Rosetta enzdes**
matching, the same `REMARK 666` PDBs are valid `match` outputs and can
be fed to `enzdes` design directly.

## Choosing the right reference doc

| You want to… | Read |
|--------------|------|
| Understand the CST file syntax + the Kemp example | [references/cst-file.md](references/cst-file.md) |
| See every CLI flag with worked examples | [references/cli.md](references/cli.md) |
| Tame combinatorial explosion (rotamer-filtering recipe) | [references/sampling.md](references/sampling.md) |
| Use a motif PDB instead of an enumerated rotamer | [references/motif.md](references/motif.md) |
| Parse / consume the output PDBs downstream | [references/outputs.md](references/outputs.md) |
| Plug invrotzyme into an RFdiffusionAA pipeline | [references/pipeline.md](references/pipeline.md) |
| See annotated example invocations | [examples/](examples/) |

## Quick decision tree

- **You have a CST file, just want clash-free assemblies fast** →
  `--dunbrack_prob 0.6 --frac_random_rotamers_per_cst <one_value_per_cst_+_ligand>`.
  Single-digit-minute on 32 cores.
- **You want exhaustive enumeration** → omit `--frac_random_rotamers*`
  and `--max_random_rotamers*`; raise `--dunbrack_prob` to `0.95`.
  Expect long runs.
- **You only care about geometric diversity of catalytic tips** →
  add `--tip_atom`. Skips most clash checks; produces *many* PDBs.
- **One catalytic residue lives on a fixed motif (e.g. P450 CYS)** →
  `--motif_for_cst 1:<resno>:motif.pdb`. Only CST 1 supported.
- **You hit combinatorial explosion** → bring `--dunbrack_prob` down
  to `0.5–0.6`, add `--use_best_rotamer_cstids 1 2 3` for the
  least-flexible residues, and `--max_outputs N` to early-stop.

## Installing this skill

```bash
# Symlink (recommended — picks up edits live)
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/invrotzyme

# Or copy:
cp -R . ~/.claude/skills/invrotzyme
```

After that, an agent invokes it via `Skill(skill="invrotzyme")`.

## Citation

InvrotZyme has no standalone publication. Cite the downstream
RFdiffusion-All-Atom enzyme-design paper when used in that pipeline,
and attribute the script to **I. Kalvet (Baker lab, UW)**.
