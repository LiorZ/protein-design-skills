# Input JSON schema

DISCO's input format closely follows the [AlphaFold Server](https://alphafoldserver.com/)
JSON format, with DISCO-specific extensions for masking, file-based
ligands, and covalent bonds. The parser lives at
`disco/data/json_parser.py`.

## Top-level structure

Each file is a **list of jobs**. Each job has:

```json
{
  "name": "my_design",        // used as the output filename prefix
  "sequences": [ ... ],       // list of entity dicts
  "covalent_bonds": []        // optional, default []
}
```

A single file can contain any number of jobs. They are processed
independently and dispatched across DDP ranks when distributed.

## Entity types

Every element of `sequences` is a one-key dict; the key selects the
entity type, and the value is its config.

### `proteinChain`

```json
{
  "proteinChain": {
    "sequence": "MKTL----VPEG",
    "count": 1
  }
}
```

| Field | Type | Notes |
|-------|------|-------|
| `sequence` | string | 20 standard one-letter codes (`A R N D C Q E G H I L K M F P S T W Y V`), `X` for unknown, **`-` for masked (will be generated)**. |
| `count` | int | Number of copies. Use `1` unless you want symmetric repeats. **DISCO requires exactly one protein chain across the entire job** (see Limitations). |

Sequence length = `len(sequence)`. To set the designed protein to N
residues, use a string of `N` hyphens.

### `dnaSequence` (single strand)

```json
{
  "dnaSequence": {
    "sequence": "GATTACAGATC",
    "count": 1
  }
}
```

| Field | Type | Notes |
|-------|------|-------|
| `sequence` | string | Alphabet: `A T G C N` (no `U`). **No masking** — provide the full sequence. |
| `count` | int | Number of copies. |

For **double-stranded** DNA, add the reverse complement as a second
`dnaSequence` in the same job. DISCO will *not* auto-pair strands.

### `rnaSequence` (single strand)

```json
{
  "rnaSequence": {
    "sequence": "GGCUAGCCAUUUGAC",
    "count": 1
  }
}
```

Same shape as `dnaSequence`. Alphabet: `A U G C N`. No masking.

### `ligand`

Three ways to specify the molecule:

**(a) SMILES** — `ligand` is a SMILES string (no prefix):

```json
{
  "ligand": {
    "ligand": "CC(=O)Oc1ccccc1C(=O)O",
    "count": 1
  }
}
```

DISCO calls `RDKit.AllChem.EmbedMolecule()` to generate a 3D conformer.
If embedding fails, the runner **asserts** with
`Conformer generation failed for input SMILES: ...`. Workaround:
pre-generate a conformer with RDKit / Open Babel and pass it as option (b).

**(b) Molecular file** — `ligand` is `FILE_<path>` to an SDF / MOL / MOL2 / PDB
with a 3D conformer:

```json
{
  "ligand": {
    "ligand": "FILE_studio-179/priority_1/heme_b_final_0.sdf",
    "count": 1
  }
}
```

- Path is absolute, or relative to the DISCO repo root (the runner
  resolves it via `os.path.join(DISCO_ROOT, lig_file_path)`).
- 2D structures are rejected — your SDF must have non-trivial Z
  coordinates.
- **XYZ is not supported.** Convert first:
  ```bash
  obabel input.xyz -O output.sdf
  ```
- Up to **99 SMILES-style ligands** per file (the parser packs them into
  residue names `l01`–`l99`). CCD-style ligands aren't capped.

**(c) CCD code** — `ligand` is `CCD_<code>` (or `CCD_X_Y_Z` for
multi-component):

```json
{
  "ligand": {
    "ligand": "CCD_ATP",
    "count": 1
  }
}
```

For multi-component ligands like glycans, concatenate codes with `_`:

```json
{
  "ligand": {
    "ligand": "CCD_NAG_BMA_BGC",
    "count": 1
  }
}
```

The parser builds the atom array by concatenating each CCD residue.

### `ion`

```json
{
  "ion": {
    "ion": "MG",
    "count": 3
  }
}
```

- Identifier is a **CCD code** for the monatomic ion (e.g. `MG`, `ZN`,
  `FE`, `CA`, `NA`, `K`, `MN`, `CU`).
- `count` controls the number of independent copies placed in the
  structure.
- Internally routed through the same builder as `ligand` (CCD branch),
  just tagged as an ion entity.

You can equivalently say `{"ligand": {"ligand": "CCD_MG"}}` — both work.

## `covalent_bonds`

Optional. Connect specific atoms across entities. Useful for:

- Covalently-attached ligands (e.g. acyl-enzyme intermediates).
- Cofactor-residue covalent links (heme-Cys axial ligation,
  PLP-Lys Schiff base, etc.).
- Disulfide-style links between residues and a ligand.

Each entry:

