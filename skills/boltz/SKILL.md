---
name: boltz
description: >
  Run Boltz-1 / Boltz-2, MIT-licensed open foundation models for biomolecular
  structure and binding-affinity prediction. Use this skill when:
  (1) Predicting structures of protein monomers, multimers, and protein-protein
      complexes,
  (2) Predicting protein-ligand complexes (ligands as SMILES or CCD codes),
  (3) Predicting protein-DNA, protein-RNA, or mixed nucleic-acid complexes,
  (4) Predicting binding affinity (probability of binding and log10(IC50))
      between a small molecule and a protein target — Boltz-2 only,
  (5) Validating designed binders / antibodies against a target (alternative
      to AlphaFold2 / Chai-1 with comparable or better accuracy on complexes,
      and 1000x faster than physics-based FEP for affinity),
  (6) Folding with pocket / contact / covalent-bond / template restraints,
  (7) Modeling cyclic peptides, modified residues (CCD), and non-canonical
      covalent bonds,
  (8) Running batched inference across one or many GPUs from a directory of
      YAML inputs.

  Covers installation (pip, GitHub, Docker), the `boltz predict` CLI and every
  flag, the YAML input schema (sequences / constraints / templates /
  properties), the deprecated FASTA format, MSA provisioning (ColabFold
  MMseqs2 server, custom `.a3m`, paired CSV, `empty` single-sequence mode,
  authenticated servers), the output layout (CIF/PDB structures, confidence
  JSON, affinity JSON, PAE / PDE / pLDDT NPZ files), Boltz-1 vs Boltz-2
  feature parity, and the cache layout (`~/.boltz` or `$BOLTZ_CACHE`).

  Pairs with: `chai-lab` and `alphafold` (alternative structure predictors),
  `ipsae` (better ranking for binder design than ipTM), `protein-qc` (QC
  thresholds for designed binders), `binder-design` (tool selection for design
  campaigns), `bindcraft` / `rfdiffusion` / `boltzgen` / `genie3` (binder
  backbone generators whose outputs you validate with Boltz).
license: MIT
category: structure-prediction
tags: [structure-prediction, protein-complex, protein-ligand, affinity, msa, restraints, antibody, binder-validation, cyclic-peptide, foundation-model]
repo: https://github.com/jwohlwend/boltz
preprint_boltz1: https://doi.org/10.1101/2024.11.19.624167
preprint_boltz2: https://doi.org/10.1101/2025.06.14.659707
slack: https://boltz.bio/join-slack
---

# Boltz-1 / Boltz-2 — Open Biomolecular Structure & Affinity Prediction

## What this is

Boltz is a family of MIT-licensed (code + weights) biomolecular foundation
models from the Barzilay / Jaakkola groups at MIT:

| Model     | Released | Highlights |
|-----------|----------|------------|
| **Boltz-1** | Nov 2024 | First fully open model to approach AlphaFold-3 accuracy on the PDB benchmark. Structure only. |
| **Boltz-2** | Jun 2025 | New foundation model. Beats AF3 / Boltz-1 on structure and jointly predicts **binding affinity** (`log10(IC50)` + binder probability). Approaches FEP accuracy at ~1000x lower cost. Adds **templates**, **multi-pocket constraints**, **contact constraints**. |

Boltz-2 is the default (`--model boltz2`); Boltz-1 is retained for parity
with the original Boltz-1 paper (pass `--model boltz1`).

One model handles all of the following entities, declared in a YAML schema:

| Entity   | YAML keyword | What you provide |
|----------|--------------|------------------|
| Protein  | `protein`    | 1-letter sequence (+ optional `msa`, `modifications`, `cyclic`) |
| DNA      | `dna`        | `ACGT` sequence |
| RNA      | `rna`        | `ACGU` sequence |
| Ligand   | `ligand`     | SMILES string **or** 3-letter CCD code (exclusive) |

Output: by default **one mmCIF per diffusion sample** ranked by an aggregate
confidence score, plus a per-sample confidence JSON (pTM / ipTM / pLDDT
breakdown, per-chain and per-chain-pair) and per-token PAE / PDE / pLDDT NPZ
files. If `properties.affinity` is set, an `affinity_*.json` is also written.

## Prerequisites

| Requirement   | Recommended                       | Notes |
|---------------|-----------------------------------|-------|
| OS            | Linux                             | macOS works on CPU only |
| Python        | 3.10 — 3.12                       | `requires-python = ">=3.10,<3.13"` |
| GPU           | NVIDIA, CUDA 12.x, bfloat16       | RTX 4090 / A10 / A30 fine for small complexes; A100 / H100 / L40S for big ones. cuEquivariance kernels accelerate recent NVIDIA cards. Old GPUs: pass `--no_kernels`. |
| Disk          | ~5 GB cache                       | Weights + CCD auto-download into `~/.boltz` (or `$BOLTZ_CACHE`). |
| Network       | Needed for first weight download, and for `--use_msa_server` (ColabFold MMseqs2) | |

