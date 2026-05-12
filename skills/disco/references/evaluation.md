# Evaluating DISCO designs

DISCO does **not** include a built-in refolder or scorer. To evaluate
generated designs you pair them with a structure predictor (Chai-1 for
paper-quality, Boltz-2 or AF2 as alternatives) and compute the
co-designability metric.

This page describes the canonical evaluation recipe.

## The metric

A design is **co-designable** iff:

1. The **protein backbone** of the refolded sequence (with the original
   conditioning) lies within **< 2 Å RMSD** of the DISCO-generated
   backbone.
2. **Every** ligand centroid in the refolded structure lies within
   **< 2 Å** of the corresponding ligand centroid in the DISCO
   structure.

This is stricter than plain backbone-RMSD designability: it checks that
the *binding mode* is preserved, not just that the sequence folds.

For pure unconditional generation (no ligand / nucleic acid), only the
backbone criterion applies — and the paper calls this **co-designability**
rather than designability because DISCO co-generates both the sequence
and the structure (so even unconditional refold is a co-design check).

## End-to-end recipe (Chai-1)

The paper uses **Chai-1** as the refolder. The `chai` skill has the
full Chai-1 CLI reference; below is the DISCO-specific stitching.

```python
# pseudo-code; adapt to your scoring pipeline
from pathlib import Path
import re
import numpy as np
import biotite.structure.io.pdb as pdb_io
import biotite.structure as struc

def parse_disco_sequence_file(path):
    """Yield dicts with keys: header, sequence, dna, rna, ligands."""
    cur = None
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if cur is not None:
                out.append(cur)
            cur = {"header": line[1:], "sequence": "", "dna": [], "rna": [], "ligands": []}
        elif line.startswith("dna_sequence "):
            cur["dna"].append(line.split(" ", 1)[1])
        elif line.startswith("rna_sequence "):
            cur["rna"].append(line.split(" ", 1)[1])
        elif line.startswith("ligand_smiles "):
            cur["ligands"].append(line.split(" ", 1)[1])
        else:
            cur["sequence"] += line
    if cur is not None:
        out.append(cur)
    return out


def ca_rmsd(struct_a, struct_b):
    a_ca = struct_a[(struct_a.atom_name == "CA")]
    b_ca = struct_b[(struct_b.atom_name == "CA")]
    assert len(a_ca) == len(b_ca)
    aligned, _ = struc.superimpose(a_ca, b_ca)
    return struc.rmsd(a_ca, aligned)


def ligand_centroid(struct, hetero=True):
    """Centroid of all hetero atoms in the structure."""
    het = struct[struct.hetero & (struct.element != "H")]
    return het.coord.mean(axis=0)


def is_co_designable(disco_pdb, chai_pdb, backbone_thresh=2.0, ligand_thresh=2.0):
    a = pdb_io.PDBFile.read(disco_pdb).get_structure(model=1)
    b = pdb_io.PDBFile.read(chai_pdb).get_structure(model=1)
    bb_rmsd = ca_rmsd(a, b)
    if bb_rmsd >= backbone_thresh:
        return False, bb_rmsd, None
    # Ligand-by-ligand centroid check (simplistic — match by residue id):
    a_ligs = {res_id: ligand_centroid(a[a.res_id == res_id]) for res_id in np.unique(a.res_id[a.hetero])}
    b_ligs = {res_id: ligand_centroid(b[b.res_id == res_id]) for res_id in np.unique(b.res_id[b.hetero])}
    lig_dists = [np.linalg.norm(a_ligs[k] - b_ligs[k]) for k in a_ligs if k in b_ligs]
    return all(d < ligand_thresh for d in lig_dists), bb_rmsd, lig_dists
```

### Step-by-step

1. **Run DISCO** to generate `pdbs/` and `sequences/`.

   ```bash
   python runner/inference.py \
     experiment=diverse \
     effort=max \
     input_json_path=input_jsons/heme_b.json \
     seeds=\[0,1,2,3,4\] \
     dump_dir=./run_heme
   ```

2. **For each sample**, build a Chai-1 input that pairs the **generated
   sequence** with the **original conditioning** (same ligand SMILES /
   SDF, same DNA / RNA sequence as the input JSON). Run Chai-1.

   See the `chai` skill for the full input format; the key fields are the
   protein sequence (from `sequences/*.txt`) and the same ligand entry as
   used in the DISCO input.

3. **Compute backbone RMSD** between the DISCO PDB and the Chai-1 best
   prediction (Cα superposition).

4. **Compute ligand centroid distance** for each ligand (or ion or
   nucleic-acid chain centroid for those targets).

5. **Pass** iff both are < 2 Å.

## Alternative refolders

| Tool | When to use | Skill |
|------|-------------|-------|
| **Chai-1** | Paper default. Match this for benchmark-comparable numbers. | `chai` |
| **Boltz-2** | Faster, also predicts affinity if you want to triage. | `boltz` |
| **AlphaFold-Multimer** | When you want PAE / ipTM in addition to RMSD. | `alphafold` |

For **ranking** (not pass/fail), the `ipsae` skill computes a much
stronger ranker than ipTM or iPAE for the refolded complexes — use it
when comparing many DISCO designs against each other.

For biophysical QC (instability index, pI, polybasic clusters, cysteine
liabilities, etc.) before ordering DNA, use the `protein-qc` skill.

## Diversity scoring

Co-designability alone overcounts duplicate folds. The paper reports
**fraction co-designable *and* diverse**:

1. Cluster passing designs by structural similarity (e.g., TM-score > 0.7,
   or Foldseek E-value cutoff).
2. Count *clusters* per (ligand, length), not raw passes.

The `foldseek` skill has the recipe for structural clustering.

## Common pitfalls

- **Refolding with the wrong conditioning.** If your DISCO input had a
  custom SMILES, Chai-1 must receive the same SMILES — pass it via
  `ligand: smiles: ...` in the Chai-1 YAML. A different conformer will
  inflate ligand-centroid RMSD.
- **Wrong residue numbering during alignment.** DISCO writes residue
  IDs starting at 1; Chai-1 may use different numbering. Align by
  position (the sequences are identical) rather than residue ID.
- **Skipping the `n_seq_duplicates_per_structure > 1` case.** Each
  `>cogen_seq i` record refolds independently. Score each sequence.
- **Comparing across `experiment` presets.** `designable` boosts
  co-designability; `diverse` boosts diversity. Don't pool them in a
  single number without noting the preset.
- **Skipping the ligand-centroid check on metalloproteins.** For metal
  ions, the centroid *is* the atom; this is a strict positional test.

## Studio-179 specific

For the canonical Studio-179 paper numbers, you also need:

- `experiment=diverse`, `effort=max`.
- 5 seeds × 3 lengths (150 / 200 / 250) per ligand.
- Chai-1 refold with the same ligand SDF (not a re-embedded SMILES).
- Diversity clustering threshold matching the paper (see paper appendix).

For raw paper outputs to validate your scorer against, see
[`DISCO-Design/DISCO_benchmark_data`](https://huggingface.co/datasets/DISCO-Design/DISCO_benchmark_data).
