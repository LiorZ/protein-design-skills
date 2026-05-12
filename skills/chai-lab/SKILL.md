---
name: chai-lab
description: >
  Run Chai-1, a multi-modal foundation model for molecular structure
  prediction. Use this skill when:
  (1) Predicting the structure of a protein, protein-protein, or
      protein-peptide complex,
  (2) Predicting protein-ligand complexes (ligands provided as SMILES or
      CCD codes),
  (3) Predicting protein-DNA, protein-RNA, or mixed nucleic-acid complexes,
  (4) Predicting glycosylated proteins or proteins with non-canonical
      covalent modifications,
  (5) Validating designed binders / antibodies against a target,
  (6) Folding with user-supplied contact / pocket restraints to guide
      complex assembly,
  (7) Generating MSAs via the ColabFold server or supplying your own
      `.aligned.pqt` files / templates,
  (8) Running batch inference distributed across multiple GPUs.

  Covers installation, the `chai-lab` CLI (`fold`, `fold-batch`,
  `a3m-to-pqt`, `citation`), the Python API (`run_inference`,
  `run_folding_on_context`), Chai's FASTA-like input format (proteins,
  ligands, glycans, modified residues, DNA, RNA), the restraints CSV
  format (contact / pocket / covalent), MSA + template provisioning,
  and how to read the per-sample CIF outputs and `scores.npz` ranking
  files (pTM, ipTM, pLDDT, PAE, PDE, clash flags, aggregate score).

  Pairs with: `boltz` and `alphafold` (alternative structure
  predictors), `ipsae` (better ranking for binder design than ipTM),
  `protein-qc` (QC thresholds for designed binders), `binder-design`
  (tool selection for design campaigns), `bindcraft` / `rfdiffusion` /
  `boltzgen` / `genie3` (binder backbone generators whose outputs you
  validate with Chai).
license: Apache-2.0
category: structure-prediction
tags: [structure-prediction, protein-complex, protein-ligand, msa, restraints, glycan, antibody, binder-validation, foundation-model]
repo: https://github.com/chaidiscovery/chai-lab
preprint: https://www.biorxiv.org/content/10.1101/2024.10.10.615955
webserver: https://lab.chaidiscovery.com
---

# Chai-1 — Multi-Modal Structure Prediction

## What this is

Chai-1 is a single open-weight foundation model (Apache-2.0, weights + code)
that predicts the all-atom 3D structure of a complex specified by a FASTA-like
file. One model handles all of:

| Input entity | How it is written in FASTA |
|--------------|----------------------------|
| Protein      | `>protein\|name=...` + canonical 1-letter sequence (modified residues as `AAA(CCD)AAA`, e.g. `RKDES(MSE)EES` for selenomethionine) |
| Ligand       | `>ligand\|name=...` + a **SMILES** string or a 3-letter **CCD** code |
| DNA          | `>dna\|name=...` + sequence in `ACGT` |
| RNA          | `>rna\|name=...` + sequence in `ACGU` |
| Glycan       | `>glycan\|name=...` + abbreviated glycan syntax, e.g. `NAG(4-1 NAG)` |

Each entity needs a **unique name**. The model jointly handles proteins,
ligands, DNA, RNA, glycans, modified residues, and non-canonical covalent
bonds in a single forward pass.

Output: by default **5 candidate CIF files** per input + per-sample
`scores.model_idx_*.npz` with pTM, ipTM, per-chain pTM, per-chain-pair
ipTM, clash flags, and per-token PAE / PDE / pLDDT.

## Prerequisites

| Requirement   | Minimum                       | Notes |
|---------------|-------------------------------|-------|
| OS            | Linux                         | x86_64 |
| Python        | 3.10+                         | |
| GPU           | NVIDIA, CUDA + bfloat16       | RTX 4090 / A10 / A30 work for small complexes; A100 80GB / H100 80GB / L40S 48GB recommended for big ones |
| Disk          | ~30 GB                        | TorchScript model weights auto-download on first run |
| Network       | Only for `--use-msa-server` / `--use-templates-server` (ColabFold MMseqs2) and the first weight download |

Hard input limits (these will raise `UnsupportedInputError`):

| Limit                    | Value             |
|--------------------------|-------------------|
| Max tokens in a complex  | **2048** (largest crop size in `AVAILABLE_MODEL_SIZES`) |
| Max templates per chain  | **4**             |
| Max MSA depth            | **16,384**        |

A "token" is one amino acid, one nucleotide, or one heavy atom in a ligand
(ligands tokenise per-atom, so big small-molecules eat into the 2048 budget
quickly).

## Three-step quick start

### 1) Install (one-time)

```bash
pip install chai_lab==0.6.1
# or the latest dev build:
pip install git+https://github.com/chaidiscovery/chai-lab.git
```