Boltz can run on CPU (no `[cuda]` extras), but is significantly slower —
treat that as a fallback for unit testing only. TPU is also accepted
(`--accelerator tpu`) but seldom used.

## Three-step quick start

### 1) Install

```bash
# Recommended (PyPI, with CUDA extras):
pip install -U "boltz[cuda]"

# Or development build:
git clone https://github.com/jwohlwend/boltz.git
cd boltz && pip install -e ".[cuda]"

# CPU-only (slow):
pip install -U boltz
```

A `boltz` console script is installed. On first run it auto-downloads:

- `boltz2_conf.ckpt` (structure model) and `boltz2_aff.ckpt` (affinity head)
- `mols.tar` → `mols/` (per-residue / per-ligand reference structures for Boltz-2)
- `ccd.pkl` (Boltz-1 CCD dictionary, if you also use Boltz-1)

into `~/.boltz` (override with `--cache /path` or env `BOLTZ_CACHE=/abs/path`).

### 2) Write a YAML and predict

```yaml
# /tmp/example.yaml
version: 1
sequences:
  - protein:
      id: A
      sequence: MVTPEGNVSLVDESLLVGVTDEDRAVRSAHQFYERLIGLWAPAVMEAAHELG
  - ligand:
      id: B
      smiles: 'N[C@@H](Cc1ccc(O)cc1)C(=O)O'
properties:
  - affinity:
      binder: B          # Boltz-2 only
```

```bash
boltz predict /tmp/example.yaml --use_msa_server --out_dir /tmp/boltz_out
```

`--use_msa_server` is essentially mandatory for protein chains unless you
supply a local `.a3m` (`msa: path/to.a3m`) or explicitly opt out
(`msa: empty`, which is single-sequence mode and degrades accuracy).

### 3) Inspect outputs

```
/tmp/boltz_out/
└── boltz_results_example/
    ├── predictions/
    │   └── example/
    │       ├── example_model_0.cif                 # best (highest confidence_score)
    │       ├── confidence_example_model_0.json     # ptm, iptm, plddt, per-chain, per-pair
    │       ├── pae_example_model_0.npz             # if --write_full_pae
    │       ├── pde_example_model_0.npz             # if --write_full_pde
    │       ├── plddt_example_model_0.npz
    │       ├── affinity_example.json               # if properties.affinity was set
    │       └── ...                                 # one set per diffusion sample
    ├── processed/                                  # preprocessed inputs (caches between runs)
    └── lightning_logs/
```

The candidate with the highest `confidence_score` (≈ `0.8 * complex_plddt + 0.2 * iptm`) is the recommended pick.
See [references/outputs.md](references/outputs.md) for the full schema.

## CLI at a glance

| Command | Purpose |
|---------|---------|
| `boltz predict INPUT [OPTIONS]` | Predict structure (+ affinity) for one YAML, one FASTA, or a **directory** of either. |

`INPUT` can be:

- a single `.yaml` / `.fasta` file, **or**
- a directory; every `.yaml` and `.fasta` inside is predicted.

The most important flags (full list in [references/cli.md](references/cli.md)):