```json
{
  "left_entity":   1,    "left_position":  12, "left_atom":  "SG",   "left_copy":  1,
  "right_entity":  2,    "right_position": 1,  "right_atom": "C1",   "right_copy": 1
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `left_entity` / `right_entity` | int (1-indexed) | Index into `sequences` list. |
| `left_position` / `right_position` | int (1-indexed) | Residue / ligand-residue index in that entity. |
| `left_atom` / `right_atom` | str or int | CCD-standard atom name (e.g. `SG`, `NE2`, `C1`). For SMILES ligands you can pass the **SMILES atom map number** as an int and the parser will look it up via `atom_map_to_atom_name`. |
| `left_copy` / `right_copy` | int | Which copy of the entity (1-indexed). Defaults to bonding all copies pairwise. |

The two entities in a bond must have **equal `count`** so the parser can
zip the per-copy atom pairs.

After resolving the bond, DISCO removes leaving atoms automatically.

### Example: heme-Cys axial ligation

```json
{
  "name": "p450_like",
  "sequences": [
    {"proteinChain": {"sequence": "M-------------------------C-----------------------------", "count": 1}},
    {"ligand":       {"ligand":   "FILE_studio-179/priority_1/heme_b_final_0.sdf", "count": 1}}
  ],
  "covalent_bonds": [
    {
      "left_entity":  1, "left_position":  28, "left_atom":  "SG",
      "right_entity": 2, "right_position": 1,  "right_atom": "FE"
    }
  ]
}
```

(The Cys is at position 28 in this masked sequence; `FE` is the iron
atom of heme.)

## Masking conventions

`-` (hyphen) is the **mask token** inside `proteinChain.sequence`. Every
masked position is a degree of freedom for DISCO to design.

| Pattern | Meaning |
|---------|---------|
| `"--------"` (all `-`) | Fully unconditional — DISCO generates every residue. |
| `"MKTL----VPEG"` | Fixed termini (`MKTL` and `VPEG`), middle 4 are designed. |
| `"AAAAA----AAAAA"` | Fixed flanking poly-A, design 4 in the middle. |
| `"X--------"` | The leading `X` is a wildcard unknown residue (will be filled in by the model as if masked — but flagged as unknown rather than mask). |

Mixing `-` and explicit residues is the canonical way to do **partial
sequence redesign**.

Masking is **not** supported in `dnaSequence` or `rnaSequence`. DNA and
RNA strands must be fully specified.

## Complete worked examples

### Unconditional, single length

```json
[
  {
    "name": "length_150",
    "sequences": [
      {"proteinChain": {"sequence": "------------------------------------------------------------------------------------------------------------------------------------------------------", "count": 1}}
    ]
  }
]
```

### Ligand-conditioned, SMILES

```json
[
  {
    "name": "warfarin_200",
    "sequences": [
      {"proteinChain": {"sequence": "--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------", "count": 1}},
      {"ligand":       {"ligand":   "CC(=O)CC(c1ccccc1)c2c(O)c3ccccc3oc2=O", "count": 1}}
    ]
  }
]
```

### Ligand + ion + covalent bond

```json
[
  {
    "name": "fe4s4_cluster_binder",
    "sequences": [
      {"proteinChain": {"sequence": "--C--C-------C--C-----------------------------------------------------------------------------", "count": 1}},
      {"ion":          {"ion": "FE", "count": 4}},
      {"ion":          {"ion": "SF4", "count": 1}}
    ]
  }
]
```

### Double-stranded DNA binder

```json
[
  {
    "name": "tf_like_binder",
    "sequences": [
      {"proteinChain": {"sequence": "-----------------------------------------------------------------------------------------------------------------------------------------------", "count": 1}},
      {"dnaSequence":  {"sequence": "TGCAGTACGTTAGC", "count": 1}},
      {"dnaSequence":  {"sequence": "GCTAACGTACTGCA", "count": 1}}
    ]
  }
]
```

(The two `dnaSequence` strands are reverse complements.)

### Multi-job length sweep

```json
[
  {"name": "len_100", "sequences": [{"proteinChain": {"sequence": "----------------------------------------------------------------------------------------------------", "count": 1}}]},
  {"name": "len_150", "sequences": [{"proteinChain": {"sequence": "------------------------------------------------------------------------------------------------------------------------------------------------------", "count": 1}}]},
  {"name": "len_200", "sequences": [{"proteinChain": {"sequence": "--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------", "count": 1}}]}
]
```

## Hard rules

1. **Exactly one `proteinChain` per job.** Multi-chain protein complexes
   are not supported by the DPLM-based architecture.
2. **DNA / RNA fully specified**, no `-`.
3. **Ligand files must have 3D coordinates.** No 2D, no XYZ.
4. **Covalent-bond endpoints must have equal `count`** in their
   respective entities.
5. **Entity indices in `covalent_bonds` are 1-indexed.**
6. **Atom names are CCD-standard, case-sensitive** (`SG` not `sg`).
7. **`FILE_` paths** resolve relative to the DISCO repo root if not
   absolute.
8. **CCD multi-component ligands** must use `_` separator (`CCD_NAG_BMA`).
9. **Up to 99 SMILES ligands per JSON file** (across all jobs).
10. **`count > 1` on a `proteinChain` is disallowed** (collapses to
    multi-chain).
