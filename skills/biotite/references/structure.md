# `biotite.structure` — the structure workhorse

Everything here is `import biotite.structure as struc`. Units are **Å**. The
subpackage is built on NumPy: structures *are* arrays, and you analyze them with
array operations.

## 1. The data model

| Type | Holds | `.coord` shape |
|------|-------|----------------|
| `Atom` | one atom (scalar annotations) | `(3,)` |
| `AtomArray` | one model of *n* atoms | `(n, 3)` |
| `AtomArrayStack` | *m* models of the same *n* atoms | `(m, n, 3)` |

Each carries **annotation arrays** (parallel, length *n*). Mandatory:
`chain_id`, `res_id` (int), `ins_code`, `res_name`, `hetero` (bool),
`atom_name`, `element`. Optional and used by some functions: `atom_id`,
`b_factor`, `occupancy`, `charge`, `sym_id`, `entity_id`.

Access annotations as attributes (`array.res_id`) or via
`get_annotation(cat)` / `set_annotation(cat, arr)` / `add_annotation(cat, dtype)`.
List them with `get_annotation_categories()`.

```python
array.array_length()      # n  (atoms per model)
stack.stack_depth()       # m  (number of models)
array.shape               # (n,)         ;  stack.shape -> (m, n)
array.copy()              # deep copy (indexing alone may give a view)
array.bonds               # BondList or None
array.box                 # (3,3) unit-cell/box vectors, or None
```

**Indexing rules** (NumPy-style, propagated to every annotation):
- `array[i]` (int) → `Atom`; `stack[i]` → `AtomArray`; `stack[i, j]` → `Atom`.
- `array[mask]` / `array[slice]` / `array[idx_array]` → a substructure of the
  same type.

### Building / combining

```python
struc.array([atom1, atom2, ...])        # list[Atom] -> AtomArray
struc.stack([arr1, arr2, ...])          # equal AtomArrays -> AtomArrayStack
struc.concatenate([arrA, arrB])         # join along the atom axis
struc.repeat(atoms, coord)              # tile annotations over new coords -> Stack
struc.from_template(template, coord)    # template annotations + new coords -> Stack
struc.coord(obj)                        # pull out the coordinate ndarray
```

## 2. Selection — boolean masks over annotations

This is the core idiom. Build a mask, index with it.

```python
ca   = array[array.atom_name == "CA"]
chnA = array[array.chain_id == "A"]
core = array[(array.atom_name == "CA") & (array.res_id >= 10) & (array.res_id <= 40)]
hetero_only = array[array.hetero]                 # ligands/waters/ions (HETATM)
no_h = array[array.element != "H"]
```

### Ready-made filters (`struc.filter_*` → boolean mask)

| Filter | Selects |
|--------|---------|
| `filter_amino_acids(a)` | any amino-acid atom (incl. non-canonical) |
| `filter_canonical_amino_acids(a)` | the 20 standard (+ SEC/PYL) |
| `filter_nucleotides(a)` / `filter_canonical_nucleotides(a)` | RNA/DNA |
| `filter_carbohydrates(a)` | sugars |
| `filter_solvent(a)` | water and common solvents |
| `filter_monoatomic_ions(a)` | Na⁺, Cl⁻, Zn²⁺, … |
| `filter_peptide_backbone(a)` | N, CA, C |
| `filter_phosphate_backbone(a)` | nucleic backbone P, O5', C5', C4', C3', O3' |
| `filter_heavy(a)` | non-hydrogen |
| `filter_polymer(a, pol_type="peptide")` | atoms in a polymer chain |
| `filter_first_altloc(a, altloc_ids)` | one altloc per atom (first) |
| `filter_highest_occupancy_altloc(a, altloc_ids, occ)` | highest-occupancy altloc |
| `filter_intersection(a, other)` | atoms of `a` also present in `other` |

Altloc filtering matters when loading crystal structures with alternate
conformations — see `file-io.md` (`altloc=` on `get_structure`).

## 3. Residue & chain iteration

Partition without manual bookkeeping:

```python
struc.get_residue_count(array)
for res in struc.residue_iter(array):     # yields AtomArray per residue
    ...
struc.get_residues(array)                  # (res_ids, list_of_residue_arrays)
struc.get_residue_starts(array)            # atom indices where each residue begins

struc.get_chain_count(array)
for chain in struc.chain_iter(array):      # yields AtomArray per chain
    ...
struc.get_chains(array)
struc.get_chain_starts(array)

# Reduce per-residue (e.g. mean B-factor per residue):
struc.apply_residue_wise(array, array.b_factor, np.mean)
struc.spread_residue_wise(array, per_residue_values)   # expand back to per-atom
```

(Analogous `apply_chain_wise` / `spread_chain_wise`.)

## 4. Superimposition & comparison

`superimpose` solves the Kabsch rotation+translation that minimizes RMSD over
**atom-for-atom corresponding** inputs and returns `(fitted, transformation)`.
It does **not** find the correspondence — match atoms yourself first (e.g. both
filtered to CA).

```python
fitted, transform = struc.superimpose(fixed, mobile)
moved = transform.apply(other_atoms)        # reuse the same transform elsewhere

# differing sequences -> align sequences first, then superimpose:
fitted, t, fix_idx, mob_idx = struc.superimpose_homologs(fixed, mobile)
# distant/structural homologs -> TM-based correspondence:
fitted, t, fix_idx, mob_idx = struc.superimpose_structural_homologs(fixed, mobile)
# robust to a few bad atoms:
fitted, t, _, _ = struc.superimpose_without_outliers(fixed, mobile, max_iterations=...)
```

Metrics:

