# File I/O — structures and sequences

## The contract

Biotite separates the **file** (a parsed representation of the file's contents)
from the **structure/sequence** (the `AtomArray` / `Sequence` you work with).
Two layers:

```
File.read(path)  ──get_structure()──►  AtomArray / AtomArrayStack
AtomArray  ──set_structure(file, ...)──►  File  ──file.write(path)
```

For the 90% case there are shortcuts that infer the format from the extension:

```python
import biotite.structure.io as strucio
atoms = strucio.load_structure("x.cif")     # -> AtomArray (or Stack if multi-model)
strucio.save_structure("y.pdb", atoms)      # extension picks the writer
```

Use the explicit `File` layer when you need headers, assemblies, bonds,
components, specific data blocks, or fine control over fields.

## Structure formats

| Format | Extension(s) | Module | Class | Notes |
|--------|--------------|--------|-------|-------|
| **PDBx / mmCIF** | `.cif`, `.pdbx` | `biotite.structure.io.pdbx` | `CIFFile` | **preferred** text format; full feature set |
| **BinaryCIF** | `.bcif` | `biotite.structure.io.pdbx` | `BinaryCIFFile` | compact binary mmCIF; fastest, smallest |
| **PDB** | `.pdb` | `biotite.structure.io.pdb` | `PDBFile` | legacy; column-limited (see gotchas) |
| **MOL** | `.mol` | `biotite.structure.io.mol` | `MOLFile` | single small molecule (V2000/V3000) |
| **SDF** | `.sdf`, `.sd` | `biotite.structure.io.mol` | `SDFile` | many molecules + properties |
| **GRO** | `.gro` | `biotite.structure.io.gro` | `GROFile` | GROMACS coordinate file |
| **Trajectories** | `.xtc` `.trr` `.dcd` `.netcdf` | `…io.{xtc,trr,dcd,netcdf}` | `XTCFile` … | coords only — need a topology template |

### mmCIF / BinaryCIF (the one to use)

```python
import biotite.structure.io.pdbx as pdbx

f = pdbx.CIFFile.read("1aki.cif")             # or BinaryCIFFile.read("1aki.bcif")
atoms = pdbx.get_structure(
    f,
    model=1,                 # int -> AtomArray; omit -> AtomArrayStack (all models)
    altloc="first",          # "first" | "occupancy" | "all"
    extra_fields=["b_factor", "occupancy", "charge"],   # beyond the mandatory annotations
    include_bonds=True,      # populate AtomArray.bonds from the chem_comp_bond/struct_conn
    use_author_fields=True,  # author (auth_) vs label_ numbering
)

# write
out = pdbx.CIFFile()
pdbx.set_structure(out, atoms)
out.write("out.cif")
```

Other useful `pdbx` helpers (all take the file object):
- `pdbx.get_sequence(f)` — the SEQRES/entity sequence(s) as `Sequence` objects.
- `pdbx.list_assemblies(f)` / `pdbx.get_assembly(f, assembly_id, model=1)` — build a
  biological assembly (applies symmetry to generate the full oligomer).
- `pdbx.get_component(f, comp_id)` — a chemical component (ligand template).
- `pdbx.get_model_count(f)`, `pdbx.get_unit_cell(f)`, `pdbx.get_sse(f)`.

### PDB

```python
import biotite.structure.io.pdb as pdb
f = pdb.PDBFile.read("x.pdb")
atoms = pdb.get_structure(f, model=1, extra_fields=["b_factor"])
pdb.set_structure(f2, atoms, hybrid36=True)   # hybrid-36 to exceed 99,999 atoms / 4-char ids
f2.write("y.pdb")
# also: pdb.get_assembly(f, assembly_id), pdb.list_assemblies(f), pdb.get_model_count(f)
```

PDB is lossy and column-limited (≤ 99,999 atoms, narrow chain/residue fields).
Prefer mmCIF/BinaryCIF for anything large, programmatic, or round-tripped.

### Ligands — MOL / SDF

```python
import biotite.structure.io.mol as mol
sdf = mol.SDFile.read("ligands.sdf")
for name in sdf:                       # SDFile is dict-like over records
    record = sdf[name]
lig = mol.get_structure(sdf)           # AtomArray (with bonds, from the connection table)
```

MOL/SDF carry an explicit bond block, so the resulting `AtomArray` has a
populated `.bonds` — handy for the RDKit bridge (`applications.md`).

### Trajectories (need a template)

Trajectory files store **coordinates only**. Supply a topology (an `AtomArray`
with the right annotations, e.g. from the matching `.gro`/`.pdb`):

```python
import biotite.structure.io.xtc as xtc
template = strucio.load_structure("system.gro")
traj = xtc.XTCFile.read("traj.xtc", start=0, stop=1000, step=10, atom_i=ca_indices)
ensemble = traj.get_structure(template)        # AtomArrayStack (m frames, n atoms)
coords   = traj.get_coord()                     # raw (m, n, 3) in Å
box      = traj.get_box()                        # (m, 3, 3)
```

`read_iter` / `read_iter_structure` stream frames for trajectories too large for
memory. `TRRFile`, `DCDFile`, `NetCDFFile` share the same interface; `GROFile`
holds a single frame (`get_structure()` → `AtomArray`).

## Sequence formats

```python
import biotite.sequence.io as seqio
seq  = seqio.load_sequence("p.fasta")       # first sequence; .fasta/.fastq/.gb autodetected
seqs = seqio.load_sequences("p.fasta")      # OrderedDict {header: Sequence}
seqio.save_sequence("out.fasta", seq)
```

### FASTA (`biotite.sequence.io.fasta`)

```python
import biotite.sequence.io.fasta as fasta
ff = fasta.FastaFile.read("seqs.fasta")     # dict-like {header: raw_string}
prot = fasta.get_sequence(ff, header="sp|P69905|HBA_HUMAN")   # auto Protein/Nucleotide
all_seqs = fasta.get_sequences(ff)          # {header: Sequence}
fasta.set_sequence(ff, my_seq, header="design_01")
ff.write("out.fasta")

# alignments as gapped FASTA / A3M:
aln  = fasta.get_alignment(ff)              # -> Alignment
msas = fasta.get_a3m_alignments(a3m_file)   # A3M query-vs-target pairwise alignments
```

### FASTQ / GenBank / GFF

- `biotite.sequence.io.fastq.FastqFile` — `file[id] = (seq_str, quality_array)`;
  `offset="Sanger"` | `"Illumina"`.
- `biotite.sequence.io.genbank.GenBankFile` (+ `MultiFile`) —
  `get_sequence(f)`, `get_annotation(f)` (→ `Annotation` of `Feature`s),
  `get_definition(f)`.
- `biotite.sequence.io.gff.GFFFile` — GFF3 features.

## Format-choice cheatsheet

- **Reading a PDB-deposited structure** → fetch `bcif` (smallest) or `cif`; read
  with `pdbx`.
- **A predictor's output** (Boltz/Chai/Protenix/AF3) → usually `.cif`; read with
  `pdbx.get_structure(... model=1, include_bonds=False)`. These often lack
  hydrogens and full bond records — build bonds with
  `connect_via_residue_names` if you need them.
- **A ligand** → MOL/SDF (keeps bonds) → RDKit bridge.
- **An MD run** → topology from `.gro`/`.pdb` + coords from `.xtc`/`.dcd`.
- **Round-tripping / large systems** → mmCIF or BinaryCIF, never PDB.
