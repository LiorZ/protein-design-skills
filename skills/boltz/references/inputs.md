# YAML input schema

Boltz accepts a YAML file (preferred) or FASTA file (deprecated) per complex. This doc covers the YAML schema in full. The FASTA format is described at the bottom for completeness.

## Top-level structure

```yaml
version: 1                    # optional, defaults to 1; only 1 is valid
sequences:                    # required: list of polymer / ligand entities
  - protein: { ... }
  - rna:     { ... }
  - dna:     { ... }
  - ligand:  { ... }
constraints:                  # optional
  - bond:    { ... }
  - pocket:  { ... }
  - contact: { ... }          # Boltz-2 only
templates:                    # optional, Boltz-2 only
  - cif: path/to/template.cif
  - pdb: path/to/template.pdb
properties:                   # optional, Boltz-2 only
  - affinity:
      binder: <ligand_chain_id>
```

Any unknown top-level key is ignored, but unknown keys *inside* a section will raise.

## `sequences:`

A list, each entry has **exactly one** of `protein`, `rna`, `dna`, `ligand`.

### `protein:`

```yaml
- protein:
    id: A                       # str, or [A, B, ...] for identical copies
    sequence: MVTPEGNVSLVD...   # 1-letter amino acids
    msa: ./path/to/seq.a3m      # see msas.md; omit only with --use_msa_server
    modifications:              # optional
      - position: 5             # 1-indexed
        ccd: MSE                # CCD code (e.g. MSE = selenomethionine)
    cyclic: true                # optional; head-to-tail cyclic peptide
```

Notes:

- `id` is the chain ID used everywhere else (constraints, properties). If you give a list, all members share the same `sequence` / `msa` / `modifications` and are treated as symmetric copies.
- `msa` accepts: a path to an `.a3m` (single chain), a path to a CSV with `sequence,key` columns (paired multimer MSAs — see [msas.md](msas.md)), or the literal string `empty` (single-sequence, *not recommended*). If omitted entirely, the `--use_msa_server` flag must be set and the MSA is fetched from ColabFold.
- `modifications`: each entry is a `{position: int, ccd: str}` pair. `position` is 1-indexed into `sequence`. `ccd` must resolve in the CCD dictionary; only CCD codes are supported here (not SMILES). The original 1-letter at `position` is replaced.
- `cyclic: true` adds a head-to-tail peptide bond between the first and last residue. Cyclic period in the parsed structure equals the chain length.

### `rna:` / `dna:`

```yaml
- rna:
    id: R
    sequence: GCAUAGC           # ACGU
- dna:
    id: D
    sequence: ATCGATCG          # ACGT
```

Both accept `modifications` (e.g. modified nucleotides via CCD) and `cyclic: true`. They do **not** accept `msa:` — nucleic acids are predicted without sequence-based co-evolution.

### `ligand:`

```yaml
- ligand:
    id: L
    smiles: 'CC(=O)O'           # mutually exclusive with ccd
- ligand:
    id: M
    ccd: ATP                    # mutually exclusive with smiles
```

Rules:

- Exactly **one** of `smiles` or `ccd` per ligand entry.
- For `smiles`, prefer a canonical SMILES; isomeric SMILES with stereo `@` markers is preserved.
- For `ccd`, the 3-letter (or longer) CCD code must be known in the dictionary (`mols/` for Boltz-2, `ccd.pkl` for Boltz-1). Common ones: `ATP`, `ADP`, `HEM`, `NAG`, `SAH`, `NAD`, etc.
- `id: [L, M]` declares multiple identical ligand copies (e.g. two ATPs in a homodimer).
- Ligand chains are tokenised **per heavy atom**, so a 100-atom ligand consumes ~100 tokens.

## `constraints:`

All constraints are 1-indexed. See [constraints.md](constraints.md) for full details and examples.

### `bond:` — explicit covalent bond between two atoms

```yaml
- bond:
    atom1: [A, 1, CA]
    atom2: [A, 2, N]
```

Each entry is `[CHAIN_ID, RES_IDX (1-indexed), ATOM_NAME]`. Atom names follow CCD conventions (case-sensitive). For ligands, `RES_IDX` is always `1` (a ligand is one residue).

Supported only between **CCD-defined** entities (CCD ligands, canonical residues, CCD-modified residues). SMILES ligands cannot be the target of a `bond` constraint.

### `pocket:` — bias a binder toward specific pocket residues

```yaml
- pocket:
    binder: B                   # chain ID of the binder
    contacts:                   # list of [chain, residue_or_atom] pairs
      - [A, 829]
      - [A, 138]
      - [A, ND1]                # for ligand chains use atom name instead of index
    max_distance: 6             # Å, 4–20; default 6; Boltz-1 only allows 6
    force: false                # if true, apply a steering potential
```

