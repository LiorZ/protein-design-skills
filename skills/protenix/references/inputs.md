# Input JSON format

Protenix input is an **AlphaFold-Server-style** JSON: a top-level **list** of
job dictionaries, even for a single job. Each job:

```json
[
  {
    "name": "my_job",
    "sequences": [ ... ],          // required: the entities to fold
    "covalent_bonds": [ ... ],     // optional: inter-entity bonds
    "constraint": { ... },         // optional: soft pocket/contact priors
    "modelSeeds": []               // optional: seeds (used with --use_seeds_in_json)
  }
]
```

- `name` — job name; becomes the output sub-directory.
- `sequences` — list of entity dicts (below). Entity **order matters**: the
  1-based index is the `entity` number referenced by bonds/constraints.

Differences from the AlphaFold Server format: no restriction on ligand/ion/PTM
CCD codes; explicit inter-entity bonds; ligands as SMILES or structure files;
multi-CCD ligands as one entity (e.g. glycans `"CCD_NAG_NAG"`); the `glycans`
field is removed (use bonded ligands / SMILES instead).

## Entities (`sequences`)

Five entity types: `proteinChain`, `dnaSequence`, `rnaSequence`, `ligand`, `ion`.
All polymers accept `count` (copies) and an optional `id` (explicit chain IDs;
list length must equal `count`, e.g. `"id": ["H", "L"]`).

### `proteinChain`

```json
{
  "proteinChain": {
    "sequence": "PREACHINGS",
    "count": 1,
    "id": ["A"],
    "modifications": [
      { "ptmType": "CCD_HY3", "ptmPosition": 1 },
      { "ptmType": "CCD_P1L", "ptmPosition": 5 }
    ],
    "pairedMsaPath":   "/abs/path/pairing.a3m",
    "unpairedMsaPath": "/abs/path/non_pairing.a3m",
    "templatesPath":   "/abs/path/hmmsearch.a3m"
  }
}
```

- `sequence` — 20 standard amino acids + `X` (UNK) only.
- `modifications` — PTMs: `ptmType` is a CCD code, `ptmPosition` is 1-based.
- `pairedMsaPath` / `unpairedMsaPath` — precomputed MSAs (typically `pairing.a3m`
  / `non_pairing.a3m`). **Use absolute paths.** Optional — omitted ⇒ MMseqs2
  auto-search (with `--use_msa true`).
- `templatesPath` — precomputed templates, `.a3m` (hmmsearch) or `.hhr`. Optional.

> The old `"msa": {"precomputed_msa_dir": ..., "pairing_db": ...}` dict form
> still works but is **deprecated** — prefer `pairedMsaPath`/`unpairedMsaPath`.
> (`examples/example.json` uses the old form; newer examples use the new fields.)

### `dnaSequence` / `rnaSequence`

```json
{ "dnaSequence": { "sequence": "GATTACA", "count": 1,
    "modifications": [ { "modificationType": "CCD_6OG", "basePosition": 1 } ] } }
```

```json
{ "rnaSequence": { "sequence": "GUAC", "count": 1,
    "unpairedMsaPath": "/abs/path/rna_msa.a3m",
    "modifications": [ { "modificationType": "CCD_2MG", "basePosition": 1 } ] } }
```

- DNA: letters `A T G C N`. RNA: letters `A U G C N`.
- `dnaSequence` is **single-stranded** — for dsDNA add a second entry with the
  reverse-complement strand.
- `modifications`: `modificationType` (CCD code) + `basePosition` (1-based).
- RNA `unpairedMsaPath` — optional precomputed RNA MSA (`.a3m`).

### `ligand`

```json
{ "ligand": { "ligand": "CCD_ATP", "count": 1 } }
{ "ligand": { "ligand": "FILE_/abs/path/atp.sdf", "count": 1 } }
{ "ligand": { "ligand": "Nc1ncnc2c1ncn2[C@@H]1O[C@H]...O)O", "count": 1 } }
```

`ligand` is one of:
- **CCD code** prefixed `CCD_` (e.g. `CCD_ATP`). Multi-residue ligands/glycans:
  concatenate, e.g. `CCD_NAG_BMA_BGC`.
