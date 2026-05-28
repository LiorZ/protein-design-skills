---
name: biotite
description: >
  Use Biotite — a fast, NumPy-backed Python library for computational
  molecular biology — to read, manipulate, analyze, and write biomolecular
  structures and sequences, and to fetch data from biological databases. This
  is the toolkit/"glue" library of the collection: it does not fold or design
  proteins, it lets you operate on the structures and sequences that the
  predictors/designers consume and produce. Use this skill when:
  (1) Parsing, editing, or writing **structure files** — PDB, mmCIF / PDBx,
      BinaryCIF, MOL / SDF, GRO, and MD trajectories (XTC / TRR / DCD / NetCDF),
  (2) Selecting / filtering atoms, residues, or chains with NumPy boolean masks
      over annotation arrays (the `AtomArray` / `AtomArrayStack` data model),
  (3) **Superimposing** structures and computing **RMSD / RMSF / lDDT /
      TM-score** — e.g. comparing a designed backbone to its AlphaFold3 / Boltz /
      Chai prediction, or two predictions to each other,
  (4) Structural analysis: **SASA**, **secondary-structure** assignment,
      **hydrogen bonds**, distances / angles / dihedrals, base pairs, RDF,
  (5) **Fetching** structures and sequences from **RCSB PDB, AlphaFold DB,
      UniProt, NCBI Entrez, and PubChem** with rich search queries,
  (6) Sequence work: DNA / RNA / protein sequence types, translation, pairwise
      and **multiple sequence alignment**, substitution matrices, fast **k-mer
      homology search**, sequence profiles / consensus, phylogenetic trees,
  (7) Reading / writing **FASTA, FASTQ, GenBank, GFF**, and building / parsing
      MSAs (incl. A3M),
  (8) Driving external tools through thin wrappers — **DSSP**, **MUSCLE /
      MAFFT / Clustal Omega**, **NCBI BLAST**, **AutoDock Vina**, **ViennaRNA**,
  (9) Converting an `AtomArray` to/from **RDKit** `Mol`, **OpenMM**
      `System`/`Topology`, or scripting **PyMOL** for rendering.

  This skill is written for the current Biotite **v1.x** (1.6.0). Biotite is a
  pure pip/conda install — **no GPU, no container** — with light dependencies
  (numpy, requests, msgpack, networkx). The skill covers the `AtomArray` data
  model, the `File.read → get_structure` / `set_structure → File.write` I/O
  pattern (and the `load_structure` / `save_structure` shortcuts), structure and
  sequence analysis, database access, the application wrappers, and the
  `biotite.interface` bridges — plus how to use Biotite as the connective tissue
  around the other tools in this collection.

  Limitations: Biotite is a **toolkit, not a model** — it does not predict or
  design structures (use `boltz` / `chai-lab` / `protenix` / `foundry` /
  `boltzgen` / `disco` for that). `biotite.application` wrappers need the
  external binary on `PATH`; `biotite.interface` bridges need the optional
  package (`rdkit`, `openmm`, or `pymol`) installed.

  Pairs with: every skill here — parse and **score** the CIF/PDB outputs of
  `boltz` / `chai-lab` / `protenix` / `foundry` / `genie3` (RMSD / lDDT /
  TM-score / clash / SASA filters), **fetch** targets from RCSB / AlphaFold DB
  for `boltzgen` / `disco`, **prepare** and clean input structures, and convert
  ligands via the RDKit bridge. `protflow` wraps several Biotite-style metrics
  (RMSD, TM-align, DSSP) as pipeline runners.
license: BSD-3-Clause
category: protein-design
tags: [structural-bioinformatics, sequence-analysis, file-io, pdb, mmcif, msa, rmsd, tm-score, sasa, secondary-structure, rcsb, alphafold-db, uniprot, rdkit, openmm, pymol, numpy, python-library]
repo: https://github.com/biotite-dev/biotite
biorxiv: https://doi.org/10.1186/s12859-018-2367-z
---

# Biotite — computational molecular biology toolkit

## What this is

Biotite is a comprehensive, **NumPy-backed** Python library for working with
biological **sequences** and **structures**. Everything is built on plain
`ndarray`s, so it is fast and interoperable, and you manipulate structures with
the NumPy idioms you already know (boolean masks, fancy indexing, vectorized
math). It is the *toolkit* of this collection — not a predictor or designer.
Reach for it to **prepare inputs for** and **analyze / score the outputs of**
the folding and design models.

Four pillars (one subpackage each):

| Subpackage | What it does |
|------------|--------------|
| `biotite.structure` | The `AtomArray` data model + structure I/O, filtering, superimposition, RMSD/lDDT/TM, SASA, SSE, H-bonds, geometry, the CCD (`.info`). |
| `biotite.sequence` | `NucleotideSequence` / `ProteinSequence`, pairwise + multiple alignment, substitution matrices, k-mer search, profiles, phylogenetics, sequence I/O. |
| `biotite.database` | Fetch + search **RCSB PDB**, **AlphaFold DB**, **UniProt**, **NCBI Entrez**, **PubChem**. |
| `biotite.application` / `biotite.interface` | Thin wrappers around external binaries (DSSP, MUSCLE, MAFFT, BLAST, Vina, ViennaRNA) and conversion bridges to RDKit / OpenMM / PyMOL. |

