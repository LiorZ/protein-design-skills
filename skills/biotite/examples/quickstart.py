#!/usr/bin/env python
"""
Biotite quickstart — fetch, load, select, analyze, compare, save.

Runnable end-to-end (needs internet for the RCSB fetch):
    pip install biotite
    python quickstart.py

Each block is independent enough to copy out on its own.
"""

import numpy as np

import biotite.database.rcsb as rcsb
import biotite.structure as struc
import biotite.structure.io as strucio
import biotite.structure.io.pdbx as pdbx


# --- 1) Fetch a structure from the RCSB PDB ----------------------------------
# BinaryCIF (.bcif) is the smallest/fastest representation.
path = rcsb.fetch("1AKI", "bcif", target_path="/tmp")
print("fetched:", path)


# --- 2) Load it -------------------------------------------------------------
# Shortcut (format inferred from extension); model=1 -> a single AtomArray.
structure = strucio.load_structure(path)
print("atoms:", structure.array_length(), "| chains:", np.unique(structure.chain_id))

# Explicit File layer when you need bonds / extra fields / assemblies:
f = pdbx.BinaryCIFFile.read(path)
structure = pdbx.get_structure(
    f, model=1, extra_fields=["b_factor"], include_bonds=True
)


# --- 3) Select via boolean masks over annotation arrays ----------------------
protein = structure[struc.filter_amino_acids(structure)]
ca = protein[(protein.atom_name == "CA") & (protein.chain_id == "A")]
print("chain-A residues:", ca.array_length())

ligands = structure[
    structure.hetero
    & ~struc.filter_solvent(structure)
    & ~struc.filter_monoatomic_ions(structure)
]
print("ligand atoms:", ligands.array_length())


# --- 4) Analyze -------------------------------------------------------------
sasa = struc.sasa(structure)                       # per-atom, Å² (NaN for some hetero)
print("total SASA (protein heavy):",
      np.nansum(sasa[struc.filter_amino_acids(structure)]))

sse = struc.annotate_sse(protein)                  # per-residue: 'a' / 'b' / 'c'
print("helix residues:", int(np.sum(sse == "a")),
      "| strand:", int(np.sum(sse == "b")))

phi, psi, omega = struc.dihedral_backbone(protein)  # radians; NaN at termini
print("phi/psi computed for", np.sum(~np.isnan(psi)), "residues")


# --- 5) Compare two structures (the design-validation step) ------------------
# Here we just compare chain A to itself rotated, to show the API. In practice
# `design` is your designed/native backbone and `pred` is a Boltz/Chai/Protenix
# /AlphaFold prediction, each filtered to matching CA atoms.
design = ca
pred = struc.rotate(ca.copy(), [0.1, 0.0, 0.0])     # pretend prediction
fitted, transform = struc.superimpose(design, pred)
idx = np.arange(design.array_length())              # design & pred already correspond 1:1
print("RMSD:", round(float(struc.rmsd(design, fitted)), 3))
# tm_score needs the corresponding atom indices in each structure:
print("TM-score:", round(float(struc.tm_score(design, fitted, idx, idx)), 3))
print("lDDT:", round(float(struc.lddt(design, pred)), 3))


# --- 6) Save back out (writer inferred from extension) -----------------------
strucio.save_structure("/tmp/1aki_chainA_ca.pdb", ca)
print("wrote /tmp/1aki_chainA_ca.pdb")


# --- 7) A little sequence work ----------------------------------------------
import biotite.sequence as seq
import biotite.sequence.align as align

s1 = seq.ProteinSequence("MKTAYIAKQR")
s2 = seq.ProteinSequence("MKTAYIAKER")
matrix = align.SubstitutionMatrix.std_protein_matrix()      # BLOSUM62
aln = align.align_optimal(s1, s2, matrix, gap_penalty=(-10, -1))[0]
print("identity:", round(align.get_sequence_identity(aln), 3))
print(aln)
