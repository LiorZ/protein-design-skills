# Input JSON examples

Copy-paste starting points. Input is always a **list** of jobs. Full schema in
`../references/inputs.md`. The Protenix repo's `examples/` has more (see the
table at the bottom of `inputs.md`).

## 1. Single protein (monomer)

```json
[
  {
    "name": "my_protein",
    "sequences": [
      { "proteinChain": { "sequence": "MAQGSHQIDFQVLHDLRQKFPEVPEV", "count": 1 } }
    ]
  }
]
```

With `--use_msa true` (default) and no MSA paths, an MMseqs2 search runs
automatically.

## 2. Homodimer / oligomer

```json
[
  {
    "name": "homodimer",
    "sequences": [
      { "proteinChain": { "sequence": "MASWSHPQFEK...ATT", "count": 2 } }
    ]
  }
]
```

`count: 2` makes two identical chains. Add `"id": ["A", "B"]` to fix chain IDs.

## 3. Protein + ligand (CCD, SMILES, or file) + ion

```json
[
  {
    "name": "kinase_atp_mg",
    "sequences": [
      { "proteinChain": { "sequence": "MGSSHHHH...PEP", "count": 1 } },
      { "ligand": { "ligand": "CCD_ATP", "count": 1 } },
      { "ion":    { "ion": "MG", "count": 2 } }
    ]
  }
]
```

Ligand alternatives (any one form):

```json
{ "ligand": { "ligand": "CCD_6OI", "count": 1 } }
{ "ligand": { "ligand": "CC(=O)Oc1ccccc1C(=O)O", "count": 1 } }
{ "ligand": { "ligand": "FILE_/abs/path/ligand.sdf", "count": 1 } }
{ "ligand": { "ligand": "CCD_NAG_BMA_BGC", "count": 1 } }
```

Note ions use a bare CCD code (`"MG"`), ligands prefix `CCD_`. The `FILE_` form
needs a 3D conformation in the file.

## 4. Protein + double-stranded DNA

```json
[
  {
    "name": "tf_dna",
    "sequences": [
      { "proteinChain": { "sequence": "MAEVIRSS...HHHHHHHH", "count": 1 } },
      { "dnaSequence": { "sequence": "CTAGGTAACATTACTCGCG", "count": 1 } },
      { "dnaSequence": { "sequence": "CGCGAGTAATGTTACCTAG", "count": 1 } }
    ]
  }
]
```

dsDNA = two single strands (the second is the reverse complement).

## 5. Modifications (PTMs / modified bases)

```json
[
  {
    "name": "phospho",
    "sequences": [
      { "proteinChain": {
          "sequence": "PREACHINGS", "count": 1,
          "modifications": [
            { "ptmType": "CCD_HY3", "ptmPosition": 1 },
            { "ptmType": "CCD_P1L", "ptmPosition": 5 }
          ] } }
    ]
  }
]
```

DNA/RNA use `modificationType` + `basePosition` instead of `ptmType`/`ptmPosition`.

## 6. Covalent bond (e.g. covalent ligand / glycosylation)

```json
[
  {
    "name": "covalent_complex",
    "sequences": [
      { "proteinChain": { "sequence": "MGS...QRL", "count": 1 } },
      { "ligand": { "ligand": "FILE_/abs/path/warhead.sdf", "count": 1 } }
    ],
    "covalent_bonds": [
      { "entity1": 1, "copy1": 1, "position1": 145, "atom1": "SG",
        "entity2": 2, "copy2": 1, "position2": 1, "atom2": "C1" }
    ]
  }
]
```

`entity` = 1-based order in `sequences`. Ligand `position` is `1` for
single-CCD/SMILES/FILE; the ligand `atom` can be a 0-based index or
element+occurrence (e.g. `C1`).

## 7. Precomputed MSA / template paths (skip auto-search)

```json
[
  {
    "name": "with_msa",
    "sequences": [
      { "proteinChain": {
          "sequence": "MGSSHHHH...PEP", "count": 1,
          "pairedMsaPath":   "/abs/path/pairing.a3m",
          "unpairedMsaPath": "/abs/path/non_pairing.a3m",
          "templatesPath":   "/abs/path/hmmsearch.a3m" } }
    ]
  }
]
```

Generate these with `protenix msa` / `mt` / `prep`, or supply your own. Use
absolute paths.

## 8. Pocket constraint (needs `protenix_base_constraint_v0.5.0`)

```json
[
  {
    "name": "epitope_guided",
    "sequences": [
      { "proteinChain": { "sequence": "ANTIGEN...SEQ", "count": 1 } },
      { "proteinChain": { "sequence": "BINDER...SEQ",  "count": 1 } }
    ],
    "constraint": {
      "pocket": {
        "binder_chain": { "entity": 2, "copy": 1 },
        "contact_residues": [
          { "entity": 1, "copy": 1, "position": 126 },
          { "entity": 1, "copy": 1, "position": 130 }
        ],
        "max_distance": 6
      }
    }
  }
]
```

## 9. Contact constraint (atom- or token-level)

```json
[
  {
    "name": "contact_guided",
    "sequences": [
      { "proteinChain": { "sequence": "PROTEIN...SEQ", "count": 1 } },
      { "ligand": { "ligand": "CCD_ATP", "count": 1 } }
    ],
    "constraint": {
      "contact": [
        { "entity1": 1, "copy1": 1, "position1": 169, "atom1": "CA",
          "entity2": 2, "copy2": 1, "position2": 1,  "atom2": "C5",
          "max_distance": 6, "min_distance": 3 }
      ]
    }
  }
]
```

Omit `atom1`/`atom2` for a token-level contact (uses the token's central atom);
`min_distance` defaults to 0.
</content>
