# Outputs

## File layout

After `bioemu.sample`:

```text
<output_dir>/
├── sequence.fasta          # the input sequence
├── topology.pdb            # backbone topology (one frame, used as .xtc top)
├── samples.xtc             # the ensemble — up to num_samples frames
└── batch_0_<n>.npz         # per-batch raw output (kept for resumability)
    batch_<n>_<n>.npz
    ...
```

After `bioemu.sidechain_relax --outpath <out> --prefix samples`:

```text
<out>/
├── samples_sidechain_rec.pdb       # single-frame topology with side chains
├── samples_sidechain_rec.xtc       # full ensemble with side chains
├── samples_md_equil.pdb            # topology after MD equilibration
├── samples_md_equil.xtc            # ensemble after MD equilibration
└── frame<N>_md_top.pdb             # only if --simtime-ns > 0 (per-frame free-MD topology)
```

## How to load and analyze

The canonical loader is **MDTraj**:

```python
import mdtraj
traj = mdtraj.load_xtc("<output_dir>/samples.xtc",
                       top="<output_dir>/topology.pdb")
print(f"{traj.n_frames} frames × {traj.n_atoms} atoms ({traj.n_residues} residues)")
```

Or with **Biotite** (faster array operations, NumPy-native):

```python
import biotite.structure.io.pdb as pdb
import biotite.structure.io.trajectory as traj_io   # for XTC
top = pdb.PDBFile.read("topology.pdb").get_structure(model=1)
xtc = traj_io.XTCFile.read("samples.xtc")
stack = traj_io.get_structure(xtc, template=top)    # AtomArrayStack
print(stack.stack_depth(), "frames")
```

(See the `biotite` skill for the full ensemble-analysis patterns —
RMSF, SASA per frame, TICA-style projections, clustering.)

## Per-batch `batch_*.npz` schema

Each `batch_<start>_<n>.npz` holds:

| Key | Shape | Notes |
|-----|-------|-------|
| `pos` | `(B, L, 3)` | Backbone-frame Cα positions in **nanometers**. |
| `node_orientations` | `(B, L, 3, 3)` | SO(3) rotation matrices per residue, defining the local backbone frame. |
| `sequence` | scalar | The input sequence string. |

`B` = batch size for that batch (≤ `batch_size_100 × (100/L)²`).
`L` = sequence length.

These are kept after the final `samples.xtc` is written so that
**re-running with a higher `num_samples` resumes** instead of starting
over.

## Frame count vs. `num_samples`

With `filter_samples=True` (default):

```
n_frames_in_samples.xtc ≤ num_samples
```

The post-filter discards any sample whose backbone has clashes or
chain breaks. For long / disordered chains the loss can be large —
use physical steering or set `filter_samples=False`.

To know how many of your requested samples survived:

```python
import mdtraj
print(mdtraj.load_xtc("samples.xtc", top="topology.pdb").n_frames, "of N requested")
```

## Units

| Quantity | Unit in BioEmu output |
|----------|------------------------|
| Coordinates in `.xtc` / `.pdb` | nanometers (`.xtc`) / Angstroms (`.pdb` — MDTraj converts on save) |
| `CaCaDistance` CV | nanometers (e.g. `target: 0.38` = 3.8 Å) |
| `RMSD` CV | nanometers |
| `PairwiseClash.min_dist` | nanometers (default `0.41` = 4.1 Å) |

If you see a steering YAML with `target: 4.0`, that's 4 nm = 40 Å —
probably a typo for 0.4 nm.

## Topology details

`topology.pdb` is a single-frame, backbone-only PDB. It contains:
- One chain (BioEmu is monomer-only).
- N, CA, C, O for every residue.
- No side chains, no hydrogens, no ligands, no waters.

For ensemble analysis you usually want side chains — run
`bioemu.sidechain_relax` to get `samples_sidechain_rec.{pdb,xtc}`,
then point your loader at the new topology.

## Quick ensemble-analysis recipes

### Mean RMSD to first frame

```python
import mdtraj
t = mdtraj.load_xtc("samples.xtc", top="topology.pdb")
t.superpose(t, frame=0)
rmsd = mdtraj.rmsd(t, t, frame=0)
print(f"mean = {rmsd.mean():.3f} nm, max = {rmsd.max():.3f} nm")
```

### Per-residue RMSF

```python
import mdtraj, numpy as np
t = mdtraj.load_xtc("samples.xtc", top="topology.pdb")
t.superpose(t, frame=0)
ca = t.top.select("name CA")
rmsf = mdtraj.rmsf(t, t, frame=0, atom_indices=ca)
# rmsf[i] = RMSF (nm) of residue i
```

### Cluster the ensemble

```python
import mdtraj
t = mdtraj.load_xtc("samples.xtc", top="topology.pdb")
t.superpose(t, frame=0)
dist = np.sqrt(np.mean((t.xyz[:, None] - t.xyz[None, :])**2, axis=(-2, -1)))
# Then sklearn AgglomerativeClustering, or k-means on TICA components, etc.
```

### Estimate the folded-state population

For a sequence with a known reference fold:

```python
import mdtraj
t = mdtraj.load_xtc("samples.xtc", top="topology.pdb")
ref = mdtraj.load_pdb("reference_folded.pdb")
rmsd_to_ref = mdtraj.rmsd(t, ref)
folded_frac = (rmsd_to_ref < 0.3).mean()    # within 3 Å = folded
print(f"folded fraction = {folded_frac:.2%}")
# ΔG_fold ≈ -kT * ln(folded / unfolded)
import numpy as np
kT_kcal = 0.593   # at 298 K
dG = -kT_kcal * np.log(folded_frac / (1 - folded_frac))
print(f"ΔG_fold ≈ {dG:.2f} kcal/mol")
```

(For rigorous ΔG numbers, follow the protocol in
`bioemu-benchmarks/BIOEMU_RESULTS.md` — this snippet is a sanity check
not a benchmark.)