| Flag | Meaning |
|------|---------|
| `--out_dir PATH` | Where to save the predictions (default `./`). A `boltz_results_<input_stem>/` directory is created inside. |
| `--cache PATH` | Where to download / look up model weights and CCD (default `~/.boltz`, or `$BOLTZ_CACHE`). |
| `--use_msa_server` | Auto-generate MSAs via ColabFold MMseqs2 (`https://api.colabfold.com`). |
| `--msa_server_url URL` | Self-hosted ColabFold endpoint. |
| `--msa_pairing_strategy greedy\|complete` | MSA pairing for multimers (default `greedy`). |
| `--use_potentials` | Inference-time potentials for better physical plausibility (slower but cleaner poses). |
| `--model boltz1\|boltz2` | Which checkpoint (default `boltz2`). |
| `--method NAME` | Condition the prediction on a structural-determination method (e.g. `x-ray diffraction`, `electron microscopy`, `md`, `afdb`, `boltz-1`). Boltz-2 only. |
| `--recycling_steps N` | Trunk recycles (default 3; AF3-style is 10). |
| `--sampling_steps N` | Diffusion sampling steps (default 200). |
| `--diffusion_samples N` | Number of candidate structures (default 1; AF3-style is 25). |
| `--max_parallel_samples N` | Parallel diffusion batch (default 5). |
| `--step_scale FLOAT` | Diffusion temperature; default 1.5 (Boltz-2) / 1.638 (Boltz-1). Lower → more diverse. |
| `--output_format mmcif\|pdb` | Output format (default `mmcif`). |
| `--devices N` | GPUs to use; >1 enables DDP. |
| `--accelerator gpu\|cpu\|tpu` | Default `gpu`. |
| `--seed N` | RNG seed. |
| `--override` | Re-run instead of reusing cached `processed/` and existing predictions. |
| `--write_full_pae` / `--write_full_pde` | Dump per-token PAE / PDE NPZ. |
| `--write_embeddings` | Dump `s` and `z` embeddings as NPZ. |
| `--no_kernels` | Disable cuEquivariance kernels (use this on old NVIDIA cards). |
| `--num_workers N` | DataLoader workers (default 2). |
| `--preprocessing-threads N` | Threads for preprocessing (default = cpu count). |
| `--max_msa_seqs N` | Cap MSA depth (default 8192). |
| `--subsample_msa` / `--num_subsampled_msa N` | Subsample MSA at runtime. |

Affinity (Boltz-2 only — see [references/affinity.md](references/affinity.md)):

| Flag | Meaning |
|------|---------|
| `--sampling_steps_affinity N` | Default 200. |
| `--diffusion_samples_affinity N` | Default 5. |
| `--affinity_mw_correction` | Add the molecular-weight correction to the affinity head. |
| `--affinity_checkpoint PATH` | Custom affinity checkpoint. |

MSA server auth — see [references/msas.md](references/msas.md).

## Choosing the right reference doc

| You want to… | Read |
|--------------|------|
| Install, manage downloads, use the Docker image, configure cache | [references/installation.md](references/installation.md) |
| See every CLI flag with examples | [references/cli.md](references/cli.md) |
| Author the YAML input (sequences, ligands, modifications, cyclic) | [references/inputs.md](references/inputs.md) |
| Add MSAs (ColabFold server, local `.a3m`, paired CSV, auth) | [references/msas.md](references/msas.md) |
| Supply structural templates (CIF / PDB) | [references/templates.md](references/templates.md) |
| Use pocket / contact / covalent-bond constraints | [references/constraints.md](references/constraints.md) |
| Predict binding affinity with Boltz-2 | [references/affinity.md](references/affinity.md) |
| Read the CIF / JSON / NPZ outputs | [references/outputs.md](references/outputs.md) |
| Validate a designed binder / antibody | [references/binder-validation.md](references/binder-validation.md) |
| Run hundreds of YAMLs across GPUs | [references/batch.md](references/batch.md) |
| Train / retrain on your own data | [references/training.md](references/training.md) |
| Diagnose OOM, kernel, MSA, weight-download failures | [references/troubleshooting.md](references/troubleshooting.md) |
| Boltz-1 vs Boltz-2 feature matrix and migration notes | [references/boltz1-vs-boltz2.md](references/boltz1-vs-boltz2.md) |

## Quick decision tree

