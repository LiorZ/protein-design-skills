# Output PDBs — structure and downstream consumption

## Filename

```
<prefix><RES1>_<RES2>_..._<setno>_<index><suffix>.pdb
```

- `prefix` and `suffix` are from `--prefix` / `--suffix`. The suffix
  is formatted as `_<suffix>` internally (so `--suffix HHE` produces
  `..._HHE.pdb`).
- `<RES1>_<RES2>_...` lists the catalytic residues in CST order:
  - canonical AAs → one-letter code (`H`, `E`, `S`, `Y`, ...)
  - ligands / non-canonicals → three-letter `name3()` (e.g. `BIO`)
  - motif residues → basename of the motif PDB without `.pdb`
- `<setno>` is the non-redundant rotamer-set index (1-based), from
  `TheozymeInvrotTree.collect_all_inverse_rotamers()`. CSTs that span
  multiple `VARIABLE_CST` alternatives create more than one
  rotamer set.
- `<index>` is the position of this combination within that set's
  `itertools.product`.

Examples (from the Kemp_eliminase run):

```
outputs/H_E_S_1_42_HHE.pdb   ← HIS + GLU + SER, set 1, combo 42
outputs/H_D_T_1_117_HHE.pdb  ← HIS + ASP + THR, set 1, combo 117
outputs/H_E_Y_2_3_HHE.pdb    ← HIS + GLU + TYR (different VARIABLE_CST branch), set 2
```

If the same filename already exists, the script attempts
`name.replace(".pdb", "a.pdb")` — note this is **buggy** (`str.replace`
is not in-place; the return value is discarded). In practice the file
will be overwritten silently. Use `--suffix` to disambiguate runs.

## PDB contents

```
HEADER                                          ...
REMARK 666 MATCH TEMPLATE X BIO    0 MATCH MOTIF A HIS    5  1  1
REMARK 666 MATCH TEMPLATE A HIS    5 MATCH MOTIF B GLU    5  2  1
REMARK 666 MATCH TEMPLATE X BIO    0 MATCH MOTIF C SER    5  3  1
ATOM      1  N   ALA A   1   ...
...
TER
ATOM    ... HIS A   5   ...
...
TER
ATOM    ... ALA B   1   ...
... GLU B   5 ...
TER
... SER C   5 ...
TER
HETATM    ... BIO X   0 ...
END
```

Layout:

- One `REMARK 666 MATCH TEMPLATE … MATCH MOTIF …` line per catalytic
  CST (excluding the ligand-as-self constraint). Order = CST order.
- Each catalytic residue lives on **its own chain**, with the
  catalytic residue at position `N_len_per_cst[j] + 1` (i.e. centred
  within the stub). When `N_len=4` and `C_len=5`, the stub is 10
  residues long and the catalytic residue is at chain-position 5.
- The ligand is the **last chain**. When there is exactly one ligand,
  the REMARK 666 line refers to it as `chain X residue 0` (the
  matcher/enzdes convention). Multi-ligand outputs reference the
  ligand by its actual in-pose chain and seqpos.
- Output is generated via `pyrosetta.distributed.io.to_pdbstring(pose)`
  and re-emitted with the REMARK lines inserted immediately after
  the HEADER.

## REMARK 666 — the enzdes header

Format:

```
REMARK 666 MATCH TEMPLATE <ds_chain> <ds_name3> <ds_resno> MATCH MOTIF <us_chain> <us_name3> <us_resno> <cst_no> <mcfi_no>
```

| Field | Meaning |
|-------|---------|
| `ds_chain`, `ds_name3`, `ds_resno` | "Downstream" residue: usually the ligand. For residue-residue CSTs (e.g. CST 2 in Kemp = GLU on HIS) the downstream is the upstream-CST residue. |
| `us_chain`, `us_name3`, `us_resno` | "Upstream" residue: the catalytic residue placed by this CST. |
| `cst_no` | 1-indexed CST block number (matches the CST file). |
| `mcfi_no` | Index into the variable CST list — which alternative in `VARIABLE_CST::BEGIN…END` was matched. |

If the script cannot reconstruct a REMARK for *any* CST in the
assembly, the entire PDB is **discarded** (`len(remarks) != len(catres_resnos)-1`
check at `invrotzyme.py:179`). Common cause: the CST file specifies
atoms in a way that doesn't match any of the rotamer's atom names —
inspect with `--debug` for traceability.

## Verifying outputs

Quick sanity-check pattern:

```bash
# How many assemblies?
ls outputs/*.pdb | wc -l

# Every output should have N-1 REMARK 666 lines, where N = number of CST blocks + ligand
grep -c "^REMARK 666" outputs/*.pdb | head

# Re-load in PyRosetta with enzdes constraints applied:
python -c '
import pyrosetta as pyr
pyr.init("-extra_res_fa lig.params -enzdes::cstfile my.cst")
pose = pyr.pose_from_file("outputs/H_E_S_1_1_HHE.pdb")
addcst = pyr.rosetta.protocols.enzdes.AddOrRemoveMatchCsts()
addcst.set_cst_action(pyr.rosetta.protocols.enzdes.CstAction.ADD_NEW)
addcst.apply(pose)
print("constraints applied OK")
'
```

If `addcst.apply(pose)` raises about missing or mis-aligned constraints,
the REMARK lines are likely inconsistent with the CST file. This is
the gating check for downstream Rosetta enzdes work.

## Downstream consumers

| Consumer | What it wants |
|----------|---------------|
| **RFdiffusionAA** (via [heme_binder_diffusion](https://github.com/ikalvet/heme_binder_diffusion)) | Reads the REMARK 666 lines to know which residues are catalytic. Uses the ligand + catalytic residues as conditioning for backbone generation; discards the idealized stubs (so `--N_len 0 --C_len 0` is also a valid input). |
| **Rosetta `enzdes`** | Uses REMARK 666 to recreate `AtomPair`/`Angle`/`Dihedral` constraints on the loaded pose. Requires `-extra_res_fa <params>` and the same CST file. |
| **LigandMPNN** (sequence design) | Treats the ligand as a fixed conditioning. Catalytic residues should typically be fixed via the `fix_pos` flag — extract them from the REMARK 666 lines. |
| **AF2 / Chai / Boltz refold** | Ignores the REMARK lines; only consumes the polypeptide sequence and ligand SMILES / CCD. Don't expect refolders to know about the catalytic motif unless you condition on it explicitly. |

## When a run produces *no* outputs

Likely causes, in decreasing order:

1. **CST 1 doesn't define all six DOFs** → empty rotamer set; the loop
   over `all_inverse_rotamers_per_cst` runs but every set's pool is
   empty.
2. **`--dunbrack_prob` is too tight** (e.g. `0.3`) and no rotamers
   survive → check the per-CST "after filtering" line in stdout.
3. **`--frac_random_rotamers_per_cst 0.0`** for the ligand → kills
   the entire enumeration.
4. **Mutual clashes are unavoidable for the geometry you've defined**
   — relax CST tolerances or shorten stub lengths.
5. **REMARK reconstruction failure** — every assembly is being built
   but discarded. Run with `--debug` on a small subset; look for
   `"Could not build all REMARK 666 lines"` in the output.
