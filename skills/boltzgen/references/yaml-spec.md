# YAML design specification — full reference

A BoltzGen design YAML has two top-level keys:

```yaml
entities:    # list of proteins, ligands, and structure files (required)
constraints: # list of bonds and total-length rules (optional)
leaving_atoms: # list of CCD atoms to remove (optional, advanced)
```

Everything that follows is one of those.

## ⚠️ Universal rules

1. **All residue indices are 1-based and use the canonical mmCIF
   `label_asym_id` / `label_seq_id`**, not the author chain / residue
   numbers PyMOL or ChimeraX usually show.
2. **File paths in `path:` are relative to the YAML's directory**, not
   your CWD.
3. **Run `boltzgen check FILE.yaml`** after every edit and open the
   resulting CIF in https://molstar.org/viewer/ — binding-site / design /
   visibility-0 regions are colored so problems are obvious.

## Index syntax cheat sheet

Wherever a `res_index` or `binding` or `sequence` accepts indices, you
can write:

| Syntax           | Means                                       |
|------------------|---------------------------------------------|
| `5`              | residue 5                                   |
| `5,8,11`         | residues 5, 8, 11                           |
| `5..7`           | residues 5–7 inclusive                      |
| `5..7,13`        | residues 5–7 inclusive *plus* 13            |
| `..5`            | residues 1 … 5                              |
| `55..`           | residues 55 … end                           |
| `"all"`          | all residues (only where a string is OK)    |

---

# `entities`

Each entry under `entities` is exactly one of:

```yaml
- protein: …    # a chain to design or keep fixed (sequence-defined)
- ligand: …     # a small molecule (CCD or SMILES)
- file: …       # one or more structure files to import chains from
```

## `protein` — designed or fixed amino-acid chain

```yaml
- protein:
    id: G                          # required; unique single-letter chain id
                                   # (or a list to clone the entity, e.g. id: [E, F])
    sequence: 15..20AAAAAAVTTTT18PPP
    binding_types: uuuuBBBuNNNuBuu # OR dict form below
    secondary_structure: HHHLLLEEE # OR dict form below
    cyclic: true                   # head-to-tail cyclization
    residue_constraints:           # per-position allow/disallow
      - position: 1
        allowed: A                 # whitelist
      - position: 3..5
        disallowed: CM             # blacklist
      - position: 8
        allowed: AGS               # tri-state whitelist
    symmetric_group: 1             # tie sampled length across chains
```

### Sequence notation

The `sequence` string mixes **fixed residues** (single-letter amino-acid
codes) with **designed regions** (numbers):

| Token         | Meaning                                                         |
|---------------|------------------------------------------------------------------|
| `AAVTT`       | Fixed sequence — these exact residues, in order                  |
| `18`          | Exactly 18 designed residues                                     |
| `15..20`      | Between 15 and 20 designed residues (sampled once per batch)     |
| `3..5C6C3`    | 3–5 designed, fixed `C`, 6 designed, fixed `C`, 3 designed       |
| `10C6C3`      | 10 designed, fixed `C`, 6 designed, fixed `C`, 3 designed        |
| `1..3CC4C1..3C1..3` | Designed/fixed chains with multiple cysteines              |
| `C10C6C3C`    | Fixed Cys + 10 designed + Cys + 6 designed + Cys + 3 designed + Cys |

Length ranges are sampled **per diffusion batch**, not per design. With
`--diffusion_batch_size 10` and `--num_designs 10`, you get 10 designs of
the *same* length. Use a small batch size *or* a much larger
`num_designs` for balanced length coverage.

### `binding_types` — which residues should / should not bind

Two equivalent forms.

**String form** (one letter per residue, only legal when sequence has no
length ranges):

```yaml
binding_types: uuuuBBBuNNNuBuu
```

| Char | Meaning              |
|------|----------------------|
| `B`  | Binding residue      |
| `N`  | Non-binding residue  |
| `u`  | Unspecified (default)|

Trailing positions can be omitted — defaults to `u`.

**Dict form** (preferred — works with length ranges):

```yaml
binding_types:
  binding: 5..7,13       # residues to bind
  not_binding: 9..11     # residues that must NOT bind
```

### `secondary_structure` — design-region SS conditioning

Only applies to designed residues. Three buckets:

```yaml
secondary_structure: HHHLLLEEE     # string form (H=helix, L=loop, E=sheet)
```

or