- **You just have sequences and want a structure** → 1-chain YAML, `boltz predict in.yaml --use_msa_server`. Defaults are fine.
- **You want AF3-level sampling (5 samples × 10 recycles)** → `--diffusion_samples 5 --recycling_steps 10`. ~10x slower.
- **You designed a binder and want to validate it** → 2-chain YAML (binder + target), `--use_msa_server`. Score with ipTM and (better) ipSAE; see the `ipsae` and `protein-qc` skills.
- **You want a binding-affinity number for a small molecule** → Boltz-2 YAML with `properties.affinity.binder: <ligand_id>`. Output is `affinity_pred_value` (`log10(IC50_µM)`, *lower = stronger binder*) and `affinity_probability_binary` (probability the ligand binds at all). See [references/affinity.md](references/affinity.md).
- **You know the binding pocket / specific contacts** → add a `pocket` or `contact` constraint to your YAML; set `force: true` to enforce it via a potential.
- **Cyclic peptide** → `cyclic: true` on the `protein` entry.
- **Modified residue with a CCD code** → `modifications: [{position: 5, ccd: MSE}]` on the polymer.
- **Glycoprotein or covalently-bound ligand** → declare the ligand and the polymer separately, then add a `bond` constraint linking the relevant atoms.
- **Many YAMLs, several GPUs** → put them in a directory, `boltz predict dir/ --devices 4`. Predictions are sharded via DDP.
- **You want the easiest UI** → no official web server; use the CLI or the [Slack community](https://boltz.bio/join-slack) for help.

If Boltz is not the right tool, the alternatives are:

- **Chai-1** (`chai-lab` skill) — similar foundation-model architecture, open weights, FASTA-like input, strong on glycans and explicit covalent bonds.
- **AlphaFold 2 / 3** (`alphafold` skill) — AF2 is the long-standing baseline; AF3 is closed-source (web only).
- **ESMFold** — single-sequence, monomers only; fastest, lower accuracy on complexes.

## Hard rules / gotchas

1. **The output directory is reused across runs.** Boltz keeps `processed/` and skips inputs whose predictions already exist. Pass `--override` to redo from scratch when you change parameters but reuse the same `--out_dir`.
2. **One affinity ligand per YAML.** `properties.affinity.binder` must be a single `ligand` chain ID (not a list, not a polymer). Boltz-2 only.
3. **Affinity ligand size caps.** Hard limit: **≤ 128 heavy atoms** (counted after `RDKit RemoveHs`). Training cap was **56**: ligands larger than that produce a `WARNING` and unreliable values.
4. **Affinity vs. protein only.** Running affinity on an RNA/DNA/cofactor target will not crash but the output is **unreliable** — Boltz-2 was trained only on small-molecule × protein.
5. **Pocket distance.** `max_distance` in `pocket` / `contact` constraints accepts 4–20 Å (default 6 Å). For Boltz-1, only 6 Å is supported, and at most one pocket constraint per YAML; Boltz-2 lifts both limits.
6. **Templates and contact constraints are Boltz-2 only** — they raise on Boltz-1.
7. **`--use_msa_server` and a local MSA can be mixed**: chains with `msa: path/to.a3m` use the local file; chains without `msa:` go to the server. `msa: empty` forces single-sequence (not recommended).
8. **Paired multimer MSAs** require CSV (`sequence,key`) not `.a3m`, with matching `key`s across chains.
9. **Names / chain IDs.** Polymer and ligand `id`s must be unique. Use a list (`[A, B]`) for identical entities — Boltz handles symmetry / pairing automatically.
10. **Atom-name precision matters for bonds.** `bond.atom1: [chain, residue_idx, ATOM_NAME]` uses **CCD-standard atom names** (case-sensitive). Verify against the RCSB CCD entry for that residue.
11. **1-indexed residues.** `position`, `RES_IDX`, and contact / bond / pocket residue indices all start at 1.
12. **Step scale.** Default differs between models (1.638 Boltz-1, 1.5 Boltz-2). Lower → more diverse samples; recommended range 1–2.
13. **Old NVIDIA cards.** If you see a `cuequivariance` import / runtime error, add `--no_kernels` — slight perf hit but it works.
14. **FASTA input is deprecated.** It cannot express modifications, covalent bonds, pocket conditioning, templates, or affinity. Always prefer YAML.

## Installing this skill

```bash
# Symlink (recommended — picks up edits live)
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/boltz

# Or copy:
cp -R . ~/.claude/skills/boltz
```

After that, an agent can invoke it via `Skill(skill="boltz")`.

## Citation

```bibtex
@article{passaro2025boltz2,
  author  = {Passaro, Saro and Corso, Gabriele and Wohlwend, Jeremy and Reveiz, Mateo and Thaler, Stephan and Somnath, Vignesh Ram and Getz, Noah and Portnoi, Tally and Roy, Julien and Stark, Hannes and Kwabi-Addo, David and Beaini, Dominique and Jaakkola, Tommi and Barzilay, Regina},
  title   = {Boltz-2: Towards Accurate and Efficient Binding Affinity Prediction},
  year    = {2025},
  doi     = {10.1101/2025.06.14.659707},
  journal = {bioRxiv}
}

@article{wohlwend2024boltz1,
  author  = {Wohlwend, Jeremy and Corso, Gabriele and Passaro, Saro and Getz, Noah and Reveiz, Mateo and Leidal, Ken and Swiderski, Wojtek and Atkinson, Liam and Portnoi, Tally and Chinn, Itamar and Silterra, Jacob and Jaakkola, Tommi and Barzilay, Regina},
  title   = {Boltz-1: Democratizing Biomolecular Interaction Modeling},
  year    = {2024},
  doi     = {10.1101/2024.11.19.624167},
  journal = {bioRxiv}
}

@article{mirdita2022colabfold,
  title   = {ColabFold: making protein folding accessible to all},
  author  = {Mirdita, Milot and Sch{\"u}tze, Konstantin and Moriwaki, Yoshitaka and Heo, Lim and Ovchinnikov, Sergey and Steinegger, Martin},
  journal = {Nature methods},
  year    = {2022}
}
```
