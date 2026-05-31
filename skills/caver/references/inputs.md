# Inputs — PDB files, snapshots, starting points

CAVER consumes one or more **PDB files** and a config that pins a
starting point. This page covers the file-format requirements, how to
stage inputs for static vs. dynamic analyses, the three starting-point
modes, and the atom-radii table.

## PDB file format

- **Plain PDB** (no mmCIF). CAVER 3.01 reads:
  - 3-letter residue names (cols 18-20). Default
    `long_residue_names yes` lets it also accept 4-letter residue
    names (cols 18-21). Switch off only if you have actual 3-letter
    residues that overflow into col 21 (rare).
  - Atom serial numbers (cols 7-11) that may contain **letters** for
    large structures (CAVER interprets A=10, B=11, etc.).
- **Heavy atoms only is fine.** The default `atom_radii.csv` ships
  heavy-atom radii — hydrogens are usually omitted from the analysis
  anyway. Stripping H reduces noise and shrinks the file.
- **HETATM records** are read. Cofactors and ligands occupy space and
  are correctly treated as obstacles. Waters are usually stripped
  unless you specifically want them as obstacles.
- **Multiple chains** are fine. CAVER builds a single Voronoi diagram
  over all atoms.
- **ANISOU / sigATM / TER** records are ignored. Multiple `MODEL` /
  `ENDMDL` blocks: CAVER reads **only the first model** per file —
  split NMR ensembles into separate files (`model1.pdb`,
  `model2.pdb`, …) for snapshot-style analysis.

If you have mmCIF / multi-model PDB / huge files:

```bash
# mmCIF → PDB (gemmi):
gemmi convert input.cif input.pdb

# Strip hydrogens (biotite):
python - <<'PY'
import biotite.structure.io.pdb as pdb
struct = pdb.PDBFile.read("input.pdb").get_structure(model=1)
struct = struct[struct.element != "H"]
pdb.PDBFile().set_structure(struct).write("clean.pdb")
PY

# Or with PyMOL:
pymol -cq -d "load input.pdb; remove hydrogens; save clean.pdb"
```

## One PDB vs. an ensemble

CAVER discovers snapshots by listing `*.pdb` in the directory passed as
`-pdb`. The directory layout is the contract:

### Static (single structure)

```
proj/
└── pdb/
    └── 1AKD.pdb           # one file
```

The "ensemble" has size 1; `frame_clustering` is a no-op; `Priority`
collapses to the per-tunnel throughput of that single frame.

### Dynamic (MD ensemble)

```
proj/
└── md_snapshots/
    ├── 1.pdb
    ├── 2.pdb
    ├── ...
    └── 100.pdb
```

- **Naming**: any name works; CAVER sorts alphabetically. Use zero-
  padded integers (`001.pdb`, `010.pdb`) if you have ≥ 100 frames and
  care about plotting order. Plain integers (`1.pdb`, `2.pdb`, …) work
  for ≤ 99 frames but produce mis-sorted heatmap axes for larger sets.
- **Alignment**: CAVER does **not** align frames. Use VMD,
  `gmx trjconv -fit rot+trans`, mdtraj, or PyMOL `align` to put every
  frame in a common reference frame **before** running CAVER.
  Otherwise the clustering sees the protein wandering and breaks up
  what should be one channel into many.
- **Atom ordering**: `starting_point_atom <N>` references the
  **N-th ATOM record across each PDB file** (atom serial number).
  All snapshots must share that ordering. If you generated frames
  with different software / pipelines, re-emit them through the same
  PDB writer.

### Sub-sampling a long trajectory

```ini
time_sparsity 5      # use every 5th file in the sorted listing
first_frame   100    # skip the equilibration
last_frame    5000   # stop at 5000
```

These three parameters slice the file list before processing — pair
with `1000.pdb` etc. naming.

### Many homologs as "snapshots"

A creative use: drop one PDB per pre-aligned homolog and let CAVER's
frame clustering group tunnels across homologs. Works as long as you
pick a `starting_point_*` that's anatomically equivalent in every
structure (e.g. catalytic Ser oxygen, residue id varies — use
`starting_point_atom` and remap per-PDB).

## Starting points — the three modes

You **must** pick exactly one form. Multiple `starting_point_atom`
lines accumulate into a single centroid.

### `starting_point_atom <serial> [<serial> …]`

```ini
starting_point_atom 578
starting_point_atom 1609
starting_point_atom 3258
```

Three atom serial numbers → CAVER averages their positions, then
optimizes within `max_distance` Å into the largest nearby cavity. The
canonical pick for an enzyme: three atoms from the catalytic triad.
Atoms must exist in **every** snapshot.

### `starting_point_residue <chain><resid> [<chain><resid> …]`

```ini
starting_point_residue 150        # any-chain residue 150
starting_point_residue A150       # explicit chain
```

CAVER uses the centroid of the residue's atoms. Simpler than picking
specific atoms; useful when the catalytic residue is obvious. Same
caveat about consistent numbering across snapshots.

