# Biotite examples

Runnable starting points for the `biotite` skill. Biotite is a plain Python
library — `pip install biotite` and run; no GPU, no container, no weights.

## Files

- **`quickstart.py`** — an end-to-end script: fetch `1AKI` from the RCSB,
  load it, select chain-A CA atoms and the ligand, compute SASA / secondary
  structure / backbone dihedrals, superimpose + score (RMSD / TM-score / lDDT),
  save out, and a small sequence-alignment block. Needs internet for the fetch.
- **`recipes.md`** — copy-paste snippets by task: load/save, select, compare a
  design to its prediction, per-residue pLDDT, biological assemblies, cleaning
  predicted models, interface contacts, fetching targets/ligands, MSA, and
  Ramachandran angles.

## Run it

```bash
pip install biotite
python quickstart.py
```

Expected: it prints the fetched path, atom/chain counts, a few analysis
numbers, the RMSD/TM/lDDT of a toy comparison, and a small alignment.

## The mental model (one paragraph)

An **`AtomArray`** is one model of *n* atoms: coordinates are `(n, 3)` in Å
(`.coord`), and per-atom metadata live in parallel length-*n* **annotation
arrays** (`chain_id`, `res_id`, `res_name`, `atom_name`, `element`, `hetero`, …).
You **select** atoms by building a NumPy boolean mask over those arrays and
indexing: `atoms[atoms.atom_name == "CA"]`. An **`AtomArrayStack`** holds *m*
models of the same atoms (`(m, n, 3)`) — NMR models, a trajectory, or the N
samples from a co-folding run. Files go in and out via
`File.read → get_structure` / `set_structure → File.write`, with
`load_structure` / `save_structure` as extension-inferring shortcuts.

## Key reminders

- **mmCIF / BinaryCIF over PDB** for anything large or programmatic; PDB has hard
  column limits.
- **`superimpose` doesn't match atoms** — filter both inputs to the same atoms
  first (e.g. CA), or use `superimpose_homologs` for differing sequences.
- **Many functions need bonds** — load with `include_bonds=True` or call
  `struc.connect_via_residue_names`.
- **pLDDT lives in `b_factor`** for AlphaFold/Boltz/Chai/Protenix models — pass
  `extra_fields=["b_factor"]` when loading.
- **`application.*`** needs the external binary on `PATH`; **`interface.*`** needs
  the optional package (rdkit/openmm/pymol).

See `../SKILL.md` for the overview and `../references/` for the full per-topic
docs (structure, sequence, file-io, database, applications, troubleshooting).
