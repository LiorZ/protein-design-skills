# Clustering — how CAVER groups tunnels

CAVER runs **two stages** of clustering:

1. **Per-frame clustering** (`frame_clustering yes`): inside one
   snapshot, near-duplicate tunnels (alternative paths to the same
   exit) are merged.
2. **Inter-frame clustering** (`clustering average_link`): tunnels from
   *different* snapshots are grouped into clusters that represent the
   "same" channel, so a 100-snapshot MD trajectory ends up as a small
   handful of named tunnels.

The output `summary.txt` ranks the inter-frame clusters by `Priority`.

## The distance function

A tunnel is a polyline in 3D with radii at each point. CAVER's
pairwise distance between two tunnels:

- Aligns by arc-length from the (shared) starting point.
- For each sampled point along both, computes a weighted spatial
  distance:
  ```
  d_ij = sqrt(  (Δx² + Δy² + Δz²)  +  w · (Δr)²  )
  ```
  where `w = weighting_coefficient`.
- The tunnel-to-tunnel distance is the average over points in the
  middle zone (`exclude_start_zone` and `exclude_end_zone` trim the
  endpoints).
- If after trimming the overlap is < `min_middle_zone`, the pair is
  declared incomparable and one is dropped.

`weighting_coefficient` controls how much the bottleneck radius
matters vs. spatial path:

- `w = 0`: purely positional (two paths through the same backbone
  region are equivalent regardless of radius).
- `w = 1`: balanced (default).
- `w > 1`: emphasizes radius differences — useful when two tunnels
  occupy the same corridor but one is a narrow side-pocket variant.

## Average-link clustering (`clustering average_link`)

The only supported algorithm. CAVER builds the full pairwise distance
matrix between all tunnels, then runs **UPGMA** (unweighted pair-group
method with arithmetic mean): repeatedly merges the two clusters
whose average inter-cluster distance is smallest. Cut the dendrogram
at `clustering_threshold` to get the final clusters.

Choosing the threshold:

- **Lower** (e.g. 2.0): more, finer clusters. Useful when you suspect
  several distinct tunnels share a region of the protein.
- **Default** (3.5): typically gives 3-10 named clusters.
- **Higher** (e.g. 5-6): aggressively merge into a few canonical
  channels. Useful when MD jitter creates many micro-variants.

The full dendrogram is dumped to `data/tree.txt`. To re-cluster
without recomputing tunnels:

```ini
load_tunnels       yes
load_cluster_tree  yes
clustering_threshold 4.0
```

…and re-run CAVER pointing `-out` at the **same** output directory.

## Frame clustering — the inner stage

`frame_clustering` removes near-duplicate paths *within* a single
snapshot. Without it, CAVER's path search will enumerate many
near-redundant traversals of the same channel (different vertex
sequences in the Voronoi graph).

Knobs:

| Param | Default | Effect |
|-------|---------|--------|
| `frame_clustering` | `yes` | Master switch |
| `frame_weighting_coefficient` | `1` | Same role as the inter-frame `w` |
| `frame_clustering_threshold` | `1` | Distance cut for de-duplication |
| `frame_exclude_start_zone` | `0` Å | Trim near the origin |
| `frame_exclude_end_zone` | `0` Å | Trim near the exit |
| `frame_min_middle_zone` | `5` Å | Min comparable length |

Most static-structure examples in the bundled set use
`frame_clustering_threshold 2` to be more aggressive (the 1AKD,
1BL8, 2BG9 example configs all set this).

For an MD ensemble: leave the defaults unless you see a single corridor
exploding into many "frame siblings" in the per-frame
`tunnel_characteristics.csv`.

## Zones (`exclude_*` and `min_middle_*`)

Tunnels share a starting region and often converge near the surface,
so naively comparing whole paths makes everything look similar. The
**zones** parameters carve out a comparable middle section.

```
   START_POINT  →  [excluded start_zone]  [middle zone — comparable]  [excluded end_zone]  → SURFACE
                            2 Å                  ≥ 5 Å                       0 Å
                       (exclude_start_zone)  (min_middle_zone)        (exclude_end_zone)
```

If the middle zone is too short after exclusions, the tunnel is
dropped from the comparison (and may get its own singleton cluster).

`save_zones yes` writes `start_zone.pdb` / `end_zone.pdb` to `data/`.
Visualize alongside the tunnels to confirm the zones look sensible.

## Approximate clustering (big datasets)

Average-link clustering is `O(N²)` in tunnels. For 10 000+ tunnels
this becomes infeasible. Switch on the approximate mode:

```ini
do_approximate_clustering            yes
cluster_by_hierarchical_clustering   20000   # exact for first N tunnels
max_training_clusters                15      # initial seeds
generate_unclassified_cluster        no
```

How it works:

1. Run **exact** average-link on the first
   `cluster_by_hierarchical_clustering` tunnels (the "training set").
2. Pick `max_training_clusters` centroids from that.
3. Assign every remaining tunnel to its nearest centroid (k-means
   style).

Trade-off: faster, slightly worse clusters near the boundaries.
`generate_unclassified_cluster yes` collects tunnels too far from any
centroid into a labeled "uncategorized" bucket (useful diagnostic for
whether your training set was representative).

## Tuning recipe — over-/under-merging

You ran CAVER, opened `summary.txt`, and it says 1 cluster or 47
clusters. Walk through:

1. **One mega-cluster** swallowing everything:
   - Lower `clustering_threshold` (`3.5 → 2.0`).
   - Increase `weighting_coefficient` (`1 → 2`) so radius differences
     count more.
   - Lower `exclude_start_zone` and `exclude_end_zone` — too-aggressive
     exclusion can collapse different paths.
   - Confirm with `data/tree.txt` that the dendrogram has real
     structure below your threshold.
2. **Hundreds of tiny clusters**:
   - Increase `clustering_threshold` (`3.5 → 5.5`).
   - Increase `frame_clustering_threshold` (more aggressive
     intra-frame dedup).
   - Drop `weighting_coefficient` (`1 → 0.5`) — radius variation is
     noisy, position is stable.
   - Bump `min_middle_zone` (`5 → 8`) — drops short, hard-to-compare
     tunnels.
3. **Stable clusters, but ranked unexpectedly**:
   - Inspect `Priority` vs `Avg_throughput` in `summary.txt`. A cluster
     with low Priority + high `Avg_throughput` is "open in few frames,
     but wide when open". For *engineering* the substrate's main
     entrance, you want both high.

## Re-clustering without re-tunneling

After a long MD run, recomputing the geometry is expensive but
re-clustering is cheap. Set:

```ini
load_tunnels       yes
load_cluster_tree  no            # rebuild the tree from the loaded tunnels
clustering_threshold 4.0
exclude_start_zone   2
```

…and run CAVER again with the **same** `-out` directory. It will read
the tunnels from `out/data/` and only rerun the clustering / outputs.

Or to re-cut the existing dendrogram (no recompute at all):

```ini
load_tunnels       yes
load_cluster_tree  yes
clustering_threshold 5.5
```

This is the fastest knob — change only `clustering_threshold` and
re-run.
