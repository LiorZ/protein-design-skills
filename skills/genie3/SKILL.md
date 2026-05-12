---
name: genie3
description: >
  Run de-novo protein design with Genie 3 — a fast, all-atom, SE(3)-equivariant
  diffusion model. Use this skill when:
  (1) Generating unconditional monomeric protein backbones (length 50–600+),
  (2) Solving motif-scaffolding problems (single- and multi-motif),
  (3) Designing protein binders for a target with hotspot residues,
  (4) Running beam search or iterative-conditioning binder pipelines,
  (5) Loading legacy Genie 2 (Cα-trace) checkpoints,
  (6) Training the Genie 3 model from scratch.

  This skill covers installation, the unified `genie3` CLI (run / generate /
  evaluate / status / train), the experiment YAML schema, the three
  application workflows, multi-GPU + multi-node sharding, problem-set
  preparation, output layout, and the in-silico success filters.

  Pairs with: `proteinmpnn` (inverse folding), `colabfold` / `esmfold`
  (structure prediction back-ends used by the evaluation pipeline),
  `foldseek` (cluster successful designs), `protein-qc` (QC thresholds),
  and `binder-design` (tool selection between Genie 3, BindCraft, RFdiffusion,
  BoltzGen).
license: MIT
category: design-tools
tags: [structure-design, backbone-generation, motif-scaffolding, binder, diffusion, equivariant]
repo: https://github.com/aqlaboratory/genie3
preprint: https://www.biorxiv.org/content/10.64898/2026.05.01.722168v1
---

# Genie 3 — Fast All-Atom SE(3)-Equivariant Protein Design

## What this is

Genie 3 is a single diffusion model with three application modes selected by
the YAML config:

| `generation.dataset.source` | `evaluation.version` | What it does |
|-----------------------------|----------------------|--------------|
| `unconditional`             | `unconditional`      | De-novo monomers; sweep length range |
| `motif`                     | `scaffold`           | Motif scaffolding (single or multi) |
| `target`                    | `binder`             | Binder design against a target PDB + hotspots |

All workflows are driven by one CLI: `genie3 {run, generate, evaluate, status, train}`.
A single `genie3` conda env covers everything (incl. ColabFold, ESMFold, ProteinMPNN, FoldSeek, TMscore, DSSP).

## Prerequisites

| Requirement   | Minimum               | Notes |
|---------------|-----------------------|-------|
| OS            | Linux (x86_64)        | Setup script targets Linux |
| GPU           | NVIDIA, CUDA 12+      | Required for generation, ColabFold, ESMFold |
| GPU VRAM      | 24 GB                 | 40+ GB for long monomers / beam search / large complexes |
| Conda         | Any modern conda      | The setup script creates the `genie3` env (Python 3.10) |
| Disk          | ~30 GB                | ColabFold AF2 multimer weights + pretrained Genie 3 checkpoint + datasets |
| Network       | Internet at setup     | HuggingFace + ColabFold MSA server (only at problem-prep time) |

## Three-step quick start

### 1) Install (one-time)

```bash
git clone https://github.com/aqlaboratory/genie3.git
cd genie3
bash scripts/setup/setup.sh        # creates conda env "genie3", installs all deps
bash scripts/setup/download.sh     # downloads pretrained weights + training data
conda activate genie3
```

The setup script installs into the `genie3` conda env: torch 2.7.1, ColabFold (alphafold-multimer-v3 weights), ESMFold (openfold + ESM2), ProteinMPNN, FoldSeek, TMscore/TMalign, DSSP. See [references/setup.md](references/setup.md).

### 2) Pick an example config

```bash
genie3 run -c examples/unconditional/experiment.yaml      # de-novo monomers
genie3 run -c examples/motif_scaffolding/experiment.yaml  # motif scaffolding
genie3 run -c examples/binder_design/experiment.yaml      # binder design
```

`run` chains generate → evaluate → reduce in three child processes (so GPU memory is freed between stages). To split stages or run multi-node, see step 3.

### 3) Inspect outputs

Every config sets `paths.rootdir`. Results land under `<rootdir>/results/` (or `<rootdir>/<problem_name>/results/` for per-problem tasks). The most useful files:

- `info.csv` — per-design metrics (one row per generated sample)
- `successful_*_generations/` and `v0_success/` — PDBs that passed in-silico filters
- `successful_*_cluster.csv` — FoldSeek clusters at TM 0.5/0.6/0.8

See [references/outputs.md](references/outputs.md) for full schema and success criteria.

## CLI at a glance

| Command | Description |
|---------|-------------|
| `genie3 run -c <CFG>` | Generate + evaluate + reduce, all in one |
| `genie3 generate -c <CFG>` | Generation only (one shard) |
| `genie3 evaluate -c <CFG>` | Evaluate one shard |
| `genie3 evaluate --reduce -c <CFG>` | Merge shard outputs and produce final CSVs |
| `genie3 status -c <CFG>` | Show shard/round progress |
| `genie3 train --config <CFG> -d N` | Train the model |

