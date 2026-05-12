# Using external motifs (`--motif_for_cst`)

By default invrotzyme enumerates inverse rotamers for every CST. The
`--motif_for_cst` flag replaces the enumerated rotamers for one CST
with a residue copied from a user-supplied PDB. Typical use case:
seating the catalytic CYS of a cytochrome P450 onto a real CYS loop
extracted from a P450 crystal structure, while the rest of the
catalytic residues are still searched by invrotzyme.

## Input format

```
--motif_for_cst <CSTNO>:<RESNO_IN_MOTIF>:<PATH/TO/MOTIF.pdb> [...]
```

Each entry is a colon-delimited triple; multiple motifs are
space-separated. Fields:

| Field | Meaning |
|-------|---------|
| `CSTNO` | The CST block (1-indexed) to replace. **Currently only `1` is supported.** Other values cause `sys.exit("External motif not supported for not-first CST's right now.")`. |
| `RESNO_IN_MOTIF` | The residue number (1-indexed) inside the motif PDB that should be used as the catalytic residue. |
| `PATH` | Path to the motif PDB. Loaded with `pyrosetta.pose_from_file`. |

The script asserts that the motif residue's `name3()` matches one of
the allowed restypes for that CST. So if your CST 1 declares
`residue1: C` (i.e. cysteine), the motif residue at `RESNO_IN_MOTIF`
must be `CYS`.

## What the script does with the motif

1. Loads the motif PDB once.
2. Identifies the CST atoms that correspond to the motif residue's
   restype from the CST's `MatcherConstraintFileInfo`.
3. For each catalytic-tip placement that other CSTs / inverse-rotamer
   enumeration produces, **aligns the motif pose** onto the catalytic
   atoms via Kabsch (`align_pdbs.align_pose_to_residue`).
4. The motif pose is then concatenated into the assembly *as a chain*,
   replacing what would have been the short idealized stub for that
   CST.
5. Clash check happens normally — including against the motif's
   backbone.

The motif pose preserves whatever backbone you supply, so:

- The output PDB for that CST will reflect the motif backbone, not an
  idealized helix or strand.
- `--N_len_per_cst` / `--C_len_per_cst` for the motif CST are ignored
  in practice — the motif pose is appended directly without stub
  extension.
- If the motif's backbone clashes with another catalytic residue or
  ligand, you'll see the debug message
  `"MOTIF POSE SEEMS TO GIVE CLASH!!!! PLEASE INVESTIGATE!!!"` and
  that combination is discarded. (Unlike rotamer clashes, motif
  failures are *not* added to the bad-rotamer cache — they're
  expected to be rare and worth manual inspection.)

## Output naming

For motif CSTs the filename component derives from the motif PDB's
basename (without `.pdb`), not from the residue letter. So a motif
loaded as `P450_motif.pdb` will show up in filenames as `P450_motif_`.

## Worked example (P450)

```bash
python invrotzyme.py \
  --cstfile inputs/HBA_CYS_P450_nosample.cst \
  --params  inputs/HBA_unique.params \
  --motif_for_cst 1:3:inputs/P450_motif.pdb \
  --frac_random_rotamers 0.1 \
  --prefix outputs/
```

- CST 1 in `HBA_CYS_P450_nosample.cst` constrains the catalytic CYS
  to the heme Fe.
- `inputs/P450_motif.pdb` is a small CYS loop extracted from a P450
  crystal structure; the catalytic CYS is residue 3 of that PDB.
- The remaining CSTs (which constrain a substrate or cofactor against
  the heme) are enumerated normally, then aligned against the
  motif-anchored heme placement.

## Limitations and footguns

- **Only CST 1 is supported.** The `parse_motif_input` function
  explicitly exits if you try anything else. If you need to fix a
  different CST, manually rearrange your CST file so the desired
  fixed residue is CST 1.
- **The motif must contain only one chain in practice.** The script
  loads the entire motif PDB into a pose and appends it to the
  assembly — multiple chains will all be included.
- **Motif residue numbering is 1-indexed and counts every residue in
  the motif PDB**, not PDB-author numbering. Use `pose.pdb_info()`
  semantics: residue 1 is whatever comes first in the file.
- **The motif's CST atoms are auto-discovered** from the
  `MatcherConstraintFileInfo` for the matching restype. If your CST
  defines the catalytic residue by `atom_type` rather than by
  `atom_name`, all matching atoms could be considered — pick a
  motif residue whose chemistry is unambiguous.
- **Per-CST flag lengths still include the motif slot.** Even if you
  fix CST 1 with a motif, you still need to provide
  `--secstruct_per_cst`, `--N_len_per_cst`, etc. for *all* CSTs —
  the motif slot's values are simply ignored.
