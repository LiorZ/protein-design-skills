# Residue & Atom Selection

The `protflow.residues` module defines two selection types — `ResidueSelection`
and `AtomSelection` — plus parsers from strings, dicts, contigs, and BioPython
entities. `protflow.tools.residue_selectors` provides four "Selector" classes
that *compute* selections from a pose and write them as a `poses.df` column.

## `ResidueSelection`

```python
from protflow.residues import ResidueSelection, from_dict, from_contig

# Three ways to build one:
ResidueSelection("A12,A13,A56")                         # comma string
ResidueSelection(["A12", "A13", "A56"])                  # list of strings
from_dict({"A": [12, 13], "B": [5]})                     # chain -> list of resnums
from_contig("A12-A20, B5")                                # contig form
```

Conversions:

```python
sel.to_string(delim=",", ordering=None)   # 'A12,A13,A14'
sel.to_list(ordering=None)                # ['A12','A13','A14']
sel.to_dict()                             # {'A':[12,13,14]}
sel.to_rfdiffusion_contig()               # 'A12-14'   (collapsed contiguous ranges)
```

Set operations (`__add__`, `__sub__`):

```python
core    = ResidueSelection("A12-A40")
exposed = ResidueSelection("A25,A30,A33")
core - exposed                            # core minus exposed
core + ResidueSelection("B5,B6")          # union
```

## Storing in `poses.df`

You can stash `ResidueSelection` objects directly in DataFrame cells. ProtFlow
serialises them transparently for every storage format:

- **pickle**: native object round-trip.
- **JSON**: serialises to a dict; `convert_resselection_cols` re-hydrates on
  load. Listed automatically when the column name appears in the special
  `import_resselection_cols` column (a list of column names per row).
- **CSV**: serialises to string; same re-hydration on load.

When loading a previous campaign via `Poses(poses="prev_scores.csv")`,
ProtFlow looks for `import_resselection_cols` and converts back to
`ResidueSelection`. If you populated such columns manually, set the
`import_resselection_cols` column to a list of column names per row so the
re-hydration finds them on the next load.

## `AtomSelection`

Atom-level analogue of `ResidueSelection`, used by metrics like `Distance`,
`Angle`, and selectors with `center_atoms=` / `noncenter_atoms=` arguments.

Atom IDs accept four shapes:

| Shape                              | Example                          |
|------------------------------------|----------------------------------|
| 3-tuple compact                    | `("A", 12, "CA")`                |
| 4-tuple (with model)               | `(0, "A", 12, "CA")`             |
| 5-tuple BioPython full-id          | `(structure, 0, "A", (' ',12,' '), ("CA",' '))` |
| 6-tuple BioPython full-id + altloc | `(...above..., 'A')`              |

Construction helpers:

```python
AtomSelection.from_list([("A",12,"CA"), ("A",13,"N")])
AtomSelection.from_dict({"A": [(12,"CA"), (13,"N")]})
AtomSelection.from_rfd3_contig("A12-A20", entity=pose)         # uses backbone atoms
AtomSelection.from_rfd3_ligand("LIG", pose=pose)                # all atoms of a ligand
AtomSelection.from_rfd3_input_selection(selection_dict, entity=pose)
AtomSelection.from_rfd3_input_spec(spec_dict_or_list, entity=pose)
```

The `from_rfd3_*` helpers parse Foundry RFD3 spec dictionaries (with keys
like `select_fixed_atoms`, `select_buried`, `select_hbond_donor`, …) into
the atom IDs RFdiffusion3 expects. ProtFlow ships these so you don't need
Foundry installed just to *describe* an RFD3 selection.

`AtomSelection` supports `+` (union) and `-` (difference), iteration, and
`.to_tuple()` / `.to_list()` / `.to_dict()`.

## Selectors that compute selections from a pose

In `protflow.tools.residue_selectors`. Each is a class with a `select(prefix)`
method that writes `{prefix}_residue_selection` to `poses.df`.

### `ChainSelector`

```python
from protflow.tools.residue_selectors import ChainSelector

ChainSelector(chains=["A", "B"]).select(prefix="binder_chains", poses=poses)
# poses.df["binder_chains_residue_selection"] = ResidueSelection of every residue in A or B
```

Constructor accepts `chain="A"` (single) or `chains=["A","B"]` (list).

### `TrueSelector`

Selects every residue. Useful as a starting point for `NotSelector`.