Pin the version in your requirements (`chai_lab==0.6.1`) — the Python API
moves between releases. Weights are downloaded on first run into
`<site-packages>/chai_lab/downloads/`; override with
`CHAI_DOWNLOADS_DIR=/path/to/cache`.

### 2) Write a FASTA and fold it

```bash
cat > /tmp/example.fasta <<'EOF'
>protein|name=heavy
QVQLVESGGGVVQPGRSLRLSCAASGFTFSSYGMHWVRQAPGKGLEWVAVIWYDGSNKYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAR
>protein|name=light
DIQMTQSPSSLSASVGDRVTITCRASQSISSYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQSYSTPLT
>ligand|name=ATP
Nc1ncnc2n(cnc12)C1OC(COP(O)(=O)OP(O)(=O)OP(O)(O)=O)C(O)C1O
EOF

chai-lab fold /tmp/example.fasta /tmp/chai_out
```

Defaults: 5 diffusion samples, single-sequence (no MSA), no templates,
ESM embeddings on, 3 trunk recycles, 200 diffusion steps, seed unset.

For best accuracy on complex assemblies pass `--use-msa-server`
(and optionally `--use-templates-server`):

```bash
chai-lab fold --use-msa-server --use-templates-server /tmp/example.fasta /tmp/chai_out
```

### 3) Inspect outputs

In `/tmp/chai_out/`:

| File | What it is |
|------|------------|
| `pred.model_idx_{0..4}.cif` | One predicted structure per diffusion sample; pLDDT (0–100) in B-factor column |
| `scores.model_idx_{0..4}.npz` | `aggregate_score`, `ptm`, `iptm`, `per_chain_ptm`, `per_chain_pair_iptm`, `has_inter_chain_clashes`, `chain_chain_clashes` |
| `msas/` | (only if `--use-msa-server`) generated `.aligned.pqt` files + `all_chain_templates.m8` |
| `msa_depth.pdf` | (only if MSAs were used) coverage plot |

The candidate with the highest `aggregate_score` is the recommended pick.
See [references/outputs.md](references/outputs.md) for the full schema and
threshold guidance.

## CLI at a glance

| Command | Purpose |
|---------|---------|
| `chai-lab fold INPUT.fasta OUTDIR` | Fold one complex |
| `chai-lab fold-batch INPUT_DIR OUTDIR [--devices 0,1,2]` | Fold every `.fasta` / `.fa` in a directory, sharded across GPUs |
| `chai-lab a3m-to-pqt DIR` | Convert a3m MSAs to Chai's `aligned.pqt` format |
| `chai-lab citation` | Print the BibTeX citation |

Common `fold` flags (see `chai-lab fold --help`):

| Flag | Meaning |
|------|---------|
| `--use-msa-server` | Query ColabFold MMseqs2 for MSAs |
| `--use-templates-server` | Query for structural templates (requires `--use-msa-server`) |
| `--msa-server-url URL` | Point at a self-hosted ColabFold server |
| `--msa-directory DIR` | Use local `.aligned.pqt` files (exclusive with `--use-msa-server`) |
| `--template-hits-path PATH.m8` | Use local `.m8` template hits |
| `--constraint-path PATH.csv` | Apply contact / pocket / covalent restraints |
| `--num-diffn-samples N` | Number of diffusion samples (default 5) |
| `--num-trunk-recycles N` | Trunk recycles (default 3) |
| `--num-diffn-timesteps N` | Diffusion steps (default 200) |
| `--num-trunk-samples N` | Independent trunk seeds (default 1, each produces `--num-diffn-samples` candidates) |
| `--seed INT` | Random seed |
| `--device cuda:N` | GPU to use |
| `--low-memory / --no-low-memory` | Keep activations on CPU between stages (default on) |
| `--fasta-names-as-cif-chains` | Use the `name=` field as the CIF chain ID (must be valid 1-char IDs) |

The Python API (`from chai_lab.chai1 import run_inference`) takes the same
arguments and returns a `StructureCandidates` dataclass.

## Choosing the right reference doc

| You want to… | Read |
|--------------|------|
| Install, manage downloads, set up an env | [references/installation.md](references/installation.md) |
| See every CLI flag with examples | [references/cli.md](references/cli.md) |
| Drive Chai from Python (`run_inference`, `run_folding_on_context`) | [references/python-api.md](references/python-api.md) |
| Author the FASTA-like input file | [references/inputs.md](references/inputs.md) |
| Add MSAs (ColabFold server, local `.aligned.pqt`, custom databases) | [references/msas.md](references/msas.md) |
| Supply structural templates (.m8 + cif) | [references/templates.md](references/templates.md) |
| Use contact / pocket restraints | [references/restraints.md](references/restraints.md) |
| Specify glycans and other covalent bonds | [references/covalent-bonds.md](references/covalent-bonds.md) |
| Read the CIF + `scores.npz` outputs | [references/outputs.md](references/outputs.md) |
| Run hundreds of FASTAs across multiple GPUs | [references/batch.md](references/batch.md) |
| Validate a designed binder / antibody | [references/binder-validation.md](references/binder-validation.md) |
| Diagnose OOM, weight-download, MSA, ESM failures | [references/troubleshooting.md](references/troubleshooting.md) |

