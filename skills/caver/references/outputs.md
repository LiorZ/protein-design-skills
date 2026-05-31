# Outputs — directory layout, CSV schemas, every score

## Top-level layout

```
out/
├── summary.txt                    # human-readable per-cluster table
├── summary_precise_numbers.csv    # same priorities, full precision
├── analysis/
│   ├── tunnel_characteristics.csv # one row per (snapshot, tunnel)
│   └── tunnel_profiles.csv        # per-position radius along each tunnel
├── data/
│   ├── tunnels/                   # per-cluster tunnel mesh PDBs
│   ├── tunnel_edges/              # path/edge files
│   ├── clusters_timeless          # cluster metadata (id-mappings, member tunnels)
│   ├── start_zone.pdb             # vicinity of the starting point
│   ├── end_zone.pdb               # vicinity of the exits
│   ├── origins.pdb                # CAVER-optimized starting points (one per frame)
│   ├── v_origins.pdb              # Voronoi-vertex origins
│   ├── times.txt                  # per-frame timings
│   ├── tree.txt                   # cluster hierarchy
│   └── <input>.pdb                # copies of input PDBs (post-clean)
├── pymol/
│   └── <input>_results.pse        # PyMOL session for static / small ensembles
├── log.txt                        # full run log
└── warnings.txt                   # parsing/optimization warnings (always check)
```

If `save_dynamics_visualization yes`, you also get per-frame VMD
geometry, `vmd.sh` / `vmd_timeless.sh` launchers, and `*.tcl` drivers.
If `generate_histograms` / `_heat_map` is on, you get matching PNGs +
data files in `analysis/`.

## `summary.txt` — the human view

Header block defines every column, then the table:

```
  ID      No   No_snaps   Avg_BR    SD   Max_BR   Avg_L    SD   Avg_C  ...
   1       1          1    0.671 0.000     0.67  14.101 0.000  1.123 ...
   2       1          1    0.840 0.000     0.84  14.136 0.000  1.150 ...
```

Column legend (verbatim from the file):

| Column | Meaning |
|--------|---------|
| `ID` | Tunnel **cluster** id; ranked by `Priority` (1 = best). |
| `No` | Total tunnels in this cluster (across snapshots). |
| `No_snaps` | Number of snapshots where this cluster appears with radius ≥ `probe_radius`. |
| `Avg_BR` | Average bottleneck radius (Å). |
| `SD` | Standard deviation of `Avg_BR` (Å). |
| `Max_BR` | Maximum bottleneck radius (Å). |
| `Avg_L` | Average tunnel length (Å). |
| `Avg_C` | Average tunnel curvature (≥ 1.0; 1.0 = straight). |
| `Priority` | **Headline ranking metric** — throughput averaged over all snapshots; missing-snapshot throughput = 0. |
| `Avg_throughput` | Throughput averaged over snapshots that have this cluster. |
| `Avg_up_E_BR`, `Max_up_E_BR` | Upper-error-bound estimates on bottleneck radius (emitted when `compute_errors yes`). |
| `Avg_up_E_TR`, `Max_up_E_TR` | Upper-error-bound estimates on full tunnel radius profile. |
| `SD` (right-most) | Pooled std dev. |

Note the **two different averages**:

- `Priority` averages over **all** snapshots (zero where the cluster
  is absent) → tells you "how reliably this tunnel is open".
- `Avg_throughput` averages over **only the snapshots that contain it**
  → tells you "when open, how good".

For ranking pick `Priority`. For "best-case" decisions pick `Max_BR`.

## `summary_precise_numbers.csv`

Same `Priority` / `Avg_throughput` / `SD` as the `.txt`, full-precision
floats, header row, one cluster per row. Use this for plotting /
filtering:

```python
import pandas as pd
df = pd.read_csv("out/summary_precise_numbers.csv")
df.columns = [c.strip() for c in df.columns]
top10 = df.nlargest(10, "Priority")
```

