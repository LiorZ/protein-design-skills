# config.txt — every parameter, in upstream order

The CAVER config file is a flat list of `<key> <value>` lines, grouped
by sections separated by `#`-comments. Lines starting with `#` are
ignored. Values can be `yes`/`no`, integers, floats, or quoted paths.

This is a complete reference, transcribed and annotated from
`caver_3.0/user_guide/config_default.txt`. The defaults shown are
CAVER's, **not** the (often more aggressive) overrides used in the
bundled examples.

## Calculation setup

| Param | Default | What it does |
|-------|---------|--------------|
| `load_tunnels` | `no` | If `yes`, skip recomputation and load tunnels from a previous run's `out/data`. Used for re-clustering only. |
| `load_cluster_tree` | `no` | If `yes`, also load the cluster tree (must pair with `load_tunnels yes`). |
| `stop_after` | `never` | Stop the pipeline early. Values: `tunnels`, `clustering`, `outputs`, `never`. Use to inspect intermediate state. |

## Input data

| Param | Default | What it does |
|-------|---------|--------------|
| `time_sparsity` | `1` | Use every N-th input PDB (`1` = all frames). |
| `first_frame` | `1` | 1-based index of first PDB in the sorted listing to include. |
| `last_frame` | `100000` | 1-based index of last PDB. Set lower than your file count to cap the run. |

## Tunnel calculation

| Param | Default | What it does |
|-------|---------|--------------|
| `starting_point_atom <serial>` | — | Atom serial inside the protein. Repeat for centroid. |
| `starting_point_residue <chain><id>` | — | Residue id. Repeat for centroid. |
| `starting_point_coordinates X Y Z` | — | Explicit XYZ. Pick **one** of the three modes. |
| `probe_radius` | `0.9` Å | Minimum radius the probe must fit along the entire tunnel. |
| `shell_radius` | `3` Å | Radius of the surface sphere defining the "outside" of the protein. |
| `shell_depth` | `4` Å | How deep into the shell a tunnel exit must penetrate to count. |

Picking the right `probe_radius` is the single most consequential
choice. See `references/inputs.md::Probe vs. shell`.

## Tunnel clustering

| Param | Default | What it does |
|-------|---------|--------------|
| `clustering` | `average_link` | Clustering algorithm. Only `average_link` (UPGMA-style) is supported. |
| `weighting_coefficient` | `1` | Distance weighting along the tunnel. Higher = bottleneck region dominates the distance. |
| `clustering_threshold` | `3.5` | Cluster-cut height. Lower → more (finer-grained) clusters. **Tune this first** when results are over- or under-merged. |
| `exclude_start_zone` | `2` Å | Ignore the first `N` Å of each tunnel when comparing — those points are near the shared starting point and uninformative. |
| `exclude_end_zone` | `0` Å | Ignore the last `N` Å of each tunnel. |
| `min_middle_zone` | `5` Å | After excluding zones, the remaining (middle) part must be ≥ `N` Å — otherwise the tunnel is dropped. |
| `save_zones` | `yes` | Emit `data/start_zone.pdb` / `end_zone.pdb` for visualization of the exclusion regions. |

## Generation of outputs

| Param | Default | What it does |
|-------|---------|--------------|
| `one_tunnel_in_snapshot` | `cheapest` | Per-snapshot reduction: `cheapest` keeps only the lowest-cost tunnel from each cluster per frame; `no` keeps all (verbose). |
| `max_output_clusters` | `999` | Cap on cluster IDs in the output. Increase for super-tunnelled structures. |
| `save_dynamics_visualization` | `no` | Generate per-frame VMD geometry for movies of tunnels over MD. Heavy on disk. |
| `generate_summary` | `yes` | `summary.txt` + `summary_precise_numbers.csv`. |
| `generate_tunnel_characteristics` | `yes` | `analysis/tunnel_characteristics.csv` (one row per snapshot × tunnel). |
| `generate_tunnel_profiles` | `yes` | `analysis/tunnel_profiles.csv` (per-position XYZ + R along each tunnel). |
| `generate_histograms` | `no` | Histograms of bottleneck radius / throughput. |
| `bottleneck_histogram MIN MAX BINS` | `0.0 2.0 20` | Histogram domain for bottleneck radii. |
| `throughput_histogram MIN MAX BINS` | `0 1.0 10` | Histogram domain for throughputs. |
| `generate_bottleneck_heat_map` | `no` | 2-D heat map of bottleneck radius vs. (frame, cluster). |
| `bottleneck_heat_map_range MIN MAX` | `1.0 2.0` | Color-scale range, Å. |
| `bottleneck_heat_map_element_size W H` | `10 10` | Pixel size per element. |
| `generate_profile_heat_map` | `no` | 2-D heat map of radius along tunnel × frame. |
| `profile_heat_map_resolution` | `0.5` Å | Sampling along the tunnel for the heatmap. |
| `profile_heat_map_range MIN MAX` | `1.0 2.0` | Color-scale range. |
| `profile_heat_map_element_size W H` | `20 10` | Pixel size per element. |
| `compute_tunnel_residues` | `no` | Per-cluster list of residues within `residue_contact_distance` of the tunnel. |
| `residue_contact_distance` | `3.0` Å | Distance cutoff for "lining" residues. |
| `compute_bottleneck_residues` | `no` | Per-cluster list of residues at / near the bottleneck. |
| `bottleneck_contact_distance` | `3.0` Å | Distance cutoff for bottleneck residues. |

