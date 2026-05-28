# Troubleshooting

## Data model / selection

| Symptom | Cause / fix |
|---------|-------------|
| Edits to a sliced array change the original (or vice-versa) | Indexing can return a **view**, not a copy. Call `.copy()` before mutating: `sub = array[mask].copy()`. |
| `array[mask]` raises a shape error | The mask must be length `array.array_length()` (one bool per atom). Build it from annotation arrays of the *same* array. |
| Filter returns nothing | Check the annotation you keyed on actually exists/populated (`array.get_annotation_categories()`); e.g. `element` may be blank in some PDBs. |
| `AttributeError: 'AtomArrayStack' object has no attribute ...` after load | You loaded a multi-model file and got a **Stack**, not an `AtomArray`. Pass `model=1` to `get_structure` / index `stack[0]`. |

## Bonds

| Symptom | Cause / fix |
|---------|-------------|
| `to_mol` / OpenMM export fails with "no bonds" | The `AtomArray` has `bonds=None`. Load with `include_bonds=True`, or `array.bonds = struc.connect_via_residue_names(array)`. |
| Bonds wrong for a ligand / non-standard residue | `connect_via_residue_names` relies on the CCD; for novel chemistry read an SDF/MOL (carries an explicit bond block) or use `connect_via_distances`. |
| Aromatic rings non-planar after RDKit round-trip | Pass `kekulize`/`explicit_hydrogen` to `to_mol`, or seed bonds from an SDF reference. |

## Superimposition / metrics

| Symptom | Cause / fix |
|---------|-------------|
| `superimpose` / `rmsd` shape mismatch | Inputs must be **atom-for-atom corresponding**. Filter both to the same atoms (e.g. CA) and the same length. |
| RMSD huge despite similar folds | `rmsd` does **no** alignment. Call `superimpose` first, or use `superimpose_homologs` (sequence-aware) / `superimpose_structural_homologs` (TM-based) when residue counts differ. |
| Comparing two different sequences | Use `superimpose_homologs` (aligns sequences → CA anchors) — don't hand-match indices. |
| Want a superposition-free quality score | Use `lddt` (local) or `rmspd` (pairwise-distance) — neither needs a good global fit. |

## File I/O

| Symptom | Cause / fix |
|---------|-------------|
| PDB write fails / truncates on a big system | PDB caps at 99,999 atoms and narrow columns. Use `set_structure(..., hybrid36=True)`, or just write mmCIF / BinaryCIF. |
| Insertion codes / altlocs duplicate residues | Choose an altloc on read: `get_structure(f, altloc="first")` (or `"occupancy"`); handle `ins_code` explicitly. |
| Trajectory load errors / wrong atom count | Trajectories store coords only — pass a matching topology **template** to `get_structure(template)`; ensure `atom_i` and template agree. |
| Predicted-model CIF (AF3/Boltz/Chai) missing bonds/H | Expected — those models output coords without full connectivity/hydrogens. Build bonds with `connect_via_residue_names`; add H via the RDKit/OpenMM bridge if needed. |
| `b_factor` / `occupancy` missing after load | They aren't loaded by default. Pass `extra_fields=["b_factor", "occupancy"]`. (For AlphaFold models, `b_factor` carries **pLDDT**.) |

## Secondary structure

| Symptom | Cause / fix |
|---------|-------------|
| `annotate_sse` gives only `a`/`b`/`c` | By design — it's a fast 3-state (P-SEA) approximation, lowercase. For DSSP 8-state (`C H B E G I T S`) use `application.dssp.DsspApp`. |
| `annotate_sse` returns `''` for some residues | That residue isn't an amino acid or lacks a `CA` atom. |

## Database / network

| Symptom | Cause / fix |
|---------|-------------|
| Entrez `fetch`/`search` throttled or 429 | Set an NCBI API key: `entrez.set_api_key("...")`; keep request rates modest. |
| PubChem requests slow / rejected | PubChem rate-limits; Biotite auto-throttles — don't parallelize hard. |
| `BlastWebApp` rejected | Provide `mail=` and obey rules; the NCBI web BLAST is for light use. For bulk, run BLAST+ locally. |
| `rcsb.fetch` 404 | Check the format string (`"bcif"`/`"cif"`/`"pdb"`/`"fasta"`) and that the id exists in that representation. |

## application / interface availability

| Symptom | Cause / fix |
|---------|-------------|
| `FileNotFoundError` launching an app | The external binary isn't on `PATH`. Install it (see `installation.md`) or pass `bin_path=`. |
| `ImportError` using a `biotite.interface.*` bridge | The optional package isn't installed: `pip install rdkit` / `conda install openmm` / install PyMOL. |
| RDKit bridge errors on import | Needs **RDKit ≥ 2024.09.1** for `to_mol`/`from_mol`. |

## Sanity checks

```python
import biotite, numpy as np
print(biotite.__version__)                       # confirm version
print(atoms.array_length(), atoms.shape)         # atom count / shape
print(atoms.get_annotation_categories())         # what fields are loaded
print(np.unique(atoms.chain_id), np.unique(atoms.element))
print(atoms.bonds is not None)                   # do we have connectivity?
```
