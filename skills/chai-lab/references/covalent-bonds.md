# Covalent bonds (glycans + custom ligand attachment)

Chai-1 supports atom-level covalent bond restraints. The two primary
use cases are:

1. **Glycosylation** — attach a sugar tree to an asparagine, serine,
   threonine, or hydroxylysine.
2. **Covalent ligand / inhibitor attachment** — attach a small molecule
   to a cysteine (or any residue) via a defined bond.

The mechanism is the same: a row in the restraints CSV with
`connection_type=covalent`.

## File format

Use the same restraints CSV from [restraints.md](restraints.md), with
`connection_type=covalent`. Distances (`min_distance_angstrom`,
`max_distance_angstrom`) and `confidence` are **ignored** for covalent
restraints — set them to `0` and `1.0` respectively.

The key difference: `res_idxA` and `res_idxB` carry an `@ATOMNAME`
suffix that names the atom on each side of the bond.

```
restraint_id,chainA,res_idxA,chainB,res_idxB,connection_type,confidence,min_distance_angstrom,max_distance_angstrom,comment
bond1,A,N437@N,B,@C1,covalent,1.0,0.0,0.0,protein-glycan
```

Breakdown:

- `A` — chain A (the protein, by FASTA order).
- `N437@N` — residue Asn at index 437, atom `N` (the side-chain amide
  nitrogen).
- `B` — chain B (the glycan; the second entity in the FASTA).
- `@C1` — the glycan has no "residue", just atoms; `@C1` is atom `C1`
  in the root sugar ring.

## Glycans

Glycans are written in the FASTA with abbreviated syntax (see
[inputs.md](inputs.md)). The bond from the protein to the root sugar is
expressed in the restraints CSV.

### Single-ring glycan on N436

FASTA:

```
>protein|name=p1
...N at position 436...

>glycan|name=g1
NAG
```

Restraint:

```csv
restraint_id,chainA,res_idxA,chainB,res_idxB,connection_type,confidence,min_distance_angstrom,max_distance_angstrom,comment
b1,A,N436@N,B,@C1,covalent,1.0,0.0,0.0,glyco
```

### Two-ring glycan (NAG-NAG)

```
>protein|name=p1
LPSSEEY... N437 ...

>glycan|name=g1
NAG(4-1 NAG)
```

The `(4-1 NAG)` syntax means: from atom `O4` of the preceding root
sugar to atom `C1` of the next sugar. Read **left-to-right** as
"building the glycan out from the root".

Bond to the protein:

```csv
restraint_id,chainA,res_idxA,chainB,res_idxB,connection_type,confidence,min_distance_angstrom,max_distance_angstrom,comment
b1,A,N437@N,B,@C1,covalent,1.0,0.0,0.0,
```

### Branched glycan

```
>glycan|name=branched
NAG(4-1 NAG(4-1 BMA(3-1 MAN)(6-1 MAN)))
```

Each `(<from>-<to> SUGAR)` block attaches to the sugar that immediately
precedes the parenthesis, building a tree. Multiple parentheses after
the same sugar create branches. Chain consecutive blocks to extend the
backbone.

### Leaving atoms

Sugar CCD reference conformers include hydroxyl groups (e.g. an `O4-H`)
that should leave when a bond is formed. Chai automatically removes
these for **sugar-ring CCD codes** via
`AllAtomStructureContext.drop_glycan_leaving_atoms_inplace`. You don't
have to do anything.

For **non-sugar ligands**, you must hand Chai a SMILES *without* the
leaving atom (see below).

## Non-glycan covalent ligands

To attach a small molecule covalently (e.g. a covalent inhibitor on a
cysteine), supply the ligand SMILES and a `covalent` restraint.

FASTA (modeled on 8CYO, a covalent inhibitor):

```
>protein|name=p1
MKK...C217...
>ligand|name=warhead
c1cc(c(cc1OCC(=O)NCCS)Cl)Cl
```

Restraint:

```csv
restraint_id,chainA,res_idxA,chainB,res_idxB,connection_type,confidence,min_distance_angstrom,max_distance_angstrom,comment
b1,A,C217@SG,B,@S1,covalent,1.0,0.0,0.0,covalent inhibitor
```

Notes:

- `C217@SG` — the SG sulfur of Cys217.
- `@S1` — atom `S1` in the ligand. To know the atom name, build the
  ligand with the **same RDKit version** Chai uses (`pip show rdkit`)
  and inspect: atom names follow RDKit's canonical naming for the
  SMILES you provide.
- **Strip the leaving atom from the SMILES**. If you intend to form a
  thioether by displacing a chloride from `c1...Cl`, the SMILES you
  hand Chai should already lack that chloride. (Or, more pragmatically,
  experiment.)

## Caveats

- **Intra-chain bonds (e.g. disulfides) are not supported** — Chai was
  not trained on them, and behaviour is undefined.
- **Modified amino acids with a CCD code go in the protein sequence in
  parentheses** (`RKDES(MSE)EES`), not as a covalent bond.
- **Atom-name typos are silent** — Chai logs and proceeds. Verify by
  inspecting the output CIF for the expected bond.
- **CCD codes ≠ SMILES for the same molecule** — CCD gives Chai a
  curated reference conformer; SMILES is built by RDKit on the fly.
  For known biologically-relevant ligands, prefer the CCD code unless
  you specifically need a custom protonation state or stereochemistry.
- See `tests/test_glycans.py` in the repo for more examples of the
  glycan syntax.
