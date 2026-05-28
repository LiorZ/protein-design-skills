# Biotite recipes

Copy-paste snippets by task. Assumes:

```python
import numpy as np
import biotite.structure as struc
import biotite.structure.io as strucio
import biotite.structure.io.pdbx as pdbx
```

## Load / save

```python
# auto by extension
atoms = strucio.load_structure("model.cif")          # AtomArray (Stack if multi-model)
strucio.save_structure("out.pdb", atoms)

# explicit, with bonds + b-factor (e.g. pLDDT from an AF/Boltz model)
f = pdbx.CIFFile.read("pred.cif")
atoms = pdbx.get_structure(f, model=1, extra_fields=["b_factor"], include_bonds=True)
```

## Select

```python
chain_a   = atoms[atoms.chain_id == "A"]
backbone  = atoms[struc.filter_peptide_backbone(atoms)]
ca        = atoms[atoms.atom_name == "CA"]
core      = atoms[(atoms.res_id >= 20) & (atoms.res_id <= 60)]
no_water  = atoms[~struc.filter_solvent(atoms)]
ligand    = atoms[atoms.hetero & ~struc.filter_solvent(atoms)
                  & ~struc.filter_monoatomic_ions(atoms)]
```

## Compare a design to its prediction

```python
design = strucio.load_structure("design.pdb")
pred   = strucio.load_structure("prediction.cif")

# match atoms first (CA of the designed chain)
d = design[(design.chain_id == "A") & (design.atom_name == "CA")]
p = pred[(pred.chain_id == "A") & (pred.atom_name == "CA")]

fitted, _ = struc.superimpose(d, p)
idx = np.arange(d.array_length())           # d & p already correspond 1:1
print("CA-RMSD:", struc.rmsd(d, fitted))
print("TM:", struc.tm_score(d, fitted, idx, idx))   # tm_score needs the matched indices
print("lDDT:", struc.lddt(d, p))            # superposition-free

# differing residue counts? let Biotite find the correspondence:
fitted, t, fix_idx, mob_idx = struc.superimpose_homologs(design_ca, pred_ca)
# (or superimpose_structural_homologs -> feed fix_idx/mob_idx straight into tm_score)
```

## Per-residue B-factor / pLDDT

```python
# AlphaFold/Boltz write pLDDT into the b_factor column
plddt_per_atom = atoms.b_factor
ca = atoms[atoms.atom_name == "CA"]
print("mean CA pLDDT:", ca.b_factor.mean())
# per-residue mean:
per_res = struc.apply_residue_wise(atoms, atoms.b_factor, np.mean)
```

## Build a biological assembly (oligomer from the asymmetric unit)

```python
f = pdbx.CIFFile.read("1aki.cif")
print(pdbx.list_assemblies(f))
assembly = pdbx.get_assembly(f, assembly_id="1", model=1)
```

## Clean a predicted model (add bonds, drop waters/ions)

```python
atoms = strucio.load_structure("pred.cif")
atoms = atoms[~struc.filter_solvent(atoms) & ~struc.filter_monoatomic_ions(atoms)]
atoms.bonds = struc.connect_via_residue_names(atoms)
strucio.save_structure("pred_clean.bcif", atoms)
```

## Distances / contacts at an interface

```python
a = atoms[atoms.chain_id == "A"]
b = atoms[atoms.chain_id == "B"]
# all-vs-all CA distances between chains
import numpy as np
ca_a = a[a.atom_name == "CA"]; ca_b = b[b.atom_name == "CA"]
d = np.linalg.norm(ca_a.coord[:, None] - ca_b.coord[None, :], axis=-1)
contacts = np.argwhere(d < 8.0)           # interface residue pairs
```

## Fetch + filter a target to design against

```python
import biotite.database.rcsb as rcsb
path = rcsb.fetch("4HHB", "bcif", target_path="/tmp")
target = strucio.load_structure(path)
chainA = target[(target.chain_id == "A") & struc.filter_amino_acids(target)]
strucio.save_structure("/tmp/target_chainA.pdb", chainA)   # hand to boltzgen/disco
```

## Pull a ligand from PubChem → RDKit

```python
import biotite.database.pubchem as pubchem
import biotite.interface.rdkit as rdkit_interface
from biotite.database.pubchem import NameQuery, search

cid = search(NameQuery("imatinib"))[0]
sdf_path = pubchem.fetch(cid, "sdf", target_path="/tmp")
lig = strucio.load_structure(sdf_path)        # bonds come from the SDF block
mol = rdkit_interface.to_mol(lig)             # -> rdkit Mol for SMILES/descriptors
```

## Pairwise % identity / MSA

```python
import biotite.sequence as seq
import biotite.sequence.align as align

matrix = align.SubstitutionMatrix.std_protein_matrix()
aln = align.align_optimal(seq.ProteinSequence(a), seq.ProteinSequence(b), matrix)[0]
print(align.get_sequence_identity(aln))

# MSA of a handful of sequences, no external binary:
msa, order, tree, dist = align.align_multiple([s1, s2, s3, s4], matrix)
# or, with MAFFT (needs the binary):
from biotite.application.mafft import MafftApp
msa = MafftApp.align([s1, s2, s3, s4], matrix=matrix)
```

## Ramachandran from a structure

```python
import numpy as np
phi, psi, omega = struc.dihedral_backbone(atoms[atoms.chain_id == "A"])
phi, psi = np.rad2deg(phi), np.rad2deg(psi)      # plot phi vs psi
```
