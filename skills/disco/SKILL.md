---
name: disco
description: >
  Run DISCO (DIffusion for Sequence-structure CO-design), a multimodal
  generative model that jointly co-designs a protein sequence and 3D structure,
  conditioned on (and co-folded with) arbitrary biomolecules — small-molecule
  ligands, ions, metals, DNA, or RNA. Use this skill when:
  (1) Generating de novo protein sequence + backbone from scratch
      (unconditional, length-controlled),
  (2) Designing a protein binder / scaffold around a small-molecule ligand
      provided as a SMILES string, an SDF / MOL / MOL2 / PDB file, or a PDB
      CCD code (single-component or multi-component glycans),
  (3) Designing proteins around metals, ions, organometallic catalysts, or
      reactive intermediates (e.g. heme enzymes for new-to-nature carbene
      transfer, B–H insertion, C(sp³)–H insertion, cyclopropanation),
  (4) Designing RNA-binding proteins conditioned on a fixed RNA sequence,
  (5) Designing DNA-binding proteins conditioned on a single-strand or
      explicitly-paired double-strand DNA sequence,
  (6) Partial-mask / sequence-redesign tasks where some residues are fixed
      and the rest are co-generated alongside structure,
  (7) Multi-ligand / multi-cofactor active-site design (combine ligand +
      ion + ligand in the same job; declare covalent_bonds when needed),
  (8) Length sweeps over a fixed target — run many lengths in one input
      JSON and rank by co-designability,
  (9) Reproducing the Studio-179 ligand-conditioned benchmark or running it
      against a single ligand,
  (10) Trading off designability vs. structural diversity via the `designable`
      and `diverse` experiment presets, and quality vs. speed via the
      `effort=fast` and `effort=max` presets,
  (11) Large-scale screening with many seeds per job (run-resume is automatic
      — interrupted runs skip samples that already exist on disk),
  (12) Multi-GPU / multi-node inference via Lightning Fabric (`fabric.num_nodes`,
      `--devices`-style sharding through DDP).

  Covers installation with `uv` (and the AMD GPU caveat around DeepSpeed),
  the optional CUTLASS / DeepSpeed-EvoformerAttention setup, the Hydra-based
  `runner/inference.py` CLI with every documented override, the AlphaFold-Server-
  style input JSON schema (`proteinChain`, `dnaSequence`, `rnaSequence`,
  `ligand`, `ion`, `covalent_bonds`), masking conventions, output layout
  (`pdbs/`, `sequences/`, `ERR/`, `_ligands.txt`), the co-designability
  evaluation metric used by the paper, and the model's hard limitations
  (no multi-chain protein complexes; no motif scaffolding yet).

  Pairs with: `chai` / `boltz` / `alphafold` (refold / validate generated
  designs — the paper uses **Chai-1** to score co-designability), `ipsae`
  (better binder ranking than ipTM / iPAE for the refolded complexes),
  `proteinmpnn` / `ligandmpnn` / `solublempnn` (resample sequences from a
  DISCO-generated backbone if you want a sequence ensemble), `protein-qc`
  (QC thresholds and biophysical filters for designed binders /
  enzymes), `rfdiffusion` / `bindcraft` / `boltzgen` / `genie3` (alternative
  generators; DISCO competes with all four as a joint sequence+structure
  designer).
license: Apache-2.0
category: protein-design
tags: [protein-design, sequence-structure-co-design, diffusion, ligand-conditioned, dna-binding, rna-binding, enzyme-design, foundation-model, all-atom, heme, metalloprotein, studio-179]
repo: https://github.com/DISCO-design/DISCO
arxiv: https://arxiv.org/abs/2604.05181
blog: https://disco-design.github.io/
huggingface_model: https://huggingface.co/DISCO-Design/DISCO
huggingface_dataset: https://huggingface.co/datasets/DISCO-Design/DISCO_benchmark_data
---

# DISCO — Diffusion for Sequence-Structure Co-design

## What this is