| Function | Meaning | Needs prior superposition? |
|----------|---------|----------------------------|
| `rmsd(ref, subject)` | RMS coordinate deviation | **yes** (does no fitting) |
| `rmsf(ref, stack)` | per-atom RMS fluctuation across models | yes (fit the stack first) |
| `rmspd(ref, subject)` | RMS of pairwise distance differences | no (fit-free) |
| `tm_score(ref, subject, ref_idx, sub_idx, reference_length="shorter")` | TM-score ∈ (0,1], length-normalized | yes |
| `lddt(ref, subject)` | Local Distance Difference Test ∈ [0,1] | **no** (superposition-free) |
| `average(stack)` | mean-coordinate structure | n/a |

`tm_score` needs the **corresponding atom indices** in each structure (it does
not match for you). If the two inputs already line up 1:1 (e.g. both filtered to
the same CA set), pass `np.arange(n)` for both; otherwise get the indices from
`superimpose_structural_homologs` (which returns `fixed_indices, mobile_indices`)
and feed them in:

```python
idx = np.arange(ref.array_length())
struc.tm_score(ref, fitted, idx, idx)               # already-matched atoms
# or, for differing structures:
fitted, t, f_idx, m_idx = struc.superimpose_structural_homologs(ref, mobile)
struc.tm_score(ref, fitted, f_idx, m_idx, reference_length="shorter")
```

For design validation: **TM-score** for global fold agreement, **lDDT** for
local/interface quality without needing a good global superposition, **RMSD**
over a matched core for a familiar number. (For binder iPAE/ipSAE-style metrics,
read those from the predictor's own output — see the `chai-lab` / `boltz`
skills.)

## 5. Geometry

All take `Atom`/`AtomArray`/`AtomArrayStack`/`ndarray`; angles in **radians**.

```python
struc.distance(a1, a2)                      # pairwise Euclidean
struc.angle(a1, a2, a3)                     # a2 is the vertex
struc.dihedral(a1, a2, a3, a4)
phi, psi, omega = struc.dihedral_backbone(chain)   # 3 arrays, shape (n_res,); NaN at termini -> Ramachandran
struc.centroid(atoms)                       # geometric center
# index_* variants take an array + index arrays (vectorized over many tuples):
struc.index_distance(array, pairs)          # pairs: (k,2) int
struc.index_dihedral(array, quads)
```

Pass `box=array.box` to any of these for **periodic** (minimum-image)
distances/angles in a simulation box.

## 6. Surface, secondary structure, H-bonds

```python
sasa = struc.sasa(array, probe_radius=1.4)  # per-atom solvent-accessible area, Å²
                                            # sum, or apply_residue_wise for per-residue

sse  = struc.annotate_sse(array)            # per-RESIDUE: 'a' helix, 'b' strand, 'c' coil
                                            # (P-SEA algorithm; lowercase 3-state.
                                            #  For DSSP 8-state use application.DsspApp)

triplets = struc.hbond(array)               # (k,3) int: donor, hydrogen, acceptor atom idx
freq     = struc.hbond_frequency(mask)      # over an AtomArrayStack / trajectory
```

Nucleic-acid specific: `base_pairs(array)`, `base_stacking`, `dot_bracket`,
`pseudoknots` (in `basepairs.py` / `dotbracket.py` / `pseudoknots.py`).

## 7. Transforms

```python
struc.translate(atoms, vector)
struc.rotate(atoms, [rx, ry, rz])               # Euler angles, radians
struc.rotate_centered(atoms, angles)            # about the centroid
struc.rotate_about_axis(atoms, axis, angle)
struc.orient_principal_components(atoms)        # align inertia axes to xyz
struc.align_vectors(atoms, origin_vec, target_vec)
# AffineTransformation (returned by superimpose) has .apply() and composes.
```

## 8. Bonds (`BondList`)

```python
array.bonds                                  # BondList or None
bonds = struc.connect_via_residue_names(array)   # CCD templates -> intra-residue bonds (fast, accurate)
bonds = struc.connect_via_distances(array)       # distance heuristic (no templates needed)
array.bonds = bonds

bonds.as_array()                             # (k,3): atom_i, atom_j, BondType
bonds.add_bond(i, j, struc.BondType.SINGLE)
bonds.get_bonds(atom_i)                      # (neighbor_idx, bond_types)
```

`BondType`: `ANY`, `SINGLE`, `DOUBLE`, `TRIPLE`, `QUADRUPLE`,
`AROMATIC_SINGLE/DOUBLE/TRIPLE`, `AROMATIC`, `COORDINATION`. Bonds are required
for RDKit export, charge/aromaticity logic, and some analyses — load with
`include_bonds=True` or build them as above.

## 9. The Chemical Component Dictionary (`structure.info`)

`import biotite.structure.info as info` — local lookups against the wwPDB CCD,
no network:

```python
info.residue("ALA")                  # AtomArray template (ideal coords + bonds)
info.bonds_in_residue("HEM")         # BondList for the component
info.full_name("ATP")                # "ADENOSINE-5'-TRIPHOSPHATE"
info.link_type("ALA")                # e.g. "L-PEPTIDE LINKING"
info.one_letter_code("ALA")          # "A"
info.mass("ALA")                     # residue/atom mass (Da)
info.vdw_radius_single("C")          # van der Waals radius
info.standardize_order(residue)      # reorder atoms to CCD canonical order
info.all_residues()                  # every known component id
```

Use `info.residue(...)` to graft missing atoms, validate atom names, or build
ligand templates; `standardize_order` before comparing/merging structures from
different sources.

## See also

- File formats and the read/write contract → `file-io.md`
- Sequence side (alignment, matrices, k-mer search) → `sequence.md`
- DSSP 8-state, MSA tools, BLAST → `applications.md`
- RDKit / OpenMM / PyMOL conversion → `applications.md`