- A **SMILES** string.
- A **3D structure file** prefixed `FILE_` (PDB, SDF, MOL, MOL2). The file
  **must contain a 3D conformation**.

### `ion`

```json
{ "ion": { "ion": "MG", "count": 2 } }
```

`ion` is a CCD code **without** the `CCD_` prefix (e.g. `MG`, `NA`, `ZN`).

## `covalent_bonds`

Bonds between a polymer and a ligand, or between two ligands (and, for cyclic
peptides only, head-to-tail amide or disulfide bonds between polymer residues).

```json
"covalent_bonds": [
  { "entity1": 2, "copy1": 1, "position1": 2, "atom1": "N6",
    "entity2": 3, "copy2": 1, "position2": 1, "atom2": "C1" }
]
```

- `entity1/2` — 1-based index into `sequences`.
- `copy1/2` — 1-based copy index. Both or neither; if omitted, bonds are made
  across matching copy pairs (entities must then have equal `count`).
- `position1/2` — residue position. Polymers: residue index. Multi-CCD ligand:
  the CCD serial number. Single-CCD / SMILES / FILE ligand: always `1`.
- `atom1/2` — atom **name** (polymer / CCD), or for SMILES/FILE ligands either a
  0-based atom **index**, or element+occurrence (e.g. `C3`, `N2`, 1-based).

> General polymer–polymer covalent bonds are **not reliably modeled** (the model
> just pulls the residues close). Only cyclic-peptide head-to-tail / disulfide
> bonds are properly supported. Field names use `entity1/entity2`; the old
> `left_*`/`right_*` names still parse but are deprecated.

## `constraint` (soft pocket / contact priors)

Requires the **constraint** checkpoint (`protenix_base_constraint_v0.5.0`).
These are *soft* — the model is encouraged, not forced, to satisfy them.

### `contact` — distance between two residues/atoms

```json
"constraint": {
  "contact": [
    { "entity1": 1, "copy1": 1, "position1": 169,
      "entity2": 2, "copy2": 1, "position2": 1, "atom2": "C5",
      "max_distance": 6, "min_distance": 0 }
  ]
}
```

- `entity/copy/position` (1/2) required. `atom1`/`atom2` optional — omit for a
  **token-level** contact (uses the token's central atom); include for an
  **atom-level** contact.
- `max_distance` (Å) required; `min_distance` (Å) defaults to 0.

### `pocket` — bias a binder chain toward contact residues

```json
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
```

Use for epitope-guided antibody / ligand-pocket prediction: keep the binder
chain near the listed residues within `max_distance` Å.

## Output of model & where it goes

`pred` writes to `-o/--out_dir`:

```
<out_dir>/<name>/<seed>/
  ├── <name>_<seed>_sample_0.cif
  ├── <name>_<seed>_summary_confidence_sample_0.json
  └── ...                                  # one set per sample (-e/--sample)
```

See `outputs.md` for the confidence-score definitions and ranking.

## Generating inputs

- **From a structure:** `protenix json -i complex.pdb -o ./jsons` (see `cli.md`).
- **Add MSAs/templates:** `protenix msa` / `mt` / `prep` rewrite the JSON with
  `pairedMsaPath` / `unpairedMsaPath` / `templatesPath` / RNA MSA paths.

## Bundled examples (in `~/Repos/Protenix/examples/`)

| File | Shows |
|------|-------|
| `input.json` | Minimal single protein chain |
| `example.json` | Multi-job: protein+dsDNA (7r6r), protein+ligands+ion (7wux), protein+DNA+ligand (7pzb) — **old `msa` dict form** |
| `example_without_msa.json` | Input lacking MSA (feed to `protenix mt`) |
| `example_constraint_msa.json` | `constraint` block usage |
| `examples_with_template/` | `.a3m` and `.hhr` `templatesPath` examples |
| `examples_with_rna_msa/` | RNA `unpairedMsaPath` example |
| `example_with_json_template/` | Antibody (`demo_ab.json`) and JSON-template examples |
| `ligands/` | SMILES (`.smi`) and 3D `.sdf` ligand files for `FILE_`/SMILES inputs |

Curated copy-paste snippets are in `../examples/input_examples.md`.
</content>
