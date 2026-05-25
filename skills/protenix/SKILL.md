---
name: protenix
description: >
  Run Protenix — ByteDance's open-source, trainable reproduction of AlphaFold 3
  for high-accuracy biomolecular structure prediction. Protenix folds complexes
  of proteins, DNA, RNA, small-molecule ligands, and ions in one pass, with
  post-translational/nucleotide modifications, covalent bonds, MSAs, templates,
  and optional pocket/contact constraints. Use this skill when:
  (1) Predicting the 3D structure of a **protein / nucleic-acid / ligand
      complex** from sequences + ligand specs (the headline use case),
  (2) Folding a **single protein** (monomer or homo-/hetero-oligomer via
      `count` / `id`) with an MMseqs2 MSA searched automatically,
  (3) Modeling **protein–ligand** binding where the ligand is a CCD code, a
      SMILES string, or a 3D structure file (SDF/MOL/MOL2/PDB),
  (4) Predicting **protein–DNA / protein–RNA** complexes, optionally with RNA
      MSA, modified bases, and double-stranded DNA (two complementary strands),
  (5) Adding **covalent bonds** (e.g. glycosylation, covalent inhibitors,
      cyclic peptides) or **PTMs / modified residues** by CCD code,
  (6) Steering predictions with **soft pocket / contact constraints** (the
      `constraint` model) to bias an interface toward known epitopes/pockets,
  (7) Trading accuracy for speed via the **mini / tiny** model variants for
      high-throughput screening, or maximizing accuracy with `protenix-v2`,
  (8) Generating inputs: converting a **PDB/CIF → input JSON** (`protenix json`)
      or running **MSA / template / RNA-MSA search** as a standalone preprocess
      step (`protenix msa` / `mt` / `prep`),
  (9) Ranking and reading **confidence** (ranking_score / pLDDT / pTM / ipTM,
      per-chain and per-chain-pair) to pick the best of N samples × M seeds.

  This skill is written for running Protenix from an **Apptainer / Singularity
  SIF container** (the runtime is heavy: torch 2.7 + CUDA 12.6 + DeepSpeed +
  cuEquivariance + JIT-compiled layer-norm / Evoformer-attention CUDA kernels).
  The Protenix repo at `~/Repos/Protenix` ships a ready-made `apptainer/`
  directory (`protenix.def`, `build.sh`, `download_weights.sh`,
  `run_protenix.sh`). The skill covers building the SIF, the host-side
  bind-mounted weights layout (`$PROTENIX_ROOT_DIR/checkpoint` + `/common`), the
  `apptainer run --nv` invocation pattern, every `protenix` subcommand and `pred`
  flag, the AlphaFold-Server-style input JSON (entities, modifications, covalent
  bonds, MSA/template paths, pocket/contact constraints), the model zoo and which
  to pick, the output layout (`<name>/<seed>/<name>_<seed>_sample_*.cif` + summary
  confidence JSON), and how to rank by confidence.

  Limitations: Apache-2.0; needs a CUDA GPU (data-cutoff 2021-09-30 for most
  checkpoints); `protenix-v2.pt` is not currently served publicly; ESM/ISM
  checkpoints need the ~5 GB ESM2-3B weights and are not downloaded by default;
  pocket/contact constraints require the `constraint` checkpoint; templates &
  RNA-MSA are supported only by the v1.0.0 / 20250630 / v2 models.

  Pairs with: `boltz` / `chai-lab` (alternative AF3-class co-folding models —
  cross-check predictions or pick the tool that handles your modality best),
  `boltzgen` / `disco` / `foundry` (design binders/enzymes, then validate the
  complex with Protenix), `placer` (atomistic ligand-pose / side-chain
  refinement and pose scoring on a Protenix pocket), `protflow` (wrap Protenix as
  a pipeline step at cluster scale), `fair-esm` (ESMFold / embeddings).
