# Restraints (contact / pocket)

Chai-1 uniquely supports user-supplied **inter-chain restraints** that
guide complex assembly. Pass a CSV via `--constraint-path FILE` (or
`constraint_path=Path("...")` in Python). One file can mix contact,
pocket, and covalent restraints (the last is documented in
[covalent-bonds.md](covalent-bonds.md)).

## Why use restraints

Without restraints, Chai sometimes predicts plausible-looking interfaces
in the wrong place. On the antibody–virus structure 7SYZ, providing
just **two** randomly selected residue-residue contacts taken from the
ground-truth interface lifts interface DockQ from ~0.02 to ~0.40 for
the antibody-light interface (and similarly for antibody-heavy). See
the original example results in
[the Chai restraints docs](https://github.com/chaidiscovery/chai-lab/blob/main/examples/restraints/README.md).

Use restraints whenever you have *external* knowledge of an interface:
crosslinking, mutagenesis, NMR, HDX-MS, epitope mapping, prior
literature, or partial cryo-EM.

## File format

CSV with these columns (header row required):

```
restraint_id,chainA,res_idxA,chainB,res_idxB,connection_type,confidence,min_distance_angstrom,max_distance_angstrom,comment
```

Field reference:

| Field | Required for | Format | Meaning |
|-------|--------------|--------|---------|
| `restraint_id` | all | unique string | Free-form ID, must be unique within file |
| `chainA` | all | `A`,`B`,`C`,…  | First chain (alphabetical position in FASTA) |
| `res_idxA` | contact, covalent | `<RES><1-based-index>` e.g. `D4`, `N437@N` | Residue + index; for covalent, suffix `@ATOM` |
| `chainB` | all | `A`,`B`,`C`,… | Second chain |
| `res_idxB` | contact, covalent | as above | For pocket leave **`chainA`'s** index empty |
| `connection_type` | all | `contact` \| `pocket` \| `covalent` | See below |
| `confidence` | all | float 0–1 | Currently **unused** by the model (future-proofing) |
| `min_distance_angstrom` | all | float | Currently **unused** by the model |
| `max_distance_angstrom` | contact, pocket | float (Å) | Upper bound on how far apart the two sites are expected to be |
| `comment` | all | free string | Human-readable, ignored by the model |

### Contact restraint

Both residues fully specified. Restraint applies to a single
residue pair across two chains.

```csv
restraint_id,chainA,res_idxA,chainB,res_idxB,connection_type,confidence,min_distance_angstrom,max_distance_angstrom,comment
r0,A,C387,B,Y101,contact,1.0,0.0,5.5,heavy-chain epitope
r1,C,I32,A,S483,contact,1.0,0.0,5.5,light-chain epitope
```

### Pocket restraint

A whole chain is constrained to be in contact with a specific residue
in another chain. **Asymmetric**: leave `res_idxA` empty.

```csv
restraint_id,chainA,res_idxA,chainB,res_idxB,connection_type,confidence,min_distance_angstrom,max_distance_angstrom,comment
r0,B,,A,C387,pocket,1.0,0.0,5.5,heavy near C387
r1,C,,A,S483,pocket,1.0,0.0,5.5,light near S483
```

Coarser than `contact`; useful when you know the binding region but not
the exact contact residue.

### Covalent restraint

See [covalent-bonds.md](covalent-bonds.md). In short: atom-level,
`@ATOMNAME` suffix on `res_idxA`/`res_idxB`, distances ignored.

## Indexing rules

- **1-based indexing.** The first residue in a chain is index 1.
- **`res_idx` carries both the letter and the index**: `D4` =
  "the 4th residue, which had better be Asp". Chai cross-checks the
  letter against the FASTA sequence and raises on mismatch. This
  catches most off-by-one bugs.
- **Chain letters come from FASTA order**, not entity names. The first
  entity is `A`, second is `B`, etc., regardless of `name=` field.
  Override by passing `--fasta-names-as-cif-chains` (then `name=` must
  itself be a valid single-char chain ID, and is used as the chain
  label here).

## Worked example: 7SYZ-style antibody/antigen

FASTA (chain order: antigen, heavy, light):

```
>protein|7SYZ_1_prot
MMADSKLVSLNNNL... S483 ...C387...
>protein|7SYZ_2_heavy
QIQLVQSGPELKKPGE...
>protein|7SYZ_3_light
DVLMIQTPLSLPVSL...
```

Contact restraints CSV:

```csv
restraint_id,chainA,res_idxA,chainB,res_idxB,connection_type,confidence,min_distance_angstrom,max_distance_angstrom,comment
restraint_1,A,C387,B,Y101,contact,1.0,0.0,5.5,protein-heavy
restraint_2,C,I32,A,S483,contact,1.0,0.0,5.5,protein-light
```

Pocket variant:

```csv
restraint_id,chainA,res_idxA,chainB,res_idxB,connection_type,confidence,min_distance_angstrom,max_distance_angstrom,comment
restraint_0,B,,A,C387,pocket,1.0,0.0,5.5,protein-heavy
restraint_1,C,,A,S483,pocket,1.0,0.0,5.5,protein-light
```

Run:

```bash
chai-lab fold --constraint-path contacts.csv input.fasta out/
```

## Tips

- Mix-and-match `contact` and `pocket` rows in a single file.
- Two or three high-quality contacts usually beat ten weak ones.
- `max_distance_angstrom` of 5.5 Å is a tight contact; 8–10 Å is
  "neighbourhood"; 20–22 Å is "same interface". Use looser bounds when
  the input information is fuzzy.
- For homo-oligomers, restrain symmetric interfaces explicitly — Chai
  won't infer the symmetry from a single restraint.
- Restraints are an **input**, not a hard constraint — Chai is biased,
  not forced. If you see ipTM dropping after adding a restraint, it
  probably means the restraint is incompatible with the structure Chai
  wants to predict.