## `analysis/tunnel_characteristics.csv`

One row per (snapshot, tunnel cluster, tunnel) — i.e. when
`one_tunnel_in_snapshot cheapest`, each cluster shows up at most once
per snapshot.

```
Snapshot, Tunnel cluster, Tunnel, Throughput, Cost, Bottleneck radius,
Bottleneck R error bound, Length, Curvature
```

Columns:

| Column | Units / range | Meaning |
|--------|---------------|---------|
| `Snapshot` | filename | The source `*.pdb`. |
| `Tunnel cluster` | int | Cluster ID matching `summary.txt`. |
| `Tunnel` | int | Per-snapshot intra-cluster index (usually 1 if `one_tunnel_in_snapshot cheapest`). |
| `Throughput` | 0…1 | `exp(-cost)` scaled — higher = wider / shorter. |
| `Cost` | float | Integrated path cost (`∫ r⁻ᵉ ds` with `cost_function_exponent = e`). |
| `Bottleneck radius` | Å | The narrowest point along the tunnel. |
| `Bottleneck R error bound` | Å or `-` | Upper bound on bottleneck (only if `compute_errors yes`). |
| `Length` | Å | Path arc-length. |
| `Curvature` | ≥ 1.0 | `Length / straight-line distance`. |

To filter for "good" tunnels:

```python
import pandas as pd
df = pd.read_csv("out/analysis/tunnel_characteristics.csv")
df.columns = [c.strip() for c in df.columns]
good = df[(df["Throughput"] > 0.3) & (df["Bottleneck radius"] > 1.0)]
```

## `analysis/tunnel_profiles.csv`

Per-position geometry **along** each tunnel. One row per
(snapshot, cluster, tunnel, axis), with the values for that axis as a
comma-separated list across positions.

```
Snapshot, Tunnel cluster, Tunnel, Throughput, Cost, Bottleneck radius,
Average R error bound, Max. R error bound, Bottleneck R error bound,
Curvature, Length, , Axis, Values...
```

Axes emitted per tunnel:

| Axis | Meaning |
|------|---------|
| `X`, `Y`, `Z` | Per-position centerline coordinates. |
| `distance` | Cumulative Euclidean step from the previous point. |
| `length` | Arc-length from the starting point. |
| `R` | Tunnel radius at each position. |
| `Upper limit of R overestimation` | Per-position error bound (or `-`). |

Sampling step is `profile_tunnel_sampling_step` (default 0.5 Å).

Parsing this is awkward because the values are pipe-on-one-row; a
helper:

```python
import csv
def load_profiles(path):
    out = {}
    with open(path) as f:
        rd = csv.reader(f)
        header = next(rd)
        for row in rd:
            if len(row) < 14: continue
            snap, cluster, tunnel = row[0].strip(), int(row[1]), int(row[2])
            axis = row[12].strip()
            values = [float(x) if x.strip() != "-" else None for x in row[13:]]
            out.setdefault((snap, cluster, tunnel), {})[axis] = values
    return out
```

## `data/`

The geometric / clustering artifacts.

### `data/tunnels/`

One folder per cluster (`tunnel_<cluster_id>/`), each holding a mesh
PDB of every tunnel in that cluster (sub-sampled by
`visualize_tunnels_per_cluster` / `visualization_subsampling`). Open
in any viewer:

```bash
pymol out/data/tunnels/tunnel_1/*.pdb
```

These are **HETATM**-only PDBs of pseudo-atoms tracing the tunnel
surface — useful for layered renders.

### `data/tunnel_edges/`

The graph edges discovered by Voronoi traversal. Mostly for debugging
or input to other tools.

### `data/clusters_timeless`

A directory (despite the name not having a `/` suffix) listing the
cluster → tunnel membership and metadata. Used by the visualization
scripts; rarely consumed by hand.

### `data/start_zone.pdb`, `end_zone.pdb`

