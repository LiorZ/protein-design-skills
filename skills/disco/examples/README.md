# DISCO example inputs

Ready-to-use input JSONs covering every supported DISCO use case. Copy a
file to `~/Repos/DISCO/input_jsons/` (or pass its absolute path) and
invoke the runner.

Each example assumes the DISCO repo is at `~/Repos/DISCO`. `FILE_`
paths resolve relative to that root.

## Quick reference

| File | Use case | Recommended invocation |
|------|----------|------------------------|
| `unconditional_sweep.json` | De novo backbones at multiple lengths (50–300), no conditioning | `experiment=designable effort=fast seeds=\[0..49\]` |
| `ligand_smiles.json` | Binder for a small molecule given as SMILES (aspirin) | `experiment=diverse effort=max seeds=\[0..4\]` |
| `ligand_sdf.json` | Binder for a ligand given as an SDF file (heme B) | `experiment=diverse effort=max seeds=\[0..4\]` |
| `ligand_ccd.json` | Binder for CCD-coded ligands (ATP and a glycan) | `experiment=diverse effort=max seeds=\[0..4\]` |
| `ion_metal.json` | Metal / metallocluster binders (Fe + SF4, Zn) | `experiment=diverse effort=max seeds=\[0..4\]` |
| `multi_ligand.json` | Multi-cofactor active site (ATP + Mg²⁺; PLP + substrate) | `experiment=diverse effort=max seeds=\[0..4\]` |
| `rna_binder.json` | RNA-binding protein at multiple lengths | `experiment=diverse effort=max seeds=\[0..4\]` |
| `dna_binder.json` | dsDNA binder (TF-like) at multiple lengths | `experiment=diverse effort=max seeds=\[0..4\]` |
| `partial_mask_hotspot.json` | Fix one or more hotspot residues + cofactor | `experiment=diverse effort=max seeds=\[0..4\]` |
| `sequence_redesign_loop.json` | Redesign positions 45–55 of a fixed sequence | `experiment=designable effort=max seeds=\[0..9\]` |
| `enzyme_design_heme_TS.json` | Heme-enzyme design conditioned on a reactive intermediate | `experiment=diverse effort=max seeds=\[0..49\]` |
| `single_ligand_studio179.json` | Studio-179-style template (3 lengths × 1 ligand) | `experiment=diverse effort=max seeds=\[0..4\]` |
| `covalent_bond.json` | Covalent attachment (PLP-Lys Schiff base) | `experiment=diverse effort=max seeds=\[0..4\]` |

## Running any example

```bash
cd ~/Repos/DISCO
source .venv/bin/activate

# Copy the example into DISCO's input_jsons/ directory:
cp ~/Repos/protein-design-skills/skills/disco/examples/ligand_smiles.json \
   input_jsons/my_aspirin_design.json

# Run:
python runner/inference.py \
  experiment=diverse \
  effort=max \
  input_json_path=input_jsons/my_aspirin_design.json \
  seeds=\[0,1,2,3,4\] \
  dump_dir=./output_aspirin
```

You can also pass an absolute path:

```bash
python runner/inference.py \
  experiment=diverse \
  effort=max \
  input_json_path=$HOME/Repos/protein-design-skills/skills/disco/examples/ligand_smiles.json \
  seeds=\[0,1,2,3,4\]
```

## Example-specific notes

### `unconditional_sweep.json`

Lengths 50, 100, 150, 200, 300. Use `experiment=designable effort=fast`
for prototyping; bump to `effort=max` for paper-quality numbers at
longer lengths.

### `ligand_smiles.json`

Aspirin (`CC(=O)Oc1ccccc1C(=O)O`) is small and easy to embed. For
larger / more flexible molecules, RDKit may fail to generate a 3D
conformer — see `ligand_sdf.json` for the file-based alternative.

### `ligand_sdf.json`