```yaml
secondary_structure:
  loop: 1
  helix: 2..3,7..10
  sheet: 4,11..14
```

### `cyclic: true`

Head-to-tail backbone cyclization (`N` of residue 1 covalently linked to
the carboxyl carbon of residue N). Pairs well with disulfide bonds
declared in `constraints` for cyclotides.

### `residue_constraints` — per-position whitelist / blacklist

Tested via `tests/test_residue_constraints.py`. Applied at inverse-folding
time, so they have no effect with `--skip_inverse_folding`.

```yaml
residue_constraints:
  - position: 1
    allowed: A           # Only Alanine at position 1
  - position: 3..5
    disallowed: CM       # No Cys or Met at positions 3-5
  - position: 8
    allowed: AGS         # Only A, G, or S at position 8
  - position: 10
    allowed: P           # Only Proline at position 10
```

`allowed:` / `disallowed:` accept either a string of one-letter codes
(`"AGS"`) or a list (`[A, G, S]`). String form is preferred for
consistency with `sequence:` and `binding_types:`.

**Statistical note** — with `--num_designs 5` a single blacklist
constraint has ~21% chance of false-pass. Validate with at least 50.

### `symmetric_group` — tied sequence sampling (`protein-redesign`)

For symmetric multimers, tag chains with the same `symmetric_group:`
integer so the inverse-folder samples one sequence and replicates it.
Typically used inside a `file` entity (see below) rather than a free
protein. Example:

```yaml
entities:
  - file:
      path: homodimer.cif
      include:
        - chain:
            id: A
            symmetric_group: 1
        - chain:
            id: B
            symmetric_group: 1
      design:
        - chain:
            id: A
            res_index: 200..210
        - chain:
            id: B
            res_index: 200..210
```

Use `--protocol protein-redesign` for these.

---

## `ligand` — small molecule

```yaml
- ligand:
    id: Q                              # single id, or list to clone, e.g. [E, F]
    ccd: WHL                           # mutually exclusive with smiles
    smiles: 'N[C@@H](Cc1ccc(O)cc1)C(=O)O'
    binding_types: B                   # 'B' = ligand should be bound; default unspec
```

Choose `ccd:` (3-letter Chemical Component Dictionary code, e.g. `SAH`,
`WHL`, `TSA`) **or** `smiles:`, never both.

Atom names referenced in `constraints.bond` differ:

- For a CCD ligand, atom names are taken from the CCD entry verbatim:
  e.g., `CK`, `CH`, `OE2`, …
- For a SMILES ligand, atom names are **element + index** counting from
  1 in SMILES order: `C1` is the first carbon, `C6` the sixth, `O1` the
  first oxygen, etc.

You can clone identical ligands by passing a list of ids:

```yaml
- ligand:
    id: [C, D]   # two SAH molecules
    ccd: SAH
```

---

## `file` — bring in chains from a CIF / PDB / nested YAML

```yaml
- file:
    path: 8r3a.cif                # or list of YAML scaffold files
    use_assembly: true            # instantiate biological assemblies (A → A1, A2, …)
    msa: …                        # global MSA flag (rarely set)
    include: …                    # which chains/residues to import
    include_proximity: …          # crop to a radius around a reference selection
    exclude: …                    # carve out residues post-include
    reset_res_index: …            # renumber chain residues 1..N after include/exclude
    fuse: A                       # graft following protein entities onto chain A
    binding_types: …              # binding / not_binding on target residues
    structure_groups: …           # visibility of target residues
    design: …                     # which target residues to redesign
    not_design: …                 # subtract from `design`
    secondary_structure: …        # SS conditioning on redesigned residues
    design_insertions: …          # insert new designed loops into a chain
```

### `path` — a CIF, a PDB, or a list of YAMLs

```yaml
path: 7rpz.cif
```

or

```yaml
path: target.pdb       # PDB also works
```

or **a list of nested YAML files** (scaffolds — see "Antibody / nanobody"
below):

```yaml
path:
  - ../nanobody_scaffolds/7eow.yaml
  - ../nanobody_scaffolds/gontivimab.yaml
```

The nested YAML uses the same `file`-shaped schema (no `entities:`
wrapper required when at the inner scaffold level — see the upstream
`example/nanobody_scaffolds/*.yaml` files).

### `include` — chains and residue ranges

Either the literal `"all"`:

```yaml
include: "all"
```

Or a list of chains:

```yaml
include:
  - chain:
      id: A
      res_index: 2..50,55..
  - chain:
      id: B           # all residues on chain B
```