The binder can be a protein, DNA, RNA, or ligand chain. In **Boltz-1**, only one `pocket` constraint per YAML and `max_distance` must equal 6. **Boltz-2** removes both limits.

### `contact:` — bias a single token-token contact (Boltz-2 only)

```yaml
- contact:
    token1: [A, 829]            # [chain, residue_idx] or [chain, atom_name] for ligands
    token2: [B, 1]
    max_distance: 6             # Å, default 6
    force: false
```

Same coordinate convention as `pocket.contacts`.

## `templates:` (Boltz-2 only)

```yaml
templates:
  - cif: ./templates/4xyz.cif                    # all protein chains get templated
  - cif: ./templates/4xyz.cif
    chain_id: A                                  # restrict to one of your chains
  - cif: ./templates/4xyz.cif
    chain_id: [A, B]
    template_id: [X, Y]                          # explicit mapping; lengths must match
  - pdb: ./templates/legacy.pdb
    chain_id: [A, B]
    template_id: [A1, A2]                        # PDB chains get incremental ids A1, A2, B1, ...
  - cif: ./templates/4xyz.cif
    force: true
    threshold: 2.0                               # Å of allowed backbone deviation
```

If `chain_id` is omitted, Boltz applies the template to all protein chains and chooses the best matching template chain by global alignment. If `template_id` is omitted but `chain_id` is given, the same search runs only over the listed chains.

`force: true` adds a backbone-RMSD potential during diffusion; you must then also provide `threshold` (Å). Without `force`, the template biases the trunk but does not constrain the final coordinates.

Only protein chains can be templated; DNA / RNA / ligand chains in the template file are ignored.

## `properties:` (Boltz-2 only)

```yaml
properties:
  - affinity:
      binder: L                  # ligand chain id, must reference a ligand entry
```

Rules:

- Only one affinity ligand per YAML.
- `binder` must be a `ligand`, not a polymer.
- The ligand must be ≤ 128 heavy atoms (RDKit-stripped of H); training cap was 56, so values for 56–128 atoms come with a `WARNING` and are unreliable.
- Affinity vs DNA/RNA/cofactor "targets" runs but is **not validated** — only protein targets are reliable.

See [affinity.md](affinity.md) for output interpretation.

## A complete example

```yaml
version: 1
sequences:
  - protein:
      id: [A, B]                # homodimer
      sequence: MVTPEGNVSLVDESLLVGVTDEDRAVRSAHQFYERLIGLW...
      msa: ./examples/msa/seq1.a3m
      modifications:
        - position: 1
          ccd: MSE
  - ligand:
      id: [C, D]
      ccd: SAH
  - ligand:
      id: E
      smiles: 'N[C@@H](Cc1ccc(O)cc1)C(=O)O'
constraints:
  - bond:
      atom1: [A, 1, SD]         # MSE selenium
      atom2: [C, 1, S]          # SAH sulfur (illustrative)
  - pocket:
      binder: E
      contacts:
        - [A, 138]
        - [A, 142]
      max_distance: 6
templates:
  - cif: ./templates/2abc.cif
    chain_id: [A, B]
properties:
  - affinity:
      binder: E
```

## FASTA (deprecated)

```
>CHAIN_ID|ENTITY_TYPE|MSA_PATH
SEQUENCE
```

`ENTITY_TYPE` ∈ `protein`, `dna`, `rna`, `smiles`, `ccd`. `MSA_PATH` is only meaningful for `protein` (use `empty` for single-sequence mode). Modifications, cyclic, bonds, pockets, contacts, templates, and affinity **cannot be expressed in FASTA** — convert to YAML for any of these features. Example:

```
>A|protein|./examples/msa/seq1.a3m
MVTPEGNVSLVD...
>B|protein|./examples/msa/seq1.a3m
MVTPEGNVSLVD...
>C|ccd
SAH
>D|smiles
N[C@@H](Cc1ccc(O)cc1)C(=O)O
```

## Validation rules summary

The parser will raise `ValueError` on:

- `version != 1`
- `sequences:` entry whose top key is not `protein` / `rna` / `dna` / `ligand`
- `ligand` with neither or both of `smiles` / `ccd`
- `properties` set when `--model boltz1`
- `properties.affinity.binder` that's a list, not a string, or not a ligand chain
- More than one affinity ligand
- Affinity ligand > 128 heavy atoms (warning at > 56)
- `templates:` with `--model boltz1`
- `contact:` constraint with `--model boltz1`
- More than one `pocket:` with `--model boltz1`, or `max_distance != 6` with `--model boltz1`
- A `bond:` referencing an atom that isn't in the parsed atom index map (typo in chain id, wrong residue index, or unknown atom name)
- A template `chain_id` that isn't a protein chain in the YAML, or a `template_id` that isn't a protein chain in the template file
- Mismatched lengths between `chain_id` and `template_id` lists
- `force: true` on a template without a `threshold`
