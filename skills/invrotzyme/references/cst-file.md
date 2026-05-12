# CST file format for invrotzyme

InvrotZyme reads the standard Rosetta matcher / enzdes constraint
format. Full canonical reference:
<https://docs.rosettacommons.org/docs/latest/rosetta_basics/file_types/match-cstfile-format>.

This page lists only the **invrotzyme-specific** requirements and shows
an annotated example.

## Hard requirements

1. **All six DOFs per CST block.** Every constraint block must define:
   `distanceAB`, `angle_A`, `angle_B`, `torsion_A`, `torsion_AB`,
   `torsion_B`. PyRosetta's `TheozymeInvrotTree` will not generate
   inverse rotamers otherwise.
2. **Use `VARIABLE_CST::BEGIN … VARIABLE_CST::END`** to declare
   alternative residue types at the same slot (e.g. SER/THR/TYR/ASN/GLN
   in an oxyanion hole).
3. **The first CST block conventionally targets the ligand.** Downstream
   code paths (REMARK 666 generation, the single-ligand shortcut) make
   stronger assumptions about CST 1 — keep your primary
   ligand-contacting residue there.
4. **Keep CST-level sampling MINIMAL.** Every `_n_samples > 0` entry in
   a DOF line multiplies the rotamer-set size. Prefer to widen the
   rotamer search with `--extra_chi*` (deterministic, per-χ control)
   over CST-level `_n_samples` (combinatorially expensive).
5. **`SECONDARY_MATCH: UPSTREAM_CST N`** and `SECONDARY_MATCH: DOWNSTREAM`
   are honored by the REMARK-666 reconstruction logic. Without them the
   downstream-residue lookup defaults to CST 0 (the ligand), which is
   correct for direct ligand contacts but wrong for residue-residue
   constraints like a HIS-ED dyad.

## Annotated Kemp eliminase example

The repo's `examples/Kemp_eliminase/inputs/BIO_His_ED_oxy_nosample.cst`
defines three CSTs:

### CST 1 — HIS base contacts the substrate

```
CST::BEGIN
  TEMPLATE::   ATOM_MAP: 1 atom_name: C7 N1 O1     ← BIO ligand atoms
  TEMPLATE::   ATOM_MAP: 1 residue3:  BIO          ← ligand restype
  TEMPLATE::   ATOM_MAP: 2 atom_type: Nhis         ← HIS Nε / Nδ
  TEMPLATE::   ATOM_MAP: 2 residue1: H             ← H = histidine
  CONSTRAINT:: distanceAB:    2.68   0.15  100.   1   0
  CONSTRAINT::    angle_A:   125.8   5.0  100.0  360. 0
  CONSTRAINT::    angle_B:   114.7   5.0   75.0  360. 0
  CONSTRAINT::  torsion_A:   180.0   5.0   75.0  360. 0
  CONSTRAINT:: torsion_AB:    58.5  45.0    0.0   90. 0
  CONSTRAINT::  torsion_B:   180.0   5.0   25.0  360. 0
CST::END
```

Note: `atom_type: Nhis` matches **either** Nε *or* Nδ (HIS vs HIS_D
tautomer). Use `--keep_his_tautomer '1:HIS'` or `'1:HIS_D'` on the
invrotzyme CLI to pin one.

### CST 2 — GLU/ASP activating the HIS

```
CST::BEGIN
  TEMPLATE::   ATOM_MAP: 1 atom_type: Ntrp         ← HIS nitrogen
  TEMPLATE::   ATOM_MAP: 1 residue3:  HIS          ← upstream residue is from CST 1
  TEMPLATE::   ATOM_MAP: 2 atom_type: OOC          ← carboxylate oxygens
  TEMPLATE::   ATOM_MAP: 2 residue1: ED            ← E or D
  CONSTRAINT::  …six DOFs…
  ALGORITHM_INFO:: match
     SECONDARY_MATCH: UPSTREAM_CST 1               ← key directive
  ALGORITHM_INFO::END
CST::END
```

`SECONDARY_MATCH: UPSTREAM_CST 1` tells the REMARK-666 generator that
the *downstream* residue for CST 2 is the residue placed by CST 1
(the HIS), not the ligand.

### CST 3 — VARIABLE_CST for the oxyanion hole

```
VARIABLE_CST::BEGIN
  CST::BEGIN  …residue1: ST  …             ← SER or THR via OH atom_type
    SECONDARY_MATCH: DOWNSTREAM
  CST::END
  CST::BEGIN  …residue3: TYR … atom_name: OH CZ CE2 …
    SECONDARY_MATCH: DOWNSTREAM
  CST::END
  CST::BEGIN  …residue1: NQ  …atom_type: NH2O…
    SECONDARY_MATCH: DOWNSTREAM
  CST::END
VARIABLE_CST::END
```

`SECONDARY_MATCH: DOWNSTREAM` means CST 3's downstream residue is the
*ligand* (CST 0 in invrotzyme's numbering), not the HIS or the
carboxylate.

For this 3-CST file you would pass three per-CST values for the
geometry flags:

```
--secstruct_per_cst H H E
--N_len_per_cst    4 4 4
--C_len_per_cst    5 5 5
```

…and **four** for the rotamer-count flags (ligand + 3 CSTs):

```
--frac_random_rotamers_per_cst 0.5 0.5 0.5 0.5
```

## Common authoring mistakes

- Missing one of the six DOFs (especially `torsion_B`) → CST won't
  expand into rotamers; the corresponding pool will be empty and the
  whole rotamer set is skipped.
- Per-CST argument length off by one → caused by forgetting the
  rotamer-count flags include the ligand. Read the assertion error.
- Asking for `_n_samples > 0` on every DOF of every CST → the
  Cartesian product blows up. Sample minimally; widen with
  `--extra_chi*`.
- `residue1: H` with `atom_type: Nhis` *plus* a HIS tautomer not pinned
  → both tautomers are enumerated, doubling the rotamer pool. Use
  `--keep_his_tautomer` when the chemistry dictates one.
- Referencing a ligand `name3` that isn't in your `.params` file →
  PyRosetta will fail to load the residue type.
