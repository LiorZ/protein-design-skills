# `biotite.application` & `biotite.interface`

Two ways Biotite connects to the outside world:

- **`biotite.application`** runs an entire **external program** under the hood
  (build command line → execute → parse output). Needs the binary installed.
- **`biotite.interface`** only **converts objects** to/from another Python
  library (RDKit, OpenMM, PyMOL), leaving you to drive that library. Needs the
  package installed.

See `installation.md` for what to install for each.

## `biotite.application` — the lifecycle

Every wrapper is an `Application` with a uniform state machine:

```python
app = SomeApp(...)
app.start()            # launch (CREATED -> RUNNING)
app.join()             # block until done (-> JOINED), parse output
result = app.get_...() # wrapper-specific getter
```

Most wrappers also offer a one-shot **classmethod** that does
start+join+extract for you (`MafftApp.align(...)`, etc.) — prefer it. `LocalApp`
runs a local binary; `WebApp` hits a remote service.

### Multiple sequence alignment (`MSAApp` family)

All take `Sequence` objects and return a Biotite `Alignment`.

```python
from biotite.application.mafft import MafftApp
from biotite.application.muscle import MuscleApp, Muscle5App
from biotite.application.clustalo import ClustalOmegaApp

aln = MafftApp.align([s1, s2, s3], matrix=matrix)          # MAFFT
aln = Muscle5App.align([s1, s2, s3])                       # MUSCLE v5
aln = ClustalOmegaApp.align([s1, s2, s3])                  # Clustal Omega
```

Instance methods add control: `Muscle5App(...).use_super5()` (large inputs),
`.set_iterations(...)`, `.set_thread_number(n)`; then `.get_alignment()`. Some
return a guide tree via `.get_guide_tree()`.

### Secondary structure — DSSP (8-state)

`annotate_sse` in `biotite.structure` is a fast 3-state (a/b/c) approximation.
For the canonical **8-state** DSSP, wrap the `mkdssp` binary:

```python
from biotite.application.dssp import DsspApp
sse = DsspApp.annotate_sse(atom_array)     # per-residue: C H B E G I T S
```

### BLAST (web — no binary)

```python
from biotite.application.blast import BlastWebApp
app = BlastWebApp("blastp", query_protein_sequence, database="nr",
                  mail="you@example.com")   # be polite; NCBI rate-limits
app.start(); app.join()
alignments = app.get_alignments()           # list[BlastAlignment]
```

`program` ∈ `blastn`/`blastp`/`blastx`/`tblastn`/`tblastx`.

### Other wrappers

- **AutoDock Vina** — `from biotite.application.autodock import VinaApp`:
  `VinaApp(ligand, receptor, center, size)` → docked poses. (For pose
  *refinement/scoring* of a ligand already in a pocket, prefer the `placer`
  skill; Vina here is for de-novo docking into a box.)
- **ViennaRNA** — `RNAfoldApp(sequence)` → `.get_free_energy()`,
  `.get_dot_bracket()`; `RNAplotApp` → 2D layout coordinates.
- **tantan** — `TantanApp(sequence)` → `.get_mask()` low-complexity/repeat mask.
- **SRA** — `FastqDumpApp(accession)` / `FastaDumpApp(accession)` pull reads via
  `prefetch` + `fasterq-dump`.

## `biotite.interface` — conversion bridges

`import biotite.interface.rdkit as rdkit_if` etc. These convert; they don't run.

### RDKit  (`biotite.interface.rdkit`)

```python
import biotite.interface.rdkit as rdkit_interface
mol  = rdkit_interface.to_mol(atom_array)          # AtomArray -> rdkit Mol (REQUIRES bonds)
atoms = rdkit_interface.from_mol(mol)              # rdkit Mol -> AtomArray (multi-conformer -> Stack)
```

- `to_mol` needs a populated `BondList` (load with `include_bonds=True`, or
  `struc.connect_via_residue_names`). Options: `kekulize`, `explicit_hydrogen`,
  `use_dative_bonds`, `include_extra_annotations`.
- Round-trip a ligand through RDKit for SMILES, descriptors, conformer
  generation, or correct bond perception, then bring it back. Needs **RDKit ≥
  2024.09.1**.

### OpenMM  (`biotite.interface.openmm`)

```python
import biotite.interface.openmm as openmm_interface
topology = openmm_interface.to_topology(atom_array)   # needs bonds
system   = openmm_interface.to_system(atom_array)     # masses + box
# after a simulation step, pull coordinates back onto the template:
atoms    = openmm_interface.from_state(template, state)            # one frame -> AtomArray
ensemble = openmm_interface.from_states(template, states)          # many -> AtomArrayStack
atoms    = openmm_interface.from_context(template, context)
```

Lets you set up / read back MD without leaving the `AtomArray` world.

### PyMOL  (`biotite.interface.pymol`)

```python
import biotite.interface.pymol as pymol_interface
pymol_interface.launch_pymol()                         # library mode, no GUI
obj = pymol_interface.PyMOLObject.from_structure(atom_array)
obj.color("red", atom_array.chain_id == "A")           # masks select atoms
obj.show("cartoon")
obj.orient()
img = pymol_interface.show(size=(800, 600), use_ray=True)   # render (e.g. in Jupyter)
back = obj.to_structure()                               # PyMOL -> AtomArray
```

Every selection argument accepts a **NumPy boolean mask** over the original
`AtomArray` — no PyMOL selection-language strings needed. Methods mirror PyMOL
`cmd`: `color`, `show`, `hide`, `cartoon`, `set`, `zoom`, `orient`, `label`,
`distance`, `select`, …

## Which to reach for

| Goal | Tool |
|------|------|
| MSA of many sequences | `MafftApp` / `Muscle5App` (or `align.align_multiple` for a few) |
| 8-state secondary structure | `DsspApp` (3-state: `struc.annotate_sse`) |
| Remote homology search | `BlastWebApp` (or build a `KmerTable`, `sequence.md`) |
| SMILES ⇄ structure, conformers, descriptors | RDKit bridge |
| Set up / read back an MD simulation | OpenMM bridge |
| Publication-quality render | PyMOL bridge |