Each `chain` can also carry `msa:` (override the global) and
`symmetric_group:` (tie sampled lengths in the protein-redesign protocol).

### `include_proximity` — crop a large target

```yaml
include_proximity:
  - chain:
      id: A
      res_index: 106..118
      radius: 30        # Å
```

Imports all residues from the file that lie within `radius` Å of the
listed reference selection. Indispensable when the source CIF is huge
(e.g., a ribosome, an MHC) but you only care about one site.

### `exclude` — remove residues after include

```yaml
exclude:
  - chain:
      id: A
      res_index: ..5,63..69
```

Common pattern in antibody / nanobody scaffolds: `include` the whole
chain, then `exclude` the CDR positions, then `design_insertions` puts
designed loops back in their place.

### `reset_res_index` — renumber after include/exclude

```yaml
reset_res_index:
  - chain:
      id: B
```

Renumbers the residues of the listed chains consecutively from 1. Use
this *after* `exclude` whenever residue numbering matters for downstream
indexing (typical for nanobody / Fab scaffolds with multi-segment CDRs).

### `fuse: A` — graft following protein entities onto a file chain

```yaml
- protein:
    id: A
    sequence: AAAAAAAAAAAAAAAAAAAAAAAA
- file:
    path: 7rpz.cif
    fuse: A                # chain A from this file is appended to protein A
    include:
      - chain:
          id: A
          res_index: ..5
```

Splices the imported residues onto the matching `protein` entity by chain
id. Niche but powerful for fixed N-terminal anchors followed by a
designed body.

### `binding_types` — target-side binding / not-binding

```yaml
binding_types:
  - chain:
      id: A
      binding: 5..7,13
  - chain:
      id: B
      not_binding: "all"     # never bind chain B
```

This tells BoltzGen where on the target the designed binder must / must
not contact.

### `structure_groups` — show / hide target structure

```yaml
structure_groups:
  - group:
      visibility: 1      # 1 = structure visible (default)
      id: A
      res_index: 10..13
  - group:
      visibility: 2      # 2 = visible but pose unspecified relative to group 1
      id: B
  - group:
      visibility: 0      # 0 = hide structure for this region (still in sequence)
      id: A
      res_index: 13
```

| Visibility | Meaning                                                                                          |
|------------|--------------------------------------------------------------------------------------------------|
| `0`        | Structure NOT specified — residues are present in sequence but their coordinates are unknown.     |
| `1`        | Structure specified (default).                                                                    |
| `2`        | Structure specified, but its **position relative to other groups** is unconstrained.              |

Later `group` entries **override** earlier ones for overlapping residues.

`structure_groups: "all"` is shorthand for visibility 1 over every included
residue.

Use cases:
- Flexible loops on a target → `visibility: 0` over the loop residues.
- Unknown / disordered tails → `visibility: 0` over `..20` or `200..`.
- Multi-domain rigid bodies with unknown relative orientation →
  put each domain in a separate `visibility: 2` group.

### `design` / `not_design` — redesign existing residues

```yaml
design:
  - chain:
      id: A
      res_index: 14..19
not_design:
  - chain:
      id: A
      res_index: 16
```

`design` marks residues on a `file`-loaded chain to be **redesigned**
(their identity is replaced; their backbone may also move).
`not_design` subtracts from `design` — useful for "redesign the whole
chain except these catalytic / disulfide residues".

For antibody / nanobody CDR design the pattern is:
1. `include` the whole chain.
2. `design` the CDR positions (heavy: 26-32, 52-57, 99-110; light: 24-34,
   50-56, 89-97).
3. `structure_groups: visibility: 0` over the CDRs to drop their original
   coordinates.