### `starting_point_coordinates X Y Z`

```ini
starting_point_coordinates 17.012 24.139 7.790
```

Explicit Cartesian XYZ (in the PDB's coordinate system). CAVER still
re-optimizes within `max_distance`. Useful when you've identified a
binding pocket by another tool (fpocket, autoSiteR, ligand position).
**Make sure the coords are inside the protein** for at least the first
snapshot — CAVER uses snapshot 1 to anchor the optimization.

### How CAVER repairs your starting point

- It searches within `max_distance` (default 3 Å) for a position with
  free radius ≥ `desired_radius` (default 5 Å).
- If no such position exists, CAVER falls back to the original point
  and may report a warning to `warnings.txt`.
- `starting_point_protection_radius` (default 4 Å) prevents the
  optimization from drifting into a position that's right against an
  atom.

## Atom radii — `bin/atom_radii.csv`

Default heavy-atom radii live at `/opt/caver/bin/atom_radii.csv`.
Schema:

```
HOH  O    1.40
ALA  CA   1.87
ALA  CB   1.87
...
```

For unknown atoms CAVER uses the element-based fallback (`C 1.70`,
`N 1.55`, `O 1.52`, `S 1.80`, etc.).

### Customizing for non-canonical residues / cofactors

Two options:

1. **Bind-mount an override** (recommended — no rebuild):

   ```bash
   apptainer run \
       --bind ./my_radii.csv:/opt/caver/bin/atom_radii.csv \
       "$SINGULARITY_HOME"/CAVER.sif \
       -home /opt/caver -pdb ./pdb -conf ./conf.txt -out ./out
   ```

2. **Edit the source** in the repo (`caver_3.0/caver/bin/atom_radii.csv`)
   and rebuild the SIF.

Add one line per (residue3, atom_name, radius) tuple. The radius is in
Ångströms. For ligands you can keep using the heavy-atom-only
convention.

### Effect of changing radii

Bottleneck radii are directly proportional to atom radii. Halving an
atom radius widens the apparent tunnel by ~that atom's contribution at
the bottleneck. Be conservative — only edit when CAVER's default is
demonstrably wrong (e.g. metal ions where 1.70 Å is too generous).

## Probe vs. shell

| Parameter | Meaning | Typical | Effect of increasing |
|-----------|---------|---------|----------------------|
| `probe_radius` | Minimum radius of an atom-sphere that must fit at every point along the tunnel | 0.9 Å (water) | Only finds wider channels; fewer / shorter tunnels |
| `shell_radius` | Radius of the "outer-surface" sphere — defines where the protein ends | 3 Å | Tunnels can extend further outside the protein before being terminated |
| `shell_depth` | Thickness of the outer shell | 4 Å | Higher means tunnels are required to penetrate further from the surface to count |

Recommended defaults (from the upstream user guide):

- Water-sized analysis: `probe_radius 0.9 shell_radius 3 shell_depth 4`.
- Narrow channels / ion pores: `probe_radius 0.6 shell_radius 5
  shell_depth 4` (see the 1BL8 example).
- Membrane channels with big outside: `shell_radius 15` (see 2BG9).

## Suggested pre-flight checklist

```bash
# 1. Sanity-check the PDB:
grep -c '^ATOM '   input.pdb       # heavy-atom count
grep -c '^HETATM ' input.pdb       # ligand / hetero atoms
grep -c '^MODEL '  input.pdb       # should be 0 or 1

# 2. Visualize the starting point (with PyMOL):
pymol -cq -d "
  load input.pdb;
  pseudoatom sp, pos=[17.012, 24.139, 7.790];
  show spheres, sp; color red, sp;
  ray 800 600; png start.png
"

# 3. Pick the right probe radius:
#    - water  → 0.9
#    - small substrate (CO2, H2O2, glycerol) → 1.4
#    - drug-like → 1.8-2.2
```

## Common pre-processing pipeline

```bash
# Strip waters + non-essential HETATMs, leaving the cofactor:
pymol -cq -d "
  load raw.pdb;
  remove resn HOH or resn NA or resn CL;
  save clean.pdb
"

# Renumber to consecutive serials (some CAVER warnings disappear):
python - <<'PY'
import biotite.structure.io.pdb as pdb
s = pdb.PDBFile.read("clean.pdb").get_structure(model=1)
f = pdb.PDBFile()
f.set_structure(s)
f.write("renumbered.pdb")
PY
```

## Multi-chain caveats

- CAVER builds tunnels through the **whole** structure — multi-chain
  ok, including symmetry mates of a homotetramer.
- For homo-oligomers where you want the tunnel from each monomer's
  active site: pick a starting point in chain A; CAVER will report the
  tunnels from that one origin. To do all four monomers, run four
  jobs (or `starting_point_residue A150 / B150 / C150 / D150` — but
  that averages the four into one origin, which is rarely what you
  want).
