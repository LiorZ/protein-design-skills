# Inputs — formats, selectors, ligand references, custom residues

## The cardinal rule

**The molecule(s) you want PLACER to predict must already be present, with 3D
coordinates, in the input PDB/mmCIF.** PLACER denoises/rebuilds atoms that are
already there. It cannot:

- take an apo protein + a free SMILES/SDF and produce a docked pose,
- introduce a ligand that has no coordinates in the input.

`--ligand_file ...SDF/MOL2` does **not** supply coordinates — it only refines
atom typing and bond perception for a ligand whose coordinates already come from
the PDB/mmCIF. (FAQ #8 upstream.)

If you only have a SMILES and an apo pocket, first place the ligand with a
docking tool (Vina/GNINA/SigmaDock) or a co-folding model (`boltz`/`chai-lab`),
then hand the resulting complex to PLACER for refinement/scoring.

## Accepted file formats

| Format | Notes |
|--------|-------|
| `.pdb`, `.ent` | The most robust general input. Rosetta-generated PDBs work well. |
| `.cif`, `.cif.gz` | Parsed correctly **only for RCSB-formatted mmCIF**. mmCIF emitted by AF2/AF3/Boltz/Chai often differs in formatting and may fail. |

### PDB vs. CIF chain caveat

For **PDB** input, a ligand must **not** share a chain letter with the protein —
this raises an `AssertionError`. RCSB **mmCIF** handles ligand chains
differently and parses cleanly. (See the upstream API example: `3rgk.pdb` fails,
`3rgk.cif` succeeds for the same myoglobin+heme structure.) If your PDB puts the
ligand on the protein's chain, either renumber it onto its own chain or convert
to RCSB-style mmCIF.

### Structures from other predictors

AF/Boltz/Chai outputs frequently cause trouble: missing hydrogens (especially on
ligands) and non-RCSB mmCIF formatting. Prefer RCSB mmCIF or a clean PDB. Also
respect the upstream licenses of those tools when reusing their outputs for
docking.

## Selector syntax

Ligands and residues are addressed by combinations of **chain letter**,
**3-letter code (`name3`)**, and **residue number**:

| Context | Form | Example |
|---------|------|---------|
| `--predict_ligand`, `--fixed_ligand` | `name3` / `name3-resno` / `chain-name3-resno` | `HEM`, `LDP-501`, `D-LDP-501` |
| `--target_res` | `chain-resno` / `chain-name3-resno` | `A-149`, `A-HIS-149` |
| `--mutate` | `resno+chain:name3` | `128A:75I`, `5A:TRP` |
| `--bonds` | `chain-resno-name3-atom:chain-resno-name3-atom:len` | `A-42-ALA-CB:B-173-JRP-CL:1.8` |
| `--crop_centers`, `--corruption_centers` | `chain-resno-name3-atom` | `B-200-HEM-FE` |

Use the most specific form when chain letters or `name3` codes repeat in the
structure.

## `--ligand_file` — refining atom typing / bonding

```
--ligand_file HEM:HEM.mol2 LDP:inhibitor.sdf
--ligand_file HEM:CCD              # read HEM from PLACER's internal CCD DB
```

Use this when PLACER mis-assigns hybridization/bonds from PDB coordinates alone
— the classic symptom is **non-planar aromatic rings** (FAQ #10). Supplying a
correct SDF/MOL2 (or `name3:CCD`) fixes the chemistry; coordinates still come
from the input structure.

In the Python API the equivalent is
`pl_input.ligand_reference({"HEM": "HEM.mol2", "LDP": "CCD"})`.

## Non-canonical / custom residues — the residue JSON

To predict with a residue that isn't a standard amino acid or known CCD ligand
(including the target of a `--mutate`), register it via `--residue_json file.json`
(API: `pl_input.add_custom_residues(dict)`).

Schema — a dict keyed by `name3`:

```json
{
  "75I": {
    "sdf": "<contents of the SDF file as a single string>",
    "atom_id": ["N", "CA", "C", "O", "CB", "..."],
    "leaving": [false, false, false, false, false, "..."],
    "pdbx_align": [0, 0, 0, 0, 0, "..."]
  }
}
```

| Key | Meaning |
|-----|---------|
| `sdf` | The full SDF file (correct bonding + chirality) as one string. |
| `atom_id` | Atom names exactly as they appear in the PDB, in the **same order** as atoms in the SDF. |
| `leaving` | Per-atom `true`/`false` — `true` for atoms deleted when the residue is part of a polymer (e.g. backbone-amide H, carboxylate `OXT`). |
| `pdbx_align` | Per-atom int list (length = #atoms). Can be all zeros — it only mattered to the mmCIF writer and does not affect PLACER. |

A worked example file ships in the upstream repo at
`examples/ligands/75I.json` (and inside the SIF at
`/opt/PLACER/examples/ligands/75I.json`), used by the `--mutate 128A:75I`
example.

## Bundled example inputs (inside the SIF)

`/opt/PLACER/examples/inputs/`:

| File | Description |
|------|-------------|
| `4dtz.cif` | P450 with heme + dopamine inhibitor (LDP). Docking demo. |
| `3rgk.cif` / `3rgk.pdb` | Myoglobin + heme. The `.pdb`/`.cif` pair illustrates the chain-letter caveat. |
| `dnHEM1.pdb` | De novo heme-binding protein (holo). |
| `dnHEM1_apo.pdb` | Same, apo — for sidechain prediction with `--target_res`. |
| `denovo_SER_hydrolase.pdb` | De novo serine hydrolase — non-canonical `--mutate` demo. |

`/opt/PLACER/examples/ligands/`: `HEM.mol2`, `75I.json`.