```python
TrueSelector().select(prefix="all", poses=poses)
```

### `NotSelector`

Complement of a given selection (per pose).

```python
NotSelector(residue_selection="active_site").select(prefix="not_active", poses=poses)
# or: NotSelector(contig="A12-A40").select(...)
```

`residue_selection` may be a column name (looked up per row) or a literal
`ResidueSelection`/string. If `contig=` is provided, every row gets the same
selection.

### `DistanceSelector`

Selects residues within a distance threshold of a center. The most powerful
selector — useful for binding pockets, interface residues, sidechain
proximity to ligands.

```python
DistanceSelector(
    center="ligand_atoms",            # column name, or AtomSelection, or contig string
    distance=6.0,
    operator="<=",                    # one of: "<", "<=", ">", ">="
    center_atoms=None,                 # restrict center to specific atom names
    noncenter_atoms=["CA"],            # restrict measured atoms on non-center residues
    include_center=False,              # whether to include the center residues themselves
).select(prefix="pocket", poses=poses)
```

Common patterns:

```python
# Pocket around a ligand (chain Z), measured to any backbone or sidechain atom:
DistanceSelector(center=ChainSelector(chain="Z"), distance=5.0).select(prefix="pocket", poses=poses)

# Interface residues within 8 Å of binder chain B, on the target side:
target_residues = NotSelector(...)   # define "everything except chain B"
DistanceSelector(center=ChainSelector(chain="B"), distance=8.0,
                  noncenter_atoms=["CA"]).select(prefix="interface", poses=poses)
```

## Motif tracking through RFdiffusion

RFdiffusion changes residue indices: a residue at A42 in the input may end up
at A18 in the output. To keep a `ResidueSelection` in sync, pass the column
name to `update_motifs`:

```python
poses.df["catalytic_triad"] = poses.df.apply(
    lambda r: ResidueSelection("A57,A102,A195"), axis=1
)
poses = rfdiff.run(
    poses, prefix="diff",
    options="'contigmap.contigs=[A1-300/0 30-30]'",
    update_motifs=["catalytic_triad"],   # re-indexed using con_ref_pdb_idx → con_hal_pdb_idx
)
# poses.df["catalytic_triad"] now contains the *new* indices for the same residues.
```

What `update_motifs` does:

1. Reads `<prefix>_con_ref_pdb_idx` and `<prefix>_con_hal_pdb_idx` from the
   RFdiffusion output (these are residue-by-residue mappings).
2. For each row of each motif column, applies the per-row mapping to produce
   a new `ResidueSelection` with the diffusion's residue indices.

If `<prefix>_complex_con_ref_pdb_idx` exists (binder-design mode with the
target preserved), ProtFlow uses the complex mapping instead. You don't have
to do anything; the runner picks the right one.

For motifs that ProtFlow doesn't know about (e.g. ligand atoms), update them
manually by reading the `_con_*_pdb_idx` columns yourself.

## Working examples

### Example 1: Pocket around a ligand, design only those residues

```python
from protflow.tools.residue_selectors import ChainSelector, DistanceSelector
from protflow.tools.ligandmpnn import LigandMPNN

# Define ligand (assumed in chain Z)
ligand = ChainSelector(chain="Z")
ligand.select(prefix="lig", poses=poses)

# 5 Å pocket around the ligand
DistanceSelector(center="lig_residue_selection", distance=5.0,
                  include_center=False).select(prefix="pocket", poses=poses)

# Design only the pocket
LigandMPNN().run(poses, prefix="design", nseq=8, model_type="ligand_mpnn",
                  design_res_col="pocket_residue_selection")
```

### Example 2: Fix a catalytic triad, design everything else

```python
poses.df["catalytic"] = poses.df.apply(
    lambda r: ResidueSelection("A57,A102,A195"), axis=1
)
LigandMPNN().run(poses, prefix="design", nseq=8, model_type="soluble_mpnn",
                  fixed_res_col="catalytic")
```

### Example 3: Interface residues for binder design

```python
binder = ChainSelector(chain="B")
binder.select(prefix="binder", poses=poses)

DistanceSelector(center="binder_residue_selection",
                  distance=8.0,
                  noncenter_atoms=["CA"]).select(prefix="interface", poses=poses)

# Now you can compute interface identity, RMSD over interface only, etc.
SelectionIdentity(residue_selection="interface_residue_selection",
                   onelettercode=True).run(poses, prefix="iface_seq")
```