PDB pseudo-atoms drawing the regions excluded by
`exclude_start_zone` / `exclude_end_zone`. Visualize alongside the
tunnels to confirm the zones are sensible.

### `data/origins.pdb`, `data/v_origins.pdb`

The CAVER-optimized starting points (one HETATM per frame). If your
starting hint was bad, the points here will be scattered or far from
the active site — useful diagnostic.

```bash
pymol -d "load 1AKD.pdb; load out/data/origins.pdb, origins; show spheres, origins; color red, origins"
```

### `data/times.txt`

Per-frame wall-clock times. Useful for capacity planning before a big
MD run.

### `data/tree.txt`

The full cluster hierarchy from average-link clustering — the
"dendrogram" cut by `clustering_threshold`. Lower the threshold to
take a deeper cut.

## `pymol/<input>_results.pse`

A pre-built PyMOL session that loads the (last) input structure, all
tunnel clusters coloured by `Priority`, and (optionally) the
start / end zones and origins. Just:

```bash
pymol out/pymol/1AKD_results.pse
```

For an MD ensemble this is built from the **first frame** plus the
clustered tunnels — for trajectory visualization, use the VMD scripts
in the output directory (`vmd.sh`, `vmd_timeless.sh`).

## `log.txt` and `warnings.txt`

Both are plain text. `log.txt` is the verbose run record (frame timings,
parameter echo, cluster counts); `warnings.txt` collects parsing /
optimization warnings:

```
WARN: residue HEM not in atom_radii.csv, using element fallback
WARN: starting point optimization moved >= max_distance, using original
WARN: snapshot 17.pdb has no tunnels at probe_radius 0.9
```

Always grep these — silent issues end up here.

## Generated histograms / heat maps

When the corresponding `generate_*` flags are on, you also get:

| File | Source flag |
|------|-------------|
| `analysis/bottleneck_histogram.png` | `generate_histograms yes` |
| `analysis/throughput_histogram.png` | `generate_histograms yes` |
| `analysis/bottleneck_heat_map.png` | `generate_bottleneck_heat_map yes` |
| `analysis/profile_heat_map.png` | `generate_profile_heat_map yes` |

…plus the raw `.csv`/`.txt` companions used to draw them.

The bottleneck heat map shows (cluster × snapshot → bottleneck radius)
as a coloured grid. The profile heat map shows
(cluster × position-along-tunnel → radius). Both are great in the
methods section of a tunnel-engineering paper.

## What to keep, what to discard

Bare minimum for downstream analysis:

```
out/summary_precise_numbers.csv
out/analysis/tunnel_characteristics.csv
out/analysis/tunnel_profiles.csv      # optional, biggest file
out/data/tunnels/                     # for visualization
out/data/origins.pdb                  # for QC of the starting point
out/pymol/                            # for the figure
out/log.txt
out/warnings.txt
```

`data/tunnels/` can be 100s of MB for big MD ensembles — drop if you
only need the CSVs.

## Picking a "best" tunnel

For enzyme engineering / binder design:

```python
import pandas as pd
df = pd.read_csv("out/summary_precise_numbers.csv")
df.columns = [c.strip() for c in df.columns]
# Top cluster by Priority that's wide enough for the substrate:
hit = df[df["Average throughput"] > 0.2].nlargest(1, "Priority")
print(hit["Tunnel cluster ID"].iloc[0])
```

The cluster ID also names a directory under `data/tunnels/<id>/` —
load those meshes in PyMOL to see the path.

## Programmatic post-processing — common joins

```python
import pandas as pd
chars = pd.read_csv("out/analysis/tunnel_characteristics.csv")
chars.columns = [c.strip() for c in chars.columns]
summary = pd.read_csv("out/summary_precise_numbers.csv")
summary.columns = [c.strip() for c in summary.columns]

# Per-frame stats joined with overall cluster priority:
merged = chars.merge(summary, left_on="Tunnel cluster",
                              right_on="Tunnel cluster ID", how="left")
```
