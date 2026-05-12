# FASTA-like input format

Chai-1 accepts a single FASTA file describing **every chain and ligand**
in the complex. Each record has a header of the form:

```
>ENTITY_TYPE|name=ENTITY_NAME
```

where:

- `ENTITY_TYPE` is one of `protein`, `ligand`, `dna`, `rna`, `glycan`.
- `ENTITY_NAME` is a string unique across the whole file. The `name=`
  prefix is optional (`>protein|my_chain` also works).

The body is the entity's sequence — interpretation depends on the type.

## Entity types

### `protein`

Standard one-letter amino acid codes (`ACDEFGHIKLMNPQRSTVWY`). To
include a modified residue with a known CCD code, embed the 3-letter
CCD code in parentheses *in place of* the canonical residue:

```
>protein|name=p1
RKDES(MSE)EES                # selenomethionine at position 6
```

This is the right way to spell modified amino acids that already have a
CCD code (MSE, SEP, TPO, PTR, …). Do **not** use a covalent-bond
restraint for these.

For homo-oligomers, list the chain multiple times with different names:

```
>protein|name=chainA
MKVLW...
>protein|name=chainB
MKVLW...
```

### `ligand`

A SMILES string **or** a 3-letter CCD code. SMILES is preferred for
novel small molecules; CCD codes give Chai a known reference conformer.

```
>ligand|name=ATP
Nc1ncnc2n(cnc12)C1OC(COP(O)(=O)OP(O)(=O)OP(O)(O)=O)C(O)C1O

>ligand|name=NAG_as_ccd
NAG
```

Ligands are tokenised **per heavy atom**, so a 100-atom natural product
consumes ~100 tokens of the 2048-token budget. Plan accordingly.

### `dna`, `rna`

One-letter nucleotide sequences:

```
>dna|name=top_strand
ATCGGCTA
>dna|name=bottom_strand
TAGCCGAT

>rna|name=guide
GGCAUGCAUC
```

### `glycan`

Abbreviated glycan syntax — a string of 3-letter sugar CCD codes joined
by `(<from_atom>-<to_atom> <next_sugar>…)` blocks. The leftmost sugar
is the root.

```
>glycan|name=single
NAG

>glycan|name=linear
NAG(4-1 NAG)                              # 4 of NAG-1 bound to 1 of NAG-2

>glycan|name=four_in_a_row
NAG(4-1 NAG(4-1 NAG(4-1 NAG)))

>glycan|name=branched
NAG(4-1 NAG(4-1 BMA(3-1 MAN)(6-1 MAN)))
```

The protein–glycan bond is **not** in the FASTA — specify it in the
restraints CSV with `connection_type=covalent`. See
[covalent-bonds.md](covalent-bonds.md).

## Multiple chains and complexes

Just keep stacking records:

```
>protein|name=heavy
QVQLVE...
>protein|name=light
DIQMTQ...
>protein|name=antigen
MASIYRG...
>ligand|name=cofactor
CCN(CC)CC
```

Chains in the output CIF are labelled `A, B, C, …` in this order. If you
want the CIF chain ID to equal the `name=` field, pass
`--fasta-names-as-cif-chains` and make every name a single valid PDB
chain character (`A–Z`, `a–z`, `0–9`).

## Validation

Chai validates:

- Entity names are unique → else `UnsupportedInputError`.
- For protein/DNA/RNA, the sequence is plausibly that entity type
  (warning, not fatal — a DNA-looking string in a `protein` record
  logs a warning).
- Total token count ≤ 2048 → else `UnsupportedInputError`.

## Worked example: antibody–antigen + cofactor

```
>protein|name=antigen
MASIYR...

>protein|name=heavy
QVQLVE...

>protein|name=light
DIQMTQ...

>ligand|name=FAD
[FAD-SMILES]
```

Chains will be assigned `A=antigen`, `B=heavy`, `C=light`, `D=FAD`. A
restraint asserting that the antibody binds antigen residue `E152`
would reference:

```
A,E152,B,,pocket,1.0,0.0,5.5,epitope,r1
```

(see [restraints.md](restraints.md)).

## Worked example: glycosylated protein

```
>protein|name=p1
LPSSEEY...N437...N445...

>glycan|name=g1
NAG(4-1 NAG)

>glycan|name=g2
NAG
```

with bonds in `bonds.restraints`:

```csv
chainA,res_idxA,chainB,res_idxB,connection_type,confidence,min_distance_angstrom,max_distance_angstrom,comment,restraint_id
A,N437@N,B,@C1,covalent,1.0,0.0,0.0,glyco1,b1
A,N445@N,C,@C1,covalent,1.0,0.0,0.0,glyco2,b2
```

See [covalent-bonds.md](covalent-bonds.md) for atom-naming details.