`compute_tunnel_residues` is the parameter you want for **tunnel
engineering** — the residues it outputs are your mutation candidates.

## Advanced — starting-point optimization

| Param | Default | What it does |
|-------|---------|--------------|
| `max_distance` | `3` Å | Max displacement allowed when optimizing the starting point into a cavity. Increase only if you know your hint is far from the true cavity. |
| `desired_radius` | `5` Å | Target free-radius the starting point should sit in after optimization. |

## Advanced — tunnel calculation

| Param | Default | What it does |
|-------|---------|--------------|
| `number_of_approximating_balls` | `12` | Number of balls per atom in the Voronoi approximation. Higher = more accurate, slower. 4-12 is the practical range; bigger membrane channels (e.g. 2BG9) use `4` for tractability. |
| `add_central_sphere` | `yes` | Adds a central representative sphere to each atom to avoid co-spherical degeneracies. **Don't change.** |
| `max_number_of_tunnels` | `10000` | Per-frame cap on tunnels (after which CAVER stops enumerating). |
| `max_limiting_radius` | `100` | Tunnels with radius above this are not pruned (in practice always inf-like). |
| `cost_function_exponent` | `2` | Exponent in the path-cost integrand. Higher = bottlenecks penalized more strongly. |
| `automatic_shell_radius` | `no` | If `yes`, compute `shell_radius` from the bottleneck times the multiplier below. |
| `automatic_shell_radius_bottleneck_multiplier` | `2` | Multiplier for the automatic shell. |
| `starting_point_protection_radius` | `4` Å | Forbid the starting point from drifting closer than this to any atom. |

## Advanced — redundant tunnels removal (within a frame)

| Param | Default | What it does |
|-------|---------|--------------|
| `frame_clustering` | `yes` | Cluster *within* a frame first, removing near-duplicate paths. |
| `frame_weighting_coefficient` | `1` | Same role as `weighting_coefficient`, for the per-frame stage. |
| `frame_clustering_threshold` | `1` | Lower = more aggressive de-duplication. |
| `frame_exclude_start_zone` | `0` Å | Like `exclude_start_zone`, but for the per-frame stage. |
| `frame_exclude_end_zone` | `0` Å | Like `exclude_end_zone`. |
| `frame_min_middle_zone` | `5` Å | Minimum unique mid-section length. |

## Advanced — averaging of tunnel ends

| Param | Default | What it does |
|-------|---------|--------------|
| `average_surface_frame` | `yes` | Smooth tunnel endpoints over frames (within a cluster). |
| `average_surface_global` | `yes` | Smooth across all frames (global). |
| `average_surface_smoothness_angle` | `10` ° | Angular smoothness during endpoint averaging. |
| `average_surface_point_min_angle` | `5` ° | Minimum angular separation of sample points used for averaging (lowered from 5.73° → 5 in 3.0). |
| `average_surface_tunnel_sampling_step` | `0.5` Å | Sampling step along the tunnel for endpoint computation. |

## Advanced — approximate clustering (for big datasets)

When you have **thousands** of snapshots and average-link gets slow,
turn this on to use a two-stage approximation.