> **The one mental model to internalize, read first:** an **`AtomArray`** is one
> model of *n* atoms. Its coordinates are a `(n, 3)` float array (`.coord`); its
> per-atom metadata are parallel length-*n* "annotation arrays" — `chain_id`,
> `res_id`, `res_name`, `atom_name`, `element`, `hetero`, `ins_code` (plus
> optional `b_factor`, `occupancy`, `charge`, …). You **select** atoms by
> building a boolean mask over those arrays and indexing:
> `array[array.atom_name == "CA"]`. An **`AtomArrayStack`** is *m* models of the
> same atoms — coords `(m, n, 3)` — e.g. NMR models, a trajectory, or the N
> samples from a co-folding model. Units are **Ångström** throughout.

## When to use Biotite vs. alternatives

| You want… | Use |
|-----------|-----|
| Read/edit/write PDB/mmCIF/SDF/trajectory; select atoms; compute RMSD/lDDT/TM/SASA/SSE | **Biotite** |
| **Predict** a complex structure from sequence + ligand | `boltz`, `chai-lab`, `protenix` |
| **Design** a backbone / sequence | `foundry` (RFdiffusion3/MPNN), `genie3`, `boltzgen`, `disco` |
| Refine/score a **ligand pose** in a pocket | `placer` |
| Orchestrate a multi-step **pipeline** on SLURM | `protflow` |
| Heavy MD analysis (many long trajectories, on-the-fly) | MDAnalysis / MDTraj (Biotite reads trajectories fine, but isn't an MD-analysis framework) |
| Just-need-a-quick-parse, deeply nested PDB header records | Biopython is an alternative; Biotite is faster and more array-friendly |

The common role in a campaign: **design** (`foundry`/`genie3`/`boltzgen`) →
**predict** (`boltz`/`chai-lab`/`protenix`) → **Biotite** to superimpose the
prediction on the design, compute backbone RMSD / interface lDDT / TM-score,
flag clashes, and filter survivors → keep the winners.

## Install

```bash
pip install biotite              # pulls numpy, requests, msgpack, networkx
# or:  conda install -c conda-forge biotite
```

Optional extras, only if you use them:
- `biotite.interface.rdkit` → `pip install rdkit` (≥ 2024.09.1)
- `biotite.interface.openmm` → `conda install -c conda-forge openmm`
- `biotite.interface.pymol`  → PyMOL (open-source build) on the env
- `biotite.application.*`     → the external binary on `PATH` (`mkdssp`,
  `muscle`, `mafft`, `clustalo`, `vina`, `RNAfold`, …)

Requires Python ≥ 3.11. Details + the per-wrapper binary list:
`references/installation.md`.

## Quickstart — fetch, load, analyze, save

```python
import biotite.database.rcsb as rcsb
import biotite.structure as struc
import biotite.structure.io as strucio

# 1) Fetch a structure from the RCSB PDB (BinaryCIF is smallest/fastest)
path = rcsb.fetch("1AKI", "bcif", target_path="/tmp")

# 2) Load it into an AtomArray (first model)
structure = strucio.load_structure(path)        # AtomArray (n atoms)

# 3) Select: protein CA atoms of chain A, via boolean masks on annotations
mask = (
    struc.filter_amino_acids(structure)
    & (structure.atom_name == "CA")
    & (structure.chain_id == "A")
)
ca = structure[mask]
print(ca.array_length(), "residues")

# 4) Analyze
sasa_per_atom = struc.sasa(structure)            # Shrake-Rupley, Å²
sse           = struc.annotate_sse(structure)    # per-residue 'a'/'b'/'c'

# 5) Save back out (format inferred from extension)
strucio.save_structure("/tmp/chainA_ca.pdb", ca)
```

Compare two structures (the bread-and-butter design-validation step):

```python
# superimpose `pred` onto `design` over matched atoms, then measure deviation
fitted, transform = struc.superimpose(design, pred)   # Kabsch
idx = np.arange(design.array_length())                # design & pred already 1:1 (e.g. matched CA)
print("RMSD:", struc.rmsd(design, fitted))
print("TM:",   struc.tm_score(design, fitted, idx, idx))   # needs corresponding indices
print("lDDT:", struc.lddt(design, pred))              # superposition-free
```

## The I/O pattern (read this once)

Two equivalent ways to get a structure in and out:

```python
# (a) Shortcuts — format inferred from the file extension:
import biotite.structure.io as strucio
atoms = strucio.load_structure("x.cif")      # AtomArray (or AtomArrayStack if model=None and multi-model)
strucio.save_structure("y.pdb", atoms)

# (b) Explicit File object — needed for headers, assemblies, bonds, components:
import biotite.structure.io.pdbx as pdbx
f = pdbx.CIFFile.read("x.cif")               # or BinaryCIFFile.read("x.bcif")
atoms = pdbx.get_structure(f, model=1, include_bonds=True, extra_fields=["b_factor"])
# ...edit atoms...
out = pdbx.CIFFile()
pdbx.set_structure(out, atoms)
out.write("y.cif")
```

- `model=1` → an `AtomArray` (one model). Omit `model` → an `AtomArrayStack`
  (all models). **mmCIF / BinaryCIF is the preferred modern format** (PDB has hard
  column-width limits and can't represent large systems); `pdbx` reads both.
- For trajectories you must pass a topology **template**:
  `XTCFile.read("traj.xtc").get_structure(template)`.
- Ligands / small molecules: `biotite.structure.io.mol` (`MOLFile`, `SDFile`).

Full format matrix (PDB / PDBx / BinaryCIF / MOL / SDF / GRO / XTC / TRR / DCD /
NetCDF) + assemblies, altlocs, bonds, and sequence-file I/O (FASTA / FASTQ /
GenBank / GFF): `references/file-io.md`.

## What lives where (reference index)

- `references/installation.md` — pip/conda, Python version, optional-dependency
  matrix (rdkit/openmm/pymol), and the external binaries each
  `biotite.application` wrapper needs.
- `references/structure.md` — the `biotite.structure` workhorse: `Atom` /
  `AtomArray` / `AtomArrayStack` / `BondList`, annotations, indexing & the
  `filter_*` helpers, residue/chain iteration, `superimpose*` / `rmsd` / `rmsf` /
  `lddt` / `tm_score`, `sasa`, `annotate_sse`, `hbond`, geometry
  (`distance`/`angle`/`dihedral`), transforms, and the CCD (`structure.info`).
- `references/sequence.md` — `biotite.sequence`: sequence types & translation,
  `align_optimal` / `align_multiple`, `SubstitutionMatrix`, `Alignment` &
  identity, the `KmerTable` fast-search workflow, `SequenceProfile`, and
  `phylo` trees.
- `references/file-io.md` — every structure & sequence file format, the
  `read → get_structure` / `set_structure → write` contract, `load_structure` /
  `save_structure`, assemblies, altlocs, bonds, trajectories.
- `references/database.md` — `rcsb` / `entrez` / `uniprot` / `afdb` / `pubchem`
  `fetch` + the `search` / `Query` builders (FieldQuery, SequenceQuery, …).
- `references/applications.md` — the `LocalApp` / `WebApp` lifecycle and each
  wrapper (DSSP, MUSCLE/MAFFT/Clustal, BLAST, Vina, ViennaRNA, tantan, SRA),
  plus the `biotite.interface` bridges (RDKit, OpenMM, PyMOL).
- `references/troubleshooting.md` — common pitfalls (views vs. copies, missing
  bonds, altloc/insertion codes, PDB width limits, element inference, web
  rate-limits).
- `examples/quickstart.py` — a runnable end-to-end script.
- `examples/recipes.md` — copy-paste snippets by task.

## Gotchas (read before you debug)

1. **Indexing can return a view, not a copy.** `sub = array[mask]` may share
   the underlying annotation arrays; mutate via `.copy()` when in doubt
   (NumPy semantics).
2. **Many functions need bonds.** `sasa` on hydrogens, charge/aromaticity, RDKit
   export, and some filters expect a `BondList`. Load with
   `include_bonds=True`, or build one with `struc.connect_via_residue_names` /
   `connect_via_distances`.
3. **`superimpose` does not match atoms for you.** Both inputs must be
   atom-for-atom corresponding (e.g. both filtered to CA). For differing
   sequences use `superimpose_homologs`; for distant structures
   `superimpose_structural_homologs` (TM-based). `rmsd` itself does **no**
   alignment.
4. **PDB has hard limits** (≤ 99,999 atoms, 4-char chain ids via hybrid-36,
   narrow columns). Use mmCIF / BinaryCIF for anything large or programmatic.
5. **`load_structure` returns a Stack for multi-model files** unless you pass
   `model=`. Code that assumes an `AtomArray` will break on NMR/predicted
   ensembles.
6. **Element column matters.** Some PDBs lack it; downstream mass/radius/bond
   logic then misbehaves. `extra_fields` and `repair`/`info` helpers fix this.
7. **`application` wrappers shell out** to a binary that must be installed and on
   `PATH`; **`interface`** bridges import an optional package. Neither ships with
   Biotite.
8. **SSE codes are lowercase** `'a'` (alpha-helix), `'b'` (beta-strand), `'c'`
   (coil) from `annotate_sse` — not DSSP's 8-state. Use `DsspApp` for 8-state.

More failure modes + fixes: `references/troubleshooting.md`.

## Citation

Biotite is BSD-3-Clause, developed by Patrick Kunzmann & the Biotite
contributors. If you use it in published work:

```
Kunzmann, P. & Hamacher, K.
Biotite: a unifying open source computational biology framework in Python.
BMC Bioinformatics 19, 346 (2018). https://doi.org/10.1186/s12859-018-2367-z

Kunzmann, P. et al.
Biotite: new tools for a versatile Python bioinformatics library.
BMC Bioinformatics 24, 236 (2023). https://doi.org/10.1186/s12859-023-05345-6
```

Docs & tutorial: https://www.biotite-python.org