## Quick decision tree

- **You just have sequences and want a structure** → `chai-lab fold input.fasta out/`. Add `--use-msa-server` for accuracy on real complexes.
- **You designed a binder with RFdiffusion / BindCraft / BoltzGen / Genie 3 and want to validate it** → fold (binder, target) as a 2-chain FASTA. Score with ipTM and (better) ipSAE on the resulting CIF. See [references/binder-validation.md](references/binder-validation.md) and the `ipsae` skill.
- **You know specific residue–residue contacts from experiments (e.g. crosslinking, mutagenesis, NMR, epitope mapping)** → write a `.restraints` CSV and pass `--constraint-path`. See [references/restraints.md](references/restraints.md).
- **You want to fold a glycosylated protein or a covalently-bound ligand** → write the glycan as `NAG(4-1 NAG)` in the FASTA and the C–N bond in the restraints CSV with `connection_type=covalent`. See [references/covalent-bonds.md](references/covalent-bonds.md).
- **You have many FASTAs** → `chai-lab fold-batch in_dir/ out_dir/ --devices 0,1,2,3`. Spawns one worker per GPU.
- **You want to integrate Chai into a pipeline** → use the Python API, which returns paths + a `StructureCandidates` dataclass with PAE / PDE / pLDDT tensors and ranking data.
- **You want the easiest UI** → the [Chai Lab web server](https://lab.chaidiscovery.com) runs the same model without any local setup.

If Chai is not the right tool, alternatives are:
- **Boltz-1/2** (`boltz` skill) — open, also strong on complexes, often faster on big inputs.
- **AlphaFold 2 / 3** (`alphafold` skill) — long-standing baseline; AF3 is closed-source via web only.
- **ESMFold** — single-sequence only, monomers; fastest, lower accuracy on complexes.

## Hard rules / gotchas

1. **Each entity in the FASTA must have a unique name** — duplicate names raise `UnsupportedInputError`. Names are referenced from the restraints file as well.
2. **The output directory must be empty (or not exist)**. `run_inference` will refuse to overwrite. Wipe / pick a new dir between runs.
3. **Chains are labelled A, B, C, … in the order they appear in the FASTA**. Restraint files use these letters in `chainA` / `chainB`, *not* the entity name (unless you pass `--fasta-names-as-cif-chains`, in which case `name=` must be a valid single-char chain ID).
4. **`res_idxA` / `res_idxB` are 1-indexed and contain the residue letter as a sanity check**, e.g. `D4` means "the 4th residue, which must be Asp". A mismatch raises.
5. **`--use-msa-server` and `--msa-directory` are mutually exclusive.** Same for `--use-templates-server` and `--template-hits-path`.
6. **Ligands are tokenised per heavy atom**, so a big small-molecule (e.g. a 100-atom natural product) consumes ~100 of the 2048-token budget on its own.
7. **Modified amino acids that have a CCD code go in the sequence in parentheses**: `RKDES(MSE)EES`. Do not specify them via covalent bond restraints.
8. **Glycan ring leaving atoms (OH groups) are auto-stripped only for sugar-ring CCD codes**. For other covalently-attached SMILES ligands, you must supply the SMILES *without* the leaving atom yourself.
9. **The model is single-precision sensitive to seed** — different `--seed` values give meaningfully different candidates. To exhaustively sample, use multiple `--seed`s or raise `--num-trunk-samples` / `--num-diffn-samples`.
10. **Don't use ipTM alone to rank designed binders** — it consistently overconfidences. Use ipSAE (see the `ipsae` skill) on Chai outputs or, at minimum, combine ipTM with pLDDT-at-interface and clash flags. The built-in `aggregate_score` already subtracts a huge penalty (`-100`) when `has_inter_chain_clashes` is true.
11. **The Python API is unstable across releases**. Pin the chai_lab version that your script was written against.

## Installing this skill

```bash
# Symlink (recommended — picks up edits live)
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/chai-lab

# Or copy:
cp -R . ~/.claude/skills/chai-lab
```

After that, an agent can invoke it via `Skill(skill="chai-lab")`.

## Citation

```bibtex
@article{Chai-1-Technical-Report,
  title   = {Chai-1: Decoding the molecular interactions of life},
  author  = {{Chai Discovery}},
  year    = 2024,
  journal = {bioRxiv},
  doi     = {10.1101/2024.10.10.615955}
}
```