license: Apache-2.0
category: protein-design
tags: [protein-design, structure-prediction, alphafold3, complex-prediction, protein-ligand, protein-nucleic-acid, msa, diffusion, constraints, apptainer, singularity, bytedance]
repo: https://github.com/bytedance/Protenix
biorxiv: https://www.biorxiv.org/content/10.1101/2025.01.08.631967
---

# Protenix — open-source AlphaFold 3 (Protein + X)

## What this is

Protenix is ByteDance's open-source, **trainable** reproduction of AlphaFold 3:
a Pairformer + diffusion model that predicts the all-atom 3D structure of a
biomolecular complex from its components. One job can mix **proteins, DNA, RNA,
small-molecule ligands, and ions**, with post-translational/nucleotide
modifications, inter-entity covalent bonds, MSAs, structural templates, and
optional soft pocket/contact constraints. It outputs CIF structures plus
AlphaFold3-style confidence scores. Released under **Apache-2.0** (code +
weights), free for commercial use.

The repo at `~/Repos/Protenix` is **v2.0.0** and exposes a `protenix` CLI
(installed as a console script). It ships a ready-made **Apptainer** setup under
`apptainer/`, which is the path this skill is built around.

> **Read first — three things that trip people up:**
> 1. **Weights live on the host, not in the image.** They are bind-mounted at
>    launch and resolved from `$PROTENIX_ROOT_DIR` (`checkpoint/` + `common/`).
>    Download them once with `apptainer/download_weights.sh`.
> 2. **Use `--use_default_params true`.** It sets the right `cycle`/`step` for the
>    chosen model (base = 10/200, mini/tiny = 4/5). Without it you get generic
>    defaults that may not match the checkpoint.
> 3. **The first run JIT-compiles CUDA kernels** (layer-norm, Evoformer
>    attention) into `$TORCH_EXTENSIONS_DIR` — slow once, cached after.

## When to use Protenix vs. alternatives

| You want… | Use |
|-----------|-----|
| **Full complex** structure (protein + DNA/RNA + ligand + ions) from sequence | **Protenix** |
| Cross-check an AF3-class prediction with a second model | **Protenix** + `boltz` / `chai-lab` |
| Best antibody–antigen / ligand accuracy (if you have the weights) | **Protenix** `protenix-v2` |
| High-throughput screening (many targets, lower cost) | **Protenix** `mini` / `tiny` |
| **Design** a binder / enzyme, then validate the complex | `boltzgen`/`disco`/`foundry` → **Protenix** |
| Refine/score a **ligand pose & side chains** in one pocket | `placer` (atomistic; runs on a Protenix output) |
| Binding **affinity** prediction | `boltz` (Boltz-2) — Protenix predicts structure + confidence, not ΔG |

A common loop: fold the complex with **Protenix** → inspect `ranking_score` /
ipTM → hand the top sample's pocket to `placer` for atomistic ligand/side-chain
refinement, or cross-check the fold with `chai-lab` / `boltz`.

## Quickstart — run from the Apptainer SIF

The heavy runtime (torch 2.7, CUDA 12.6, DeepSpeed, cuEquivariance, JIT CUDA
kernels) is packaged once into a SIF. The Protenix repo already contains the
definition and helper scripts under `apptainer/`.

### 1) Build the SIF (one-time, from the repo root)

```bash
cd ~/Repos/Protenix
bash apptainer/build.sh            # -> apptainer/protenix.sif  (uses --fakeroot)
```

`build.sh` stages a clean copy of the repo (minus `.git`/caches/outputs) and
bakes it into the image; the source lives at `/opt/protenix` inside. See
`references/installation.md` for fakeroot vs. cluster builds, cache dirs, and the
CUTLASS/kernel details.

### 2) Download model weights to the host (one-time)

```bash
PROTENIX_ROOT_DIR=/shared/ModelWeights/Protenix bash apptainer/download_weights.sh
```