| Param | Default | What it does |
|-------|---------|--------------|
| `do_approximate_clustering` | `no` | Enable approximate clustering. |
| `cluster_by_hierarchical_clustering` | `20000` | Use exact hierarchical clustering for the first `N` representative tunnels; assign the rest by nearest centroid. |
| `max_training_clusters` | `15` | Number of initial training clusters for k-means seeding. |
| `generate_unclassified_cluster` | `no` | Emit an "unclustered" bucket for tunnels too far from any centroid. |

## Advanced — outputs (resolution / subsampling)

| Param | Default | What it does |
|-------|---------|--------------|
| `profile_tunnel_sampling_step` | `0.5` Å | Sampling resolution along the tunnel for `tunnel_profiles.csv`. |
| `visualization_tunnel_sampling_step` | `1` Å | Sampling resolution for mesh PDB / PyMOL geometry. |
| `visualize_tunnels_per_cluster` | `5000` | Cap on tunnels rendered per cluster in dynamics visualizations. |
| `visualization_subsampling` | `random` | Strategy when capping: `random`, `top` (best by priority), `all`. |
| `compute_errors` | `no` | Emit upper-bound error estimates on radii (`Avg_up_E_BR`, `Max_up_E_BR`, …). |
| `save_error_profiles` | `no` | Save error-bound profiles alongside tunnel profiles. |

## Advanced — Others

| Param | Default | What it does |
|-------|---------|--------------|
| `path_to_vmd` | `"C:/Program Files/University of Illinois/VMD/vmd.exe"` | Default Windows path. Override with the host's VMD; harmless to leave wrong if you don't run the VMD launcher. |
| `generate_trajectory` | `no` | If `yes` and VMD is reachable, emit a movie of the tunnel ensemble. Requires `path_to_vmd`. |
| `swap` | `yes` | Use disk swap for very large frames. Set `no` to keep everything in RAM (faster, more `-Xmx`). |
| `seed` | random | RNG seed. **Always set this** (`seed 1`) for reproducible runs. |
| `long_residue_names` | `yes` | Read 4-letter residue names (cols 18-21). Turn off only if necessary. |
| `correct_voronoi_diagram` | `yes` (since 3.01) | Use the 3.01 corrected starting-point optimization. Don't disable except for backward compatibility with 3.0. |

## Two canonical templates

### Static structure (single PDB)

```ini
starting_point_residue 150
probe_radius 0.9
shell_radius 3
shell_depth 4

clustering_threshold 3.5
exclude_start_zone 2
min_middle_zone 5

one_tunnel_in_snapshot cheapest
generate_summary yes
generate_tunnel_characteristics yes
generate_tunnel_profiles yes
compute_tunnel_residues yes
residue_contact_distance 3.0

seed 1
```

### MD ensemble with visualizations + heatmaps

```ini
time_sparsity 1
first_frame 1
last_frame 100

starting_point_atom 578
starting_point_atom 1609
starting_point_atom 3258

probe_radius 0.9
shell_radius 3
shell_depth 4

clustering average_link
weighting_coefficient 1
clustering_threshold 3.5

one_tunnel_in_snapshot cheapest
save_dynamics_visualization yes

generate_summary yes
generate_tunnel_characteristics yes
generate_tunnel_profiles yes
generate_histograms yes
generate_bottleneck_heat_map yes
generate_profile_heat_map yes
compute_tunnel_residues yes
compute_bottleneck_residues yes

frame_clustering yes
frame_clustering_threshold 1

swap no
seed 1
```

Both templates also ship as `examples/config_static.txt` and
`examples/config_md.txt`.

## How to tune

1. **Start with defaults + your starting point + `seed 1`.** Run.
   Check `summary.txt` exists and reports at least one cluster.
2. **No tunnels found?** Drop `probe_radius` to 0.6; verify the
   starting point (visualize `origins.pdb` from `data/`).
3. **Too many low-priority clusters?** Increase `clustering_threshold`
   (e.g. `3.5 → 5`) to merge similar paths, or set
   `last_frame` higher / `time_sparsity` lower if MD ensemble is
   under-sampled.
4. **Too few clusters / merged distinct channels?** Lower
   `clustering_threshold` (`3.5 → 2.0`).
5. **Want the residues to mutate?** `compute_tunnel_residues yes`,
   `residue_contact_distance 3.0`. Inspect `data/clusters_timeless/`.
6. **Big MD set crashes?** `swap yes`, `do_approximate_clustering yes`,
   bump `JAVA_OPTS="-Xmx32g"`.