Shared flags: `-c/--config`, `--num-devices N`, `--shard-id ID`, `--num-shards N`, `--verbose`, `--log-dir <DIR>`. Full reference in [references/cli.md](references/cli.md).

## Choosing the right reference doc

| You want to… | Read |
|--------------|------|
| Install the env or download weights | [references/setup.md](references/setup.md) |
| Understand every CLI flag and process model | [references/cli.md](references/cli.md) |
| Author or modify an experiment YAML | [references/configuration.md](references/configuration.md) |
| Run unconditional generation | [references/unconditional.md](references/unconditional.md) |
| Run motif scaffolding (single or multi-motif) | [references/motif-scaffolding.md](references/motif-scaffolding.md) |
| Run binder design (basic) | [references/binder-design.md](references/binder-design.md) |
| Use beam search or iterative conditioning for binders | [references/iterative-and-beam.md](references/iterative-and-beam.md) |
| Build a new binder problem set from PDB targets | [references/problem-prep.md](references/problem-prep.md) |
| Distribute work across many GPUs / nodes | [references/multi-node.md](references/multi-node.md) |
| Read the per-design CSV columns and success filters | [references/outputs.md](references/outputs.md) |
| Train the model from scratch | [references/training.md](references/training.md) |
| Diagnose failures | [references/troubleshooting.md](references/troubleshooting.md) |

## Quick decision tree (which application?)

- **You want diverse de-novo monomers, no constraint** → `unconditional`. Tune `direction_scale` (0.8 short / 0.0 long) and length range.
- **You have a functional motif (active site, epitope) and want a scaffold around it** → `motif`. Define the motif PDB with `REMARK 999` headers + a problem JSON (`segment_config_str`).
- **You have a target PDB and want a binder for it** → `target`. Provide hotspot residues and binder length range. Choose folding `mode: template` (no MSA) for speed or `msa` for accuracy.

If you don't know whether Genie 3 is the right tool vs BindCraft / RFdiffusion / BoltzGen, consult the `binder-design` skill (tool selection guide).

## Hard rules / gotchas

1. **Always activate the env first**: `conda activate genie3`. The CLI dispatches to itself via `subprocess`, so `genie3` must be on PATH.
2. **`paths.rootdir` is the single source of truth for output**. Do not also set `generation.io.outdir` — the loader will reject conflicting values.
3. **Do not set `generation.dataset.datadir`** — use `paths.dataset` instead. Same for `reward.reward.datadir`.
4. **First chain in any binder PDB must be the binder chain**. The reducer extracts chain `A` as the binder.
5. **Re-running `genie3 run` resumes from the last incomplete stage** (sharded or iterative). Sentinel files (`.generate_done`, `.evaluate_done`, `.shard_markers/`) drive this.
6. **`genie3 evaluate --reduce` runs once after all evaluation shards finish**. Don't shard the reduce step.
7. **`direction_scale` heavily affects quality/diversity**. Defaults: `0.8` for short monomers (≤300), `0.0` for long monomers (>300) and binders, `0.1` for motif scaffolding.
8. **ColabFold MSAs** are only needed for problem prep (`prepare.py`) and for `evaluation.folding.mode: msa`. The MSA server is queried over the network at prep time.
9. **Beam search batches**: `n_sample` in beam mode means *number of beam-search runs*, and the loader auto-divides by `beam_width` to hit your requested total. See [references/iterative-and-beam.md](references/iterative-and-beam.md).
10. **Iterative `cond_strategy: iter_common*`** computes the common interface from prior rounds' successes and *caches it under `<rootdir>/problems/<problem>.json`* — that is the dataset path used by subsequent rounds.

## Where to install the skill

This directory (`skill/`) is the skill payload. To make it discoverable to a Claude Code agent on this machine:

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skill" ~/.claude/skills/genie3
# or copy:
cp -R skill ~/.claude/skills/genie3
```

After that, an agent can invoke it via the Skill tool with `skill: genie3` (or you can include the marketplace structure if publishing). Skills are loaded by name from `~/.claude/skills/<name>/SKILL.md` and may reference files in their own directory.

## Citation

```bibtex
@article{lin2026genie3,
  title   = {Fast and Ultra-Capable Protein Design: Advancing the Frontier
             Through Atomistic SE(3)-Equivariance with Genie 3},
  author  = {Lin, Yeqing and Lee, Minji and Vermani, Aakarsh and Jiang, Ellena
             and {De Cooman}, Sebastiaan and Spetko, Matej and AlQuraishi, Mohammed},
  journal = {bioRxiv},
  year    = {2026},
  doi     = {10.64898/2026.05.01.722168}
}
```