Uses `FILE_studio-179/priority_1/heme_b_final_0.sdf`. The path resolves
relative to the DISCO repo root. Substitute any 3D-conformer SDF / MOL /
MOL2 / PDB.

### `ligand_ccd.json`

Two jobs:
- `atp_len_200` — `CCD_ATP`, a single CCD entry.
- `glycan_NAG_BMA_BGC_len_200` — multi-component glycan
  (`CCD_NAG_BMA_BGC`), join CCD codes with `_`.

### `ion_metal.json`

Two jobs:
- `fe_cluster_len_150` — four iron ions + one [4Fe-4S] cluster (`SF4`).
  Add `covalent_bonds` if you want explicit Cys-Fe ligation.
- `zn_binder_len_120` — a single Zn²⁺ ion (e.g. for carbonic-anhydrase-like
  active sites).

### `multi_ligand.json`

- `atp_mg_len_200` — common pattern: ATP requires Mg²⁺ for catalysis.
- `plp_lys_substrate_len_200` — PLP cofactor + a histidine-substrate
  SMILES. Combine with `covalent_bond.json` to add the Schiff-base bond.

### `rna_binder.json`

26-nt RNA target swept at lengths 60, 70, 80. Mirror the paper's
6YMC setup. Recall: RNA cannot be masked.

### `dna_binder.json`

15-bp dsDNA (two `dnaSequence` entries — the two strands are
reverse complements). Mirror the paper's 7S03 setup.

### `partial_mask_hotspot.json`

Two patterns:
- `heme_with_cys_hotspot_len_200` — fixes Cys at position 31, attaches it
  to heme Fe via `covalent_bonds`. The Fe-Cys axial ligation pattern of
  P450-like enzymes.
- `two_his_zn_coordination_len_150` — fixes two His residues for Zn²⁺
  coordination (no explicit `covalent_bonds`; DISCO will discover the
  geometry).

### `sequence_redesign_loop.json`

A 100-residue chain with positions 45–55 masked — DISCO will redesign
this loop while keeping the rest of the sequence fixed.

### `enzyme_design_heme_TS.json`

Three lengths (150, 200, 250) all conditioned on the carbene transition-state
intermediate from `studio-179/priority_0/`. Pair with
`experiment=diverse effort=max` and **50+ seeds** for a realistic enzyme
design campaign. No catalytic residue is pre-specified — DISCO
discovers the coordination.

### `single_ligand_studio179.json`

A drop-in template for benchmarking a custom ligand against Studio-179.
Edit the `FILE_` path to your own SDF and rename the jobs.

### `covalent_bond.json`

PLP-Lys Schiff base example: Lys at position 80 is fixed in the
sequence; a covalent bond is declared between Lys-NZ and PLP-C4A. The
parser strips the leaving atoms automatically.

## Adapting for your own targets

1. **Pick the closest example** from the table above.
2. **Copy it** into `~/Repos/DISCO/input_jsons/<your_name>.json` (or
   anywhere — `input_json_path` accepts absolute paths).
3. **Edit the `sequence` length** by changing the number of hyphens.
4. **Replace the conditioning entity** (ligand SMILES / path /
   CCD code / DNA / RNA / ion).
5. **Update `name`** so output files have a meaningful prefix.
6. **Run** with the recommended preset.

If you make significant edits, validate your JSON before running:

```bash
python -c "import json; json.load(open('input_jsons/my_design.json'))"
```

## Common mistakes

- **Wrong sequence length.** Count hyphens carefully — Hydra has no
  way to know what you "meant".
- **`U` in `dnaSequence` or `T` in `rnaSequence`.** Switch alphabets.
- **`-` in nucleic-acid sequences.** Not supported; fully specify.
- **`count > 1` on `proteinChain`.** Disallowed — DISCO is single-chain.
- **`covalent_bonds` position pointing to a masked residue type.** If
  the bond is on `SG`, fix the residue identity to `C` at that position;
  if on `NE2`, fix to `H`; etc. Otherwise the geometry will resolve but
  the biology won't make sense.
