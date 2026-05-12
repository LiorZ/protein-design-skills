# Limitations

What DISCO cannot do today (and what's planned).

## Hard limitations

### 1. No protein–protein complex design

DISCO uses **DPLM-650M** as a language model in place of an MSA / pair
module. DPLM was trained exclusively on **single-chain** proteins, so
the model predicts multi-chain proteins poorly. The runner enforces
this:

> Inputs containing more than one protein chain will raise an error.

**Implication:** DISCO **cannot** design:
- Protein–protein binders (e.g. PD-L1 binders, target-of-interest
  binders for a protein target).
- Antibody–antigen complexes.
- Homo-oligomers.
- Heterodimers.

What it **can** design (single protein chain + non-protein partners):
- Protein–small-molecule (binder for a ligand).
- Protein–DNA, protein–RNA (binder for a nucleic acid).
- Protein–multi-ligand (active site with multiple cofactors).
- Protein–ion / protein–metal cluster (metalloproteins).

For protein-target binders, use `bindcraft` (joint AF2 hallucination)
or `rfdiffusion` + `proteinmpnn` instead.

### 2. No motif scaffolding

DISCO does **not** support fixing a 3D structural motif (a backbone
segment with a target geometry) and designing the surrounding scaffold.

What you **can** do:
- Fix individual residues at specified *sequence* positions
  (partial-mask). See [partial-mask.md](partial-mask.md).

What you **can't** do (yet):
- Provide a target backbone PDB and ask DISCO to scaffold it.
- Provide a coordinate-level constraint on a sub-fragment.

For motif-scaffolding tasks, use `rfdiffusion` (`contig_map` syntax) or
`genie3`.

The DISCO maintainers list motif scaffolding as planned.

### 3. DNA / RNA must be fully specified

The `dnaSequence` and `rnaSequence` parsers reject `-` (mask) in
nucleic-acid positions. You can condition on a fixed sequence; you
cannot ask DISCO to design a nucleic-acid sequence.

### 4. dsDNA strands aren't auto-paired

Adding one `dnaSequence` produces a single strand. For dsDNA, you must
add the reverse complement as a second `dnaSequence` entity yourself.
There's no convenience flag.

### 5. Up to 99 SMILES ligands per input file

The parser packs SMILES-style ligands into residue names `l01`–`l99`
to avoid collisions with CCD codes. This is a hard cap. Split your
input file if you exceed it (CCD-style ligands don't count toward this
cap).

### 6. Ligand files need 3D coordinates

SDF / MOL / MOL2 / PDB must contain a 3D conformer. 2D will be
rejected. XYZ is **not** a supported format — convert to SDF first
(`obabel input.xyz -O output.sdf`).

### 7. SMILES that RDKit can't 3D-embed will hard-assert

The parser raises on conformer-generation failure. Workaround:
pre-generate a conformer externally and pass as `FILE_`.

### 8. `effort=fast` is unconditional-only

For ligand / DNA / RNA conditioning, `fast` produces sharply worse
co-designability. The paper explicitly warns against `fast` for
conditional generation.

### 9. `infer_batch_size > 1` is untested

The runner assumes batch size 1 in several places (e.g. the ligand
SMILES extraction). Don't change it.

### 10. No built-in refolder / scorer

DISCO produces structures and sequences but **does not** compute
co-designability or any other quality score internally. You bring your
own refolder (Chai-1 / Boltz / AF2). See [evaluation.md](evaluation.md).

### 11. `seq_tnsr_to_str` uses an internal residue-index table

The mapping `PRO_RES_IDX_TO_RESNAME_ONE` from `disco/data/constants.py`
is what converts decoder predictions to one-letter sequences. If you
write custom downstream tooling, use the same table to stay consistent.

### 12. Atom names are CCD-standard

`covalent_bonds` references use CCD-standard atom names (e.g. `SG`,
`NE2`, `OD1`). Custom atom names from a third-party SDF won't match —
check the CCD entry for your ligand or use SMILES atom-map numbers
instead.

### 13. NVIDIA Ampere+ for full speed

DeepSpeed4Science EvoformerAttention needs Ampere or newer
(A100 / L40S / H100 / H200 / B100 / B200) and CUTLASS on disk. Older
NVIDIA cards run with the naive attention fallback — much more memory,
slower. AMD GPUs always use the naive path.

### 14. Output PDB chain IDs are auto-assigned

You don't control chain ID labels in the output PDB; the dumper assigns
them in a fixed order based on entity ordering. If your downstream
pipeline expects specific chain IDs, post-process.

### 15. No covalent-bond on partial-mask edge cases

If a `covalent_bonds` entry references a position that's covered by
masking and ends up generated as a non-matching residue type, the bond
will still resolve (DISCO uses CCD atom names by residue type), but the
biology won't make sense — e.g. a `SG` bond on a residue that gets
generated as Ala. Fix the residue identity with partial masking on the
relevant position to keep the bond meaningful.

## Soft limitations / caveats

- **Long proteins drift toward lower co-designability.** Length 300+
  needs many more seeds for the same hit rate.
- **Sequence diversity drops at low `logits_temp`.** Defaults are 0.8;
  raise to 1.0–1.2 for more divergent draws (at some loss of
  designability).
- **Co-designability ≠ activity.** Structural validation alone does
  not predict catalytic / binding activity. Wet-lab follow-up is
  required.
- **No CSV / W&B logging by default in inference.** Roll your own
  summary if you need one.
- **No template conditioning.** Unlike Boltz-2 / Chai-1 / AF3, DISCO
  doesn't accept a template PDB as a generation guide.

## Planned (per README, "Coming Soon")

- **Feynman-Kac correctors.** Better sampling via Feynman-Kac
  reweighting (algorithm exists in the paper, code release pending).
- **Training code.** Code for training DISCO from scratch.

When these land, this skill will need updates; for now they're not
available.

## When DISCO is the wrong tool

| You want… | Use instead |
|----------|-------------|
| Protein–protein binder design | `bindcraft` (joint AF2 hallucination); `rfdiffusion`+`proteinmpnn` |
| Antibody design | ABodyBuilder / IgFold / BindCraft antibody mode |
| Motif scaffolding from a 3D motif PDB | `rfdiffusion`, `genie3` |
| Sequence-only inverse folding | `proteinmpnn`, `ligandmpnn`, `solublempnn` |
| Affinity prediction for a known complex | `boltz` (Boltz-2 affinity head) |
| Cyclic peptides | Boltz / Chai-1 with `cyclic` flag |
| Membrane proteins with explicit membrane | Not really any tool yet; consider mdMPNN |

## When DISCO is the **right** tool

- **Ligand-conditioned binder / active-site design** — joint co-design
  is the model's headline strength.
- **De novo enzyme design from a reactive intermediate** — see
  [enzyme-design.md](enzyme-design.md).
- **Nucleic-acid-binding protein design** — handles DNA / RNA
  conditioning natively.
- **Unconditional library generation** — fast and high-quality at
  moderate lengths.
- **Studio-179 reproducibility / benchmark comparison** — DISCO is the
  benchmark's introducer and the model to beat.