4. `exclude` the original CDR residues (so they don't double up).
5. `design_insertions` to put in new CDRs of variable length.
6. `reset_res_index` so positional encoding stays consecutive.

### `secondary_structure` on a `file` chain

Same `loop` / `helix` / `sheet` keys as for the `protein` entity, but
keyed by chain:

```yaml
secondary_structure:
  - chain:
      id: A
      loop: 14
      helix: 15..17
      sheet: 19
```

Only applies to redesigned positions (those listed under `design:`).

### `design_insertions` — add new designed loops

```yaml
design_insertions:
  - insertion:
      id: A
      res_index: 26          # insert AFTER this residue
      num_residues: 7..9     # 7-9 designed residues (range OK)
      secondary_structure: HELIX
                             # UNSPECIFIED (default), LOOP, HELIX, SHEET
```

`res_index` is the position whose right side gets the insertion.
`num_residues` accepts a range (`3..8`) or a single integer.

Used **with** `exclude` (to remove the original residues at the insertion
locus) and `design` (no-op here because the inserted loop is designed by
construction).

---

# `constraints`

```yaml
constraints:
  - bond: …
  - total_len:
      min: 10
      max: 20
```

## `bond` — covalent bonds

```yaml
- bond:
    atom1: [R, 4, SG]    # [chain_id, residue_idx, atom_name]
    atom2: [Q, 1, CK]
```

- **chain_id**: matches an `id` from `entities`.
- **residue_idx**: 1-based.
  - For chains with length ranges, count *as if the minimum length was
    sampled*. The model handles the offset internally.
- **atom_name**: CCD-standard atom name, case-sensitive (e.g., `SG`,
  `N`, `CD`, `OE2`).
  - For SMILES ligands: element + 1-based SMILES index (`C6`, `O1`).
  - For CCD ligands: look up the atom name in the RCSB CCD entry.

Common bond patterns:

```yaml
# Disulfide
- bond:
    atom1: [B, 2, SG]
    atom2: [B, 14, SG]

# Stapled peptide (WHL ligand)
- bond:
    atom1: [G, 4, SG]
    atom2: [F, 1, CK]
- bond:
    atom1: [G, 11, SG]
    atom2: [F, 1, CH]

# Head-to-tail isopeptide (cyclization that 'cyclic: true' doesn't do)
- bond:
    atom1: [C, 1, N]
    atom2: [C, 9, CD]
```

## `total_len`

```yaml
- total_len:
    min: 10
    max: 20
```

Constrains the *sum* of designed residues across all designed entities.
Useful when you have several length ranges and want a global cap.

---

# `leaving_atoms`

Advanced: tell BoltzGen to remove specific atoms before sampling.
Mostly used for chemically exotic cyclizations:

```yaml
constraints:
  - bond:
      atom1: [C, 1, N]
      atom2: [C, 9, CD]
leaving_atoms:
  - atom: [C, 9, OE2]   # GLU's OE2 leaves when CD makes the new bond
```

Atoms are `[chain_id, residue_idx, atom_name]`, same syntax as `bond`.

---

# Putting it together — full kitchen-sink example

```yaml
entities:
  - protein:
      id: G
      sequence: 15..20AAAAAAVTTTT18PPP
      residue_constraints:
        - position: 1
          allowed: A
        - position: 3..5
          disallowed: CM
        - position: 8
          allowed: AGS

  - protein:
      id: R
      sequence: 3..5C6C3            # peptide with two designed Cys for a staple

  - ligand:
      id: Q
      ccd: WHL                      # the staple

  - file:
      path: 7rpz.cif
      include:
        - chain:
            id: A
        - chain:
            id: B
      include_proximity:
        - chain:
            id: A
            res_index: 10..16
            radius: 35
      binding_types:
        - chain:
            id: A
            binding: 5..7,13
        - chain:
            id: B
            not_binding: "all"
      structure_groups:
        - group: {visibility: 1, id: A, res_index: 10..16}
        - group: {visibility: 2, id: B}
        - group: {visibility: 0, id: A, res_index: 13}
      design:
        - chain: {id: A, res_index: ..4,20..27}
      secondary_structure:
        - chain: {id: A, loop: 1, helix: 2..3, sheet: 4}
      design_insertions:
        - insertion: {id: A, res_index: 20, num_residues: 2..9, secondary_structure: HELIX}

  - protein:
      id: A
      sequence: AAAAAAAAAAAAAAAAAAAAAAAA
      binding_types: uuuuBBBuNNNuBuu

  - file:
      path: 7rpz.cif
      fuse: A
      include:
        - chain: {id: A, res_index: ..5}

  - protein:
      id: T
      sequence: C10C6C3C
      cyclic: true

constraints:
  - bond: {atom1: [R, 4, SG],  atom2: [Q, 1, CK]}
  - bond: {atom1: [R, 11, SG], atom2: [Q, 1, CH]}
  - bond: {atom1: [T, 12, SG], atom2: [T, 19, SG]}
  - total_len: {min: 10, max: 200}
```

See [`../examples/design_spec_kitchen_sink.yaml`](../examples/design_spec_kitchen_sink.yaml)
for a copy-pastable version.