DISCO is a multimodal diffusion model that **jointly generates a protein
sequence and a 3D structure in one shot**, optionally conditioned on, and
co-folded with, one or more non-protein entities (small-molecule ligands,
ions, metalloclusters, DNA, RNA). Unlike sequential pipelines
(RFdiffusion → ProteinMPNN → AlphaFold refold), DISCO co-designs both
modalities so that sequence-based objectives can shape structure and
vice versa.

In the paper, DISCO:

- Is **state-of-the-art on 178 / 179** ligands of the Studio-179 benchmark
  (and best on DNA and RNA conditioning) for *co-designability* — the
  fraction of generated designs whose backbone *and* all ligand centroids
  re-fold to RMSD < 2 Å with Chai-1.
- Was used to design **heme enzymes** for **new-to-nature carbene
  transfer** chemistry (alkene cyclopropanation, spirocyclopropanation,
  B–H and C(sp³)–H insertions) — conditioning solely on the **reactive
  intermediate** (no catalytic residues pre-specified, no template scaffold).
  Top designs exceeded the activity of previously-engineered enzymes,
  and random mutagenesis of one design gave a 4× activity gain (i.e. the
  designs are evolvable).

The code lives at `~/Repos/DISCO` and is built on top of the
[Protenix](https://github.com/bytedance/protenix) codebase.

## When to use DISCO vs. alternatives

| You want… | Use |
|----------|-----|
| **One-shot joint sequence + structure** around a ligand / nucleic acid | **DISCO** |
| Backbone-only generation, then a separate sequence-design step | `rfdiffusion` (backbone) + `proteinmpnn` / `ligandmpnn` / `solublempnn` (sequence). Or `boltzgen` for all-atom backbone + side chain |
| End-to-end binder hallucination against a **protein target** | `bindcraft` (joint AF2-based) — DISCO does **not** design protein–protein complexes |
| Refold / validate a DISCO design | `chai` (paper uses Chai-1), `boltz`, or `alphafold` |
| Rank refolded binder designs | `ipsae` ≫ ipTM ≫ iPAE; cross-reference with `protein-qc` thresholds |
| Multi-chain antibody / Fv design | Not DISCO — use ABodyBuilder / IgFold pipelines |

DISCO's headline strengths are **ligand-conditioned active-site design**,
**enzyme design from reactive intermediates**, and **nucleic-acid-binding
protein design**. If you only need a protein structure (no biomolecule
conditioning) you can still use DISCO unconditionally, but a pure
inverse-folding pipeline is usually cheaper.

## Quickstart — three steps

### 1) Install (one-time)

DISCO uses [`uv`](https://docs.astral.sh/uv/) for dependency management.

```bash
cd ~/Repos/DISCO
uv sync                 # installs torch + everything in pyproject.toml
source .venv/bin/activate
```

CUDA backend: if you need a specific CUDA wheel for torch (e.g. cu124):

```bash
uv pip uninstall torch
uv pip install torch --torch-backend=cu124
```

AMD GPUs: DeepSpeed has no AMD support. Remove `deepspeed` from
`pyproject.toml` before `uv sync`, and pass
`use_deepspeed_evo_attention=false` on every inference command.

Optional but recommended on NVIDIA Ampere+ (A100 / L40S / H100 / B100):
clone CUTLASS and point `CUTLASS_PATH` at it so DeepSpeed4Science
EvoformerAttention can compile its memory-efficient kernels on first call:

```bash
git clone https://github.com/NVIDIA/cutlass.git /path/to/cutlass
export CUTLASS_PATH=/path/to/cutlass        # add to shell profile to persist
```

If you skip CUTLASS, pass `use_deepspeed_evo_attention=false` — DISCO falls
back to a naive attention that materializes the full attention matrix
(much more GPU memory).

### 2) Write an input JSON

The JSON lists *jobs*; each job describes the entities to model. A fully
masked protein chain is a string of `-` characters of the desired length.

```json
[
  {
    "name": "length_200_aspirin",
    "sequences": [
      {
        "proteinChain": {
          "sequence": "----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------",
          "count": 1
        }
      },
      {
        "ligand": {
          "ligand": "CC(=O)Oc1ccccc1C(=O)O",
          "count": 1
        }
      }
    ]
  }
]
```

`200` `-` characters → 200-residue designed protein. Sequence-letter codes
in place of `-` fix that residue; mix to fix termini / hotspots and design
the rest.

See [references/inputs.md](references/inputs.md) for every supported entity
type and field.

### 3) Run inference

```bash
python runner/inference.py \
  experiment=designable \
  input_json_path=input_jsons/your_config.json \
  seeds=\[0,1,2,3,4\]
```

The first run will JIT-compile the pairformer kernels (CUTLASS path), which
can take several minutes before any inference step is logged. The model
weights (`DISCO.pt`) are downloaded automatically from HuggingFace
(`DISCO-Design/DISCO`) on first launch.

If a run is interrupted, **rerun the same command** — DISCO checks each
`<name>_sample_<seed>.pdb` and skips ones that already exist on disk.

## Hydra CLI — every documented flag

DISCO's runner is a [Hydra](https://hydra.cc/) entrypoint, so every config
key can be overridden inline with `key=value`. The most useful ones:

| Override | Purpose | Default |
|----------|---------|---------|
| `experiment=designable\|diverse` | Sampling-strategy preset (see below) | none |
| `input_json_path=PATH` | Input JSON describing jobs | `input_jsons/unconditional_config.json` |
| `seeds=[0,1,2,...]` | Random seeds; total samples = `len(seeds) × len(jobs)` | `[101, 102]` |
| `num_inference_seeds=N` | Shorthand: use seeds `[0..N-1]` | `null` |
| `effort=fast\|max` | Diffusion-step / recycling preset | `max` |
| `dump_dir=PATH` | Output root | `./output` |
| `load_checkpoint_path=PATH` | Custom checkpoint (else fetched from HF) | `null` |
| `use_deepspeed_evo_attention=true\|false` | DeepSpeed4Science kernels (needs `CUTLASS_PATH`) | `true` |
| `fabric.num_nodes=N` | Multi-node DDP | `1` |
| `bb_only=true\|false` | Backbone-only token mask for outputs | `true` |
| `deterministic=true\|false` | Force deterministic sampling | `true` |
| `model.N_cycle=N` | Trunk recycling cycles (per-effort: 2 / 4) | `4` |
| `sample_diffusion.N_step=N` | Diffusion sampling steps (per-effort: 100 / 200) | `200` |
| `sample_diffusion.gamma0=F` | Initial diffusion noise scale | `0.8` / `1.6` |
| `sample_diffusion.gamma_min=F` | Min gamma | `1.0` |
| `sample_diffusion.gamma_anneal=none\|linear\|cosine` | Anneal gamma over the trajectory | `none` |
| `sample_diffusion.noise_scale_lambda=F` | EDM noise multiplier λ | `1.003` / `0.1` |
| `sample_diffusion.step_scale_eta=F` | Step-size η | `1.5` |
| `sample_diffusion.integrator=euler\|heun` | Diffusion integrator (heun = 2× NFE) | `euler` |
| `sample_diffusion.noisy_guidance.enabled=true\|false` | Toggle structure+sequence noisy guidance | `true` (designable) / `false` (diverse) |
| `sample_diffusion.noisy_guidance.omega_struct=F` | Structure guidance scale | `1.5` |
| `sample_diffusion.noisy_guidance.omega_seq=F` | Sequence guidance scale | `2.0` |
| `sample_diffusion.noisy_guidance.rescale_phi=F` | Rescaling factor φ | `0.7` |
| `sample_diffusion.noisy_guidance.guidance_start_frac=F` | Fraction of trajectory at which guidance starts | `0.3` |
| `sample_diffusion.noisy_guidance.guidance_end_frac=F` | Fraction at which guidance stops | `0.8` |
| `sequence_sampling_strategy.logits_temp=F` | Decoder logits temperature | `0.8` |
| `sequence_sampling_strategy.entropy_adaptive_temp=true\|false` | Per-position entropy-adaptive T | `true` (designable) / `false` (diverse) |
| `sequence_sampling_strategy.entropy_adaptive_beta=F` | Strength of entropy-adaptive scaling | `1.0` |
| `sequence_sampling_strategy.score_type=random\|...` | Path-planning score selector | `random` |
| `sequence_sampling_strategy.sequence_noise_scheduler.power=F` | Sequence-noise schedule exponent | `1.0` / `1.5` |
| `n_seq_duplicates_per_structure=N` | Sample N sequences per generated structure | `1` |
| `inference_noise_scheduler.rho=F` | EDM σ-schedule exponent | `7.0` |
| `model.use_joint_diffusion_module=false` | Internal: joint vs disjoint diffusion module | `false` |
| `need_atom_confidence=true\|false` | Dump per-atom confidence in output | `false` |
| `output_format=unconditional_monomer_protein\|null` | PDB-style output (default) or CIF dump | `unconditional_monomer_protein` |
| `dtype=fp32\|bf16\|fp16` | Inference precision | `bf16` |

Anything visible in [`configs/`](https://github.com/DISCO-design/DISCO/tree/main/configs)
can be overridden the same way. See [references/cli.md](references/cli.md) for
the long-form table and worked examples.

## The two experiment presets

| Preset | Sequence T scaling | Noisy guidance | Best for |
|--------|--------------------|----------------|----------|
| `designable` | Entropy-adaptive (per-position) | **On** (struct + seq, ω≈1.5/2.0) | Unconditional + cases where you want refoldable samples. Paper default. |
| `diverse` | Plain (`logits_temp=0.8`, no entropy adaptive) | **Off** | Ligand / DNA / RNA conditioning — recovers the paper's headline Studio-179 numbers. Also: higher structural variety. |

Cheap-but-near-designable run: keep the other `designable` knobs and turn
guidance off — `sample_diffusion.noisy_guidance.enabled=false`. This costs
~10% in co-designability but cuts the effective batch size of each forward
pass (guidance doubles it).

## The two effort presets

| Preset | `N_step` | `N_cycle` | Speed | Quality |
|--------|---------:|----------:|------:|--------:|
| `fast` | 100 | 2 | ~4× faster | ~10% lower co-designability |
| `max`  | 200 | 4 | baseline (paper) | full quality |

Rule of thumb: **`effort=fast` only for unconditional** generation. For any
ligand- / DNA- / RNA-conditioned design use `effort=max`. To benchmark
against DISCO, always use `effort=max`.

You can also override the underlying knobs directly:
`model.N_cycle=3 sample_diffusion.N_step=150`.

## Input JSON schema — at a glance

Each file is a JSON **list** of jobs. Each job has a `name` (used as the
output filename prefix) and a `sequences` list of entities, plus an
optional `covalent_bonds` list.

Supported entity types:

| Entity | Key | Sequence alphabet | Masking with `-`? |
|--------|-----|-------------------|--------------------|
| Protein chain | `proteinChain` | 20 AAs + `X` (unknown) | **Yes** |
| DNA (single strand) | `dnaSequence` | A, T, G, C, N | **No** — fully specified only |
| RNA (single strand) | `rnaSequence` | A, U, G, C, N | **No** — fully specified only |
| Ligand | `ligand` | CCD code (`CCD_XXX[_YYY...]`), SMILES, or `FILE_<path>` to SDF / MOL / MOL2 / PDB with a 3D conformer | n/a |
| Ion / metal | `ion` | CCD code (`MG`, `ZN`, `FE`, `CA`, `NA`, ...) | n/a |

Field details and an annotated example: [references/inputs.md](references/inputs.md).

### Three ways to specify a ligand

1. **SMILES** — `"ligand": "CC(=O)Oc1ccccc1C(=O)O"`. DISCO generates a 3D
   conformer at runtime via RDKit (`EmbedMolecule`). Will assert if RDKit
   fails to embed — for those, pre-generate a conformer and use option 2.
2. **File** — `"ligand": "FILE_path/to/molecule.sdf"`. SDF, MOL, MOL2, PDB.
   Must be **3D** (2D will be rejected). Paths can be absolute or relative
   to the DISCO repo root. **XYZ is not supported** — convert with
   `obabel input.xyz -O output.sdf` first.
3. **CCD code** — `"ligand": "CCD_ATP"`. For multi-component ligands
   (glycans, etc.) join CCD codes with `_`: `"CCD_NAG_BMA_BGC"`.

### Multi-strand DNA

`dnaSequence` is **one strand**. For double-stranded DNA, add the reverse
complement as a second `dnaSequence` entity in the same job. Same applies
if you want explicit base-pairing for RNA.

### Partial sequence masking

Mix masked and fixed residues to fix specific positions (e.g. an N-terminal
signal, a known active-site motif). Example: `"MKTL----VPEG"` fixes
4 residues at each end and designs the 4 middle residues.

### Covalent bonds

Add a `covalent_bonds` field to a job to connect specific atoms across
entities (e.g. a covalently-attached ligand, a thioester intermediate).
Each entry is:

```json
{
  "left_entity": 1, "left_position": 12, "left_atom": "SG",
  "right_entity": 2, "right_position": 1, "right_atom": "C1",
  "left_copy": 1, "right_copy": 1
}
```

Entities are 1-indexed in the order they appear in `sequences`. Atom
names are CCD-standard. For SMILES ligands, you can use the SMILES atom
map number instead of `"left_atom": "C1"`.

## Outputs — the file layout

```
dump_dir/
├── pdbs/
│   ├── <name>_sample_<seed>.pdb              # generated structure (one per sample)
│   └── <name>_sample_<seed>_ligands.txt      # ligand SMILES — only if ligands present
├── sequences/
│   └── <name>_sample_<seed>.txt              # FASTA-like; >cogen_seq 0, then sequence,
│                                             #   then optional dna_sequence / rna_sequence
│                                             #   / ligand_smiles lines
└── ERR/
    └── <name>.txt                            # only for failed samples (with traceback)
```

By default DISCO writes **PDB** files (`output_format=unconditional_monomer_protein`).
Set `output_format=null` to instead write **CIF** files (and richer
per-residue metadata) via the dumper.

If `n_seq_duplicates_per_structure > 1`, the sequence file contains
multiple `>cogen_seq i` records for the same backbone — useful for
generating a sequence ensemble per structure.

If `need_atom_confidence=true`, the dumper also writes per-atom confidence
data alongside summary scores.

See [references/outputs.md](references/outputs.md) for full schemas.

## Evaluation — co-designability

The paper's headline metric is **co-designability**: a design counts if,
after refolding the generated sequence with **Chai-1**, the protein
backbone and the centroids of all conditioning ligands are within
**< 2 Å RMSD** of the DISCO design. Studio-179 reports the fraction of
generated designs that are *diverse* **and** co-designable.

To replicate the metric for your own runs, use the `chai` (or `boltz` /
`alphafold`) skill to refold each `sequences/*.txt` with the original
ligand / DNA / RNA conditioning, align to the corresponding
`pdbs/*.pdb`, and threshold on backbone + ligand-centroid RMSD. See
[references/evaluation.md](references/evaluation.md) for a worked recipe.

## The Studio-179 benchmark

DISCO ships the SDF files for 179 ligands (170 single + 9 multi-ligand)
under `studio-179/priority_{0,1,2,3}/`. The benchmark covers:

- rigid molecules (e.g. tetrachlorodibenzodioxin),
- large or flexible molecules (e.g. CoQ10, 50-heavy-atom isoprenoid),
- metals and metalloclusters (e.g. [4Fe-4S], Fe / Co / Hg / Pb "ideal"
  metal-centre placeholders),
- organometallic catalysts (Ru(bpy), Ir-biotin, Ir-piano), and
- the reactive carbene intermediate used for the heme-enzyme experiment
  (in `priority_0/`).

Pre-split jobs for parallel runs are in
`input_jsons/all_priorities_ligands_split_{0..3}.json`. Each split runs
every job at three lengths (150, 200, 250) — the canonical benchmark
configuration.

```bash
python runner/inference.py \
  experiment=diverse \
  effort=max \
  input_json_path=input_jsons/all_priorities_ligands_split_0.json \
  seeds=\[$(seq -s "," 0 4)\]
```

For a **single ligand**, mirror `input_jsons/heme_b.json`: three jobs at
lengths 150 / 200 / 250 each referencing the same SDF. The example file
under [examples/single_ligand_studio179.json](examples/single_ligand_studio179.json)
is ready to adapt.

See [references/studio-179.md](references/studio-179.md) for tiers,
priority structure, and per-tier expected pass rates.

## Choosing the right reference doc

| You want to… | Read |
|--------------|------|
| Install (`uv`, CUTLASS, AMD path, HF weights, custom checkpoints) | [references/installation.md](references/installation.md) |
| See every Hydra override with examples | [references/cli.md](references/cli.md) |
| Author an input JSON for protein / ligand / ion / DNA / RNA / covalent | [references/inputs.md](references/inputs.md) |
| Pick the right preset for your use case (designable vs diverse, fast vs max) | [references/presets.md](references/presets.md) |
| Read PDB / sequences / ERR / `_ligands.txt` outputs | [references/outputs.md](references/outputs.md) |
| Reproduce Studio-179 or benchmark a custom ligand against it | [references/studio-179.md](references/studio-179.md) |
| Compute co-designability with Chai-1 / Boltz / AF2 | [references/evaluation.md](references/evaluation.md) |
| Design a heme enzyme (or any reactive-intermediate-conditioned design) | [references/enzyme-design.md](references/enzyme-design.md) |
| Design a DNA- or RNA-binding protein | [references/nucleic-acid.md](references/nucleic-acid.md) |
| Run unconditional length sweeps for backbones | [references/unconditional.md](references/unconditional.md) |
| Run partial-mask jobs (fix hotspots, design the rest) | [references/partial-mask.md](references/partial-mask.md) |
| Multi-GPU / multi-node / large-scale screening | [references/scaling.md](references/scaling.md) |
| Diagnose JIT-compile, CUTLASS, OOM, MSA, or shape-mismatch failures | [references/troubleshooting.md](references/troubleshooting.md) |
| What DISCO **cannot** do (and what's planned) | [references/limitations.md](references/limitations.md) |

## Quick decision tree

- **Just want a backbone + sequence of a given length, no target** →
  `experiment=designable`, `input_jsons/unconditional_config.json`,
  `effort=fast` is fine.
- **Want a binder around a small molecule (SMILES in hand)** →
  put 1× `proteinChain` (~150–250 `-`s) + 1× `ligand` with the SMILES
  in a job. `experiment=diverse`, `effort=max`. Run multiple lengths.
- **Want a binder around a metal cofactor** → use `CCD_FE` (or whatever
  CCD) as an `ion`, or the appropriate `_ideal.sdf` from `studio-179/`
  as a `ligand` with `FILE_`. `experiment=diverse`, `effort=max`.
- **Want a heme enzyme around a transition-state intermediate** →
  see [references/enzyme-design.md](references/enzyme-design.md). Pass
  the TS SDF as the only ligand; don't pre-specify catalytic residues.
- **Want an RNA-binding protein for an aptamer sequence** → 1× masked
  protein chain + 1× `rnaSequence` (no `-` allowed). Lengths 50–80
  recovered paper results.
- **Want a TF-like dsDNA binder** → 1× protein chain + 1× `dnaSequence`
  (single strand) + 1× `dnaSequence` (reverse complement). `experiment=diverse`,
  `effort=max`.
- **Want to fix the N- and C-terminal motifs but redesign the loop** →
  partial mask the protein chain: `"MKTL----VPEG"`.
- **Want many seeds in parallel across GPUs** → `fabric.num_nodes>1` and
  launch with `srun` / `torchrun`; DDP shards the dataloader automatically.
- **Want a sequence ensemble for the same backbone** →
  `n_seq_duplicates_per_structure=N`. Output sequences file gets `N`
  `>cogen_seq i` records.

## Hard rules / gotchas

1. **One protein chain per job.** DISCO is single-chain-only — it inherits
   this from DPLM (the LM that replaces the MSA module). >1
   `proteinChain` per job will raise. Protein–ligand, protein–DNA,
   protein–RNA, and protein–multi-ligand are all fine.
2. **No motif scaffolding (yet).** Fixing a structural motif while
   designing the surrounding scaffold isn't supported — only
   sequence-level masking is. The maintainers list this as planned.
3. **DNA and RNA must be fully specified.** Masking nucleic acid
   positions with `-` is not supported. Provide complete sequences.
4. **Double-stranded DNA is two `dnaSequence` entries.** DISCO does not
   auto-pair strands; you must add the reverse complement explicitly.
5. **Ligand files must have a 3D conformer.** SDF / MOL / MOL2 / PDB with
   2D coordinates will be rejected. XYZ is not supported — convert first.
6. **SMILES that RDKit can't embed will hard-assert.** Workaround:
   pre-generate a conformer with RDKit / Open Babel and pass it as `FILE_`.
7. **`effort=fast` is unconditional-only.** For ligand / DNA / RNA
   conditioning, use `effort=max` — otherwise co-designability drops
   sharply.
8. **`infer_batch_size=1` is the only tested setting.** The runner makes
   assumptions about this elsewhere. Don't override.
9. **`-` is mask only inside `proteinChain`.** It's a residue letter, not
   a generic token. In other entity types it's not interpreted.
10. **DeepSpeed EvoformerAttention requires Ampere+ NVIDIA and CUTLASS.**
    On AMD or older NVIDIA, run with `use_deepspeed_evo_attention=false`
    — slower / much more memory, but works.
11. **Run-resume is name-keyed.** DISCO skips a sample iff
    `<dump_dir>/<name>_sample_<seed>.pdb` exists. Renaming the job
    re-runs it; changing seeds re-runs only the new seeds.
12. **First-launch JIT compile.** Pairformer kernels compile lazily —
    nothing is broken if the first 5-10 minutes are silent.
13. **Sequence outputs are FASTA-ish, not strict FASTA.** Each file mixes
    `>cogen_seq i` records with `dna_sequence` / `rna_sequence` /
    `ligand_smiles` annotation lines. Parse line-prefix, not BioPython.
14. **There is no built-in refolder.** Co-designability requires an
    external structure predictor — use Chai-1 (paper default) via the
    `chai` skill.
15. **Single-component CCD codes can be entered as `ion` or `ligand`.**
    Use `ion` for monatomic metals (`NA`, `MG`, `ZN`, `FE`, `CA`) — the
    parser routes it to the same builder but tags it as an ion.
16. **No protein-protein complexes.** This is the model's biggest gap.
    Use `bindcraft` (joint AF2 hallucination) for protein-target binders.

## Installing this skill

```bash
# Symlink (recommended — picks up edits live)
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/disco

# Or copy:
cp -R . ~/.claude/skills/disco
```

After that, an agent invokes it via `Skill(skill="disco")`.

## Citation

```bibtex
@Article{disco2026,
  title   = {General Multimodal Protein Design Enables DNA-Encoding of Chemistry},
  author  = {Jarrid Rector-Brooks and Théophile Lambert and Marta Skreta and
             Daniel Roth and Yueming Long and Zi-Qi Li and Xi Zhang and
             Miruna Cretu and Francesca-Zhoufan Li and Tanvi Ganapathy and
             Emily Jin and Avishek Joey Bose and Jason Yang and
             Kirill Neklyudov and Yoshua Bengio and Alexander Tong and
             Frances H. Arnold and Cheng-Hao Liu},
  year    = {2026},
  eprint  = {2604.05181},
  archivePrefix = {arXiv},
  primaryClass  = {cs.LG},
  url     = {https://arxiv.org/abs/2604.05181}
}
```