This fetches the non-ESM checkpoints (~7.5 GB) into `$PROTENIX_ROOT_DIR/checkpoint`
and the CCD / cluster / release-date caches into `$PROTENIX_ROOT_DIR/common`.
Weights are **not** baked into the SIF — they are bind-mounted at run time. See
`references/models.md` for the model list and `references/installation.md` for
the directory layout.

### 3) Predict (GPU)

The wrapper handles `--nv` and the weights bind-mount:

```bash
cd ~/Repos/Protenix
apptainer/run_protenix.sh pred \
    -i examples/input.json \
    -o ./output \
    -n protenix_base_default_v1.0.0 \
    --use_default_params true \
    --seeds 101 --sample 5
```

Equivalent manual invocation:

```bash
apptainer run --nv \
    --bind /shared/ModelWeights/Protenix:/shared/ModelWeights/Protenix \
    --env PROTENIX_ROOT_DIR=/shared/ModelWeights/Protenix \
    apptainer/protenix.sif pred -i examples/input.json -o ./output \
    -n protenix_base_default_v1.0.0 --use_default_params true
```

- `--nv` exposes the host GPU (required; CPU is impractical).
- Apptainer auto-mounts `$HOME` and `$PWD`, so inputs/outputs under them resolve
  without extra binds. Bind anything outside with `--bind SRC:DST`.
- Restrict GPUs with `--env CUDA_VISIBLE_DEVICES=0`.
- **Don't launch from inside a Protenix checkout** unless you mean to — cwd
  shadows the baked-in `/opt/protenix` and JIT artifacts get written into your
  tree (harmless, but messy). Run from a data dir. See `references/installation.md`.

### 4) Read the output

```
output/<name>/<seed>/
  ├── <name>_<seed>_sample_0.cif                       # predicted structure
  ├── <name>_<seed>_summary_confidence_sample_0.json   # scores
  └── ...                                              # one per sample
```

Rank samples by **`ranking_score`** (higher = better; Protenix sorts by it by
default). Full layout + every score in `references/outputs.md`.

## The `protenix` CLI at a glance

| Subcommand | Purpose |
|------------|---------|
| `protenix pred` | Run structure prediction on a JSON file/dir (the main command) |
| `protenix json` | Convert PDB/CIF → Protenix input JSON (`--altloc`, `--assembly_id`) |
| `protenix msa`  | MSA search (MMseqs2) for a JSON or FASTA; writes MSA paths back |
| `protenix mt`   | MSA search **then** template search |
| `protenix prep` | MSA + template + RNA-MSA search (full input preprocess) |

Most-used `pred` flags (short / long → meaning):

| Flag | Meaning |
|------|---------|
| `-i/--input` | Input JSON file **or directory** of JSONs (required) |
| `-o/--out_dir` | Output dir (default `./output`) |
| `-n/--model_name` | Checkpoint, e.g. `protenix_base_default_v1.0.0` (default) |
| `--use_default_params` | **Set `true`** — picks correct cycle/step per model |
| `-s/--seeds` | Comma-separated seeds, e.g. `101,102,103` |
| `-e/--sample` | Diffusion samples per seed (default 5) |
| `-c/--cycle` / `-p/--step` | Pairformer cycles / diffusion steps (override) |
| `--use_msa` | Use MSA (default true; auto-searches if no paths in JSON) |
| `--use_template` / `--use_rna_msa` | Enable templates / RNA MSA (v1.0.0/20250630/v2 only) |
| `--need_atom_confidence` | Also emit per-atom confidence |
| `-d/--dtype` | `bf16` (default) or `fp32` |

Every flag (including the kernel selectors `--trimul_kernel` / `--triatt_kernel`,
`--msa_server_mode`, `--use_tfg_guidance`, and the hmmer/RNA-DB paths) is
documented in `references/cli.md`.

## Input JSON in 30 seconds

Input is an **AlphaFold-Server-style** list of jobs. Each job has a `name` and a
list of `sequences` (entities). Minimal protein monomer:

```json
[
  {
    "name": "my_protein",
    "sequences": [
      { "proteinChain": { "sequence": "MAQGSHQ...HF", "count": 1 } }
    ]
  }
]
```

Entities: `proteinChain`, `dnaSequence`, `rnaSequence`, `ligand`, `ion`.
Ligands accept a **CCD code** (`"CCD_ATP"`), a **SMILES** string, or a 3D file
(`"FILE_/path/lig.sdf"`). You can add `modifications` (PTMs), `covalent_bonds`
between entities, precomputed MSA/template paths, and soft `contact`/`pocket`
`constraint`s. Full schema with copy-paste examples: `references/inputs.md` and
`examples/input_examples.md`.

## Choosing a model

- **`protenix_base_default_v1.0.0`** — recommended default (368 M, AF3-aligned
  data cutoff, supports MSA + templates + RNA MSA).
- **`protenix_base_20250630_v1.0.0`** — same size, newer data cutoff (2025-06-30)
  for practical/applied use.
- **`protenix-v2`** — best accuracy (464 M, antibody-antigen gains) **but the
  checkpoint is not currently served publicly** (download returns 403).
- **`protenix_base_constraint_v0.5.0`** — required for `pocket`/`contact`
  constraints.
- **`protenix_mini_default_v0.5.0` / `protenix_tiny_default_v0.5.0`** — fast,
  for high-throughput screening (cycle 4 / step 5).
- **`protenix_mini_esm_v0.5.0` / `_ism_`** — single-sequence (no MSA) ESM-based;
  need the ESM2-3B weights and are **not** downloaded by the default script.

Full table (params, features, default cycle/step) in `references/models.md`.

## Confidence — what to rank on

Each sample's `*_summary_confidence_*.json` reports AlphaFold3-style scores:

- **`ranking_score`** — the headline ranking metric (higher = better). Protenix
  sorts samples by it.
- **`plddt`** — per-residue confidence, higher better.
- **`ptm` / `iptm`** — global / interface predicted TM-score (→1 better); use
  `iptm` and `chain_pair_iptm` to judge interfaces.
- **`has_clash`**, **`gpde`**, **`disorder`**, per-chain breakdowns.

Definitions and how to combine them in `references/outputs.md`.

## Reference index

- `references/installation.md` — building the SIF (`apptainer/` scripts,
  fakeroot, cluster builds), the host weights layout + `download_weights.sh`,
  bind-mounts, GPU selection, kernel JIT cache, conda/Docker alternatives.
- `references/cli.md` — every `protenix` subcommand and `pred` flag with semantics.
- `references/inputs.md` — input JSON schema: entities, modifications, ligands,
  covalent bonds, MSA/template paths, pocket/contact constraints, `protenix json`.
- `references/models.md` — the model zoo, capabilities, default params, weights.
- `references/outputs.md` — output layout + every confidence score and how to rank.
- `references/troubleshooting.md` — build, weights, GPU/kernel, and input failures.
- `examples/run_examples.sh` — copy-paste `run_protenix.sh` / `apptainer` invocations.
- `examples/input_examples.md` — input JSONs (monomer, complex+ligand, DNA,
  covalent bond, constraints).

## Installing this skill

```bash
# Symlink (recommended — picks up edits live)
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/protenix
# Or copy:
cp -R . ~/.claude/skills/protenix
```

After that, an agent invokes it via `Skill(skill="protenix")`.

## Citation

Protenix, ByteDance AML AI4Science Team. Apache-2.0.

```
ByteDance AML AI4Science Team et al.
Protenix — Advancing Structure Prediction Through a Comprehensive
AlphaFold3 Reproduction. bioRxiv 2025.01.08.631967.
https://www.biorxiv.org/content/10.1101/2025.01.08.631967

Zhang et al. Protenix-v2: Broadening the Reach of Structure Prediction
and Biomolecular Design. bioRxiv 2026.04.10.717613.
```
</content>
</invoke>
