---
name: caver
description: >
  Run **CAVER 3.0 / 3.01** — the canonical tool from the Loschmidt
  Laboratories / Masaryk University for **identification, geometric
  characterization, clustering, and visualization of transport pathways
  (tunnels, channels, pores)** in macromolecular structures. CAVER
  operates on PDB files (a single static structure or an ensemble of MD
  snapshots) and returns the tunnels leading from a user-specified
  starting point inside the protein to the bulk solvent. Use this skill
  when:
  (1) Finding the access tunnel(s) connecting a buried active site /
      cofactor / co-substrate / catalytic residue to the protein
      surface, with their bottleneck radius, length, curvature,
      throughput, and priority — the headline CAVER use case,
  (2) Analyzing tunnel **dynamics** across a molecular-dynamics
      trajectory (10 / 100 / 1 000+ snapshots), clustering equivalent
      tunnels across frames into a small number of stable channels and
      ranking them by `Priority` (averaged throughput),
  (3) Comparing tunnels across **multiple homologs / variants / designs**
      that have been pre-aligned to a common frame — drop each one in
      as a snapshot and let CAVER's frame clustering group them,
  (4) Mapping which **residues line a tunnel or its bottleneck**
      (`compute_tunnel_residues`, `compute_bottleneck_residues`) — the
      starting point for **engineering residues** that gate substrate /
      product flux (Damborsky-lab tunnel engineering workflow),
  (5) Sampling tunnel geometry along the channel: tunnel **profiles**
      (per-position radius along the path, curvature, length) and the
      **bottleneck heat map** / **profile heat map** for ensembles,
  (6) Generating ready-to-display visualizations — a PyMOL session
      (`pymol/*_results.pse`) for static structures, VMD scripts
      (`vmd.sh`, `vmd_timeless.sh`) for trajectories, and per-cluster
      tunnel mesh PDBs,
  (7) Picking a **starting point** in one of three ways:
      `starting_point_atom` (one or more atom indices →
      centroid), `starting_point_residue` (one or more residue ids →
      centroid), or `starting_point_coordinates X Y Z` (explicit XYZ),
      with automatic re-optimization inside the cavity,
  (8) Choosing/tuning **clustering** (average-link clustering with a
      tunable `clustering_threshold`, optional approximate clustering
      for very large datasets, frame-clustering for redundancy
      removal),
  (9) Driving CAVER from a downstream pipeline (`protflow`, custom
      scripts) — the CLI is `java -cp lib -jar caver.jar -home <CAVER>
      -pdb <dir> -conf <config> -out <out>` and the outputs are
      well-structured CSVs + PDBs, easy to post-process with biotite /
      pandas.

  This skill is written for running CAVER from an **Apptainer /
  Singularity SIF container** (`CAVER.sif`, built from the `CAVER.def`
  shipped at `~/Repos/CAVER/CAVER.def` and placed in
  `$SINGULARITY_HOME`). The container bundles a JRE (Eclipse Temurin 21)
  plus the CAVER tree at `/opt/caver`, so you don't need Java on the
  host. CAVER itself is a CPU-only Java program — no GPU, no `--nv`.

  Hard limitations / gotchas:
  - CAVER **does not perform docking**. It finds geometric tunnels; it
    does not score ligand passage energetics. Pair with MD / SMD / steered
    sampling / CaverDock for that.
  - The starting point **must be inside the protein** (in a cavity, not
    outside the convex hull). Wrong placement is the #1 cause of
    "no tunnels found".
  - **Hydrogens are usually counter-productive**: the default atom radii
    are heavy-atom-only. Strip H before running, or accept that the
    bottleneck radii will be slightly conservative.
  - Default heap is small (4 GB). Large MD ensembles need
    `JAVA_OPTS="-Xmx16g"` or more.
  - CAVER expects standard PDB. mmCIF must be converted first
    (`biotite`, `gemmi`, `pymol`).

  Pairs with: `biotite` (clean and align inputs, compute downstream
  metrics on the predicted tunnel residues), `placer` / `boltz` /
  `chai-lab` / `protenix` (predict the bound complex first, then ask
  CAVER for the access tunnel to the ligand), `foundry` / `disco` /
  `boltzgen` (design enzymes / binders, then validate that a substrate
  tunnel actually exists), `protflow` (cluster-scale enzyme engineering
  with tunnel-aware filtering), GROMACS / OpenMM (run an MD trajectory,
  feed the snapshots to CAVER for dynamic-tunnel analysis), and the
  upstream **CaverDock** for ligand-transport energetics on the
  CAVER-defined tunnels.
license: GPL-3.0
category: protein-design
tags: [protein-analysis, tunnels, channels, pores, voronoi, transport-pathways, md-analysis, enzyme-engineering, active-site, bottleneck, java, apptainer, singularity, caver, loschmidt-laboratories, masaryk-university]
repo: http://www.caver.cz/
citation: "Chovancova E. et al. CAVER 3.0: A Tool for the Analysis of Transport Pathways in Dynamic Protein Structures. PLoS Comput Biol 8: e1002708 (2012). doi:10.1371/journal.pcbi.1002708"
---

# CAVER — analysis of transport tunnels in proteins

## What this is

CAVER 3.0 (this skill targets **3.01**, the latest 3.x patch) is the
reference implementation of Voronoi-diagram-based **tunnel finding**
inside macromolecular structures. Given a PDB file (or many PDBs from
an MD trajectory), a starting point inside a buried cavity, and a probe
radius, it:

1. Builds a Voronoi diagram of the atoms.
2. Finds least-cost paths from the starting point to the protein
   exterior — the **tunnels**.
3. Clusters equivalent tunnels (within and across snapshots) so a 100-
   frame MD trajectory collapses down to a handful of stable channels.
4. Characterizes each cluster: bottleneck radius, length, curvature,
   throughput, priority, lining residues, error bounds.
5. Emits CSV summaries, per-tunnel mesh PDBs, histograms / heat maps,
   and PyMOL / VMD visualizations.

This is the workhorse tool behind every paper that says "we engineered
residues lining the access tunnel" — it's how the Damborsky group
(authors) and the field at large enumerate the tunnels in the first
place.

> **Read first — three things that trip people up:**
>
> 1. **The starting point must be inside the protein.** If you pick a
>    surface residue or accidentally pass a ligand atom outside the fold,
>    CAVER will either fail to find any tunnel or find spurious ones. Use
>    `starting_point_residue <catalytic_residue_id>` against a buried
>    catalytic residue, or the centroid of three buried atoms with
>    `starting_point_atom <id> / starting_point_atom <id> /
>    starting_point_atom <id>`. CAVER auto-optimizes the location into
>    the nearest cavity (`max_distance` parameter).
> 2. **Probe radius drives sensitivity.** Default `probe_radius 0.9`
>    finds water-sized tunnels. Drop to `0.6` to also catch very narrow
>    channels (the examples in this repo all use `0.6`), or push up to
>    `1.4`+ to only find substrate-sized tunnels.
> 3. **For MD: one PDB per snapshot in one directory.** CAVER discovers
>    snapshots by listing `*.pdb` in the `-pdb` directory; per-frame
>    naming should be consistent (`1.pdb`, `2.pdb`, …). All snapshots
>    must use the **same** atom ordering for `starting_point_atom` to
>    work across frames.

## Quickstart — run from the Apptainer SIF

This skill assumes the SIF lives in `$SINGULARITY_HOME`:

```bash
export SINGULARITY_HOME=/path/to/dir/with/CAVER.sif
ls "$SINGULARITY_HOME"/CAVER.sif        # should exist
```

### 1) Build the SIF (one-time)

A definition file at `~/Repos/CAVER/CAVER.def` is provided:

```bash
cd ~/Repos/CAVER
apptainer build --fakeroot "$SINGULARITY_HOME"/CAVER.sif CAVER.def
```

It bundles **Eclipse Temurin 21 JRE** plus the CAVER tree at
`/opt/caver`. The image is small (~250 MB) and CPU-only — no `--nv`.
Build details: `references/installation.md`.

### 2) Run on a single static structure

Project layout:

```
proj/
├── 1AKD.pdb                 # the structure (heavy-atoms; stripped of waters / HETATM is safe)
├── config.txt               # CAVER parameters
└── out/                     # written by CAVER
```

Minimal `config.txt`:

```ini
# Pick the starting point — pick one of these three forms:
starting_point_atom 1234     # one or more atom indices (centroid)
# starting_point_residue 150
# starting_point_coordinates 17.012 24.139 7.790

probe_radius      0.9        # water-sized; 0.6 for very narrow tunnels
shell_radius      3
shell_depth       4

clustering_threshold      3.5
exclude_start_zone        2
exclude_end_zone          0
min_middle_zone           5

one_tunnel_in_snapshot    cheapest
generate_summary          yes
generate_tunnel_characteristics yes
generate_tunnel_profiles  yes
compute_tunnel_residues   yes
residue_contact_distance  3.0
```

Run:

```bash
mkdir -p proj/pdb && cp 1AKD.pdb proj/pdb/

apptainer run "$SINGULARITY_HOME"/CAVER.sif \
    -home /opt/caver \
    -pdb  ./proj/pdb \
    -conf ./proj/config.txt \
    -out  ./proj/out
```

CAVER reads `proj/pdb/*.pdb`, runs tunnel analysis, and writes
`proj/out/`.

### 3) Run on an MD ensemble

Same call, just stage the snapshots:

```
proj/
├── md_snapshots/
│   ├── 1.pdb
│   ├── 2.pdb
│   ├── ...
│   └── 100.pdb
├── config.txt
└── out/
```

```bash
apptainer run --env JAVA_OPTS="-Xmx16g" "$SINGULARITY_HOME"/CAVER.sif \
    -home /opt/caver \
    -pdb  ./proj/md_snapshots \
    -conf ./proj/config.txt \
    -out  ./proj/out
```

For dynamic runs you almost always want bigger heap
(`-Xmx16g`/`-Xmx32g`). See `references/troubleshooting.md::OOM`.

### 4) Read the output

```
out/
├── summary.txt                          # human-readable per-cluster table
├── summary_precise_numbers.csv          # same numbers, full precision
├── analysis/
│   ├── tunnel_characteristics.csv       # one row per (snapshot, tunnel)
│   └── tunnel_profiles.csv              # per-position radius along each tunnel
├── data/
│   ├── tunnels/                         # per-cluster mesh PDB
│   ├── tunnel_edges/                    # graph edges of the path
│   ├── clusters_timeless                # clustering metadata
│   ├── start_zone.pdb, end_zone.pdb     # protein vicinity at each end
│   ├── origins.pdb, v_origins.pdb       # starting-point cloud
│   ├── tree.txt, times.txt              # cluster hierarchy + timings
│   └── <input>.pdb                      # copies of input structures
├── pymol/
│   └── <input>_results.pse              # open in PyMOL
├── log.txt
└── warnings.txt
```

Always rank by **`Priority`** (column in `summary.txt` and
`summary_precise_numbers.csv`) — it's the throughput averaged over
**all** snapshots (zero for snapshots that had no tunnel). Higher = a
tunnel that's persistently open. Pick the top few clusters; ignore the
long tail. Full layout + every column documented in
`references/outputs.md`.

## Config file — the full taxonomy

CAVER is configured by a single text file (`-conf config.txt`),
organized into thematic blocks. Reference list with every parameter,
default, and recommended override: **`references/config.md`**.

Top-level groups (matching the upstream
`user_guide/config_default.txt`):

| Group | Examples | Purpose |
|-------|----------|---------|
| Calculation setup | `load_tunnels`, `load_cluster_tree`, `stop_after` | Resume / partial reruns |
| Input data | `time_sparsity`, `first_frame`, `last_frame` | Sub-sample / slice MD |
| Tunnel calculation | `starting_point_*`, `probe_radius`, `shell_radius`, `shell_depth` | The geometry knobs |
| Tunnel clustering | `clustering`, `clustering_threshold`, `weighting_coefficient`, `exclude_start_zone`, `min_middle_zone` | Group equivalent tunnels |
| Outputs | `generate_*`, `compute_tunnel_residues`, `compute_bottleneck_residues`, `bottleneck_heat_map_*`, `profile_heat_map_*` | What to emit |
| Advanced — start-point opt | `max_distance`, `desired_radius` | Repair starting points |
| Advanced — tunnel calc | `number_of_approximating_balls`, `add_central_sphere`, `automatic_shell_radius*`, `max_number_of_tunnels`, `cost_function_exponent` | Numerical stability |
| Advanced — redundancy removal | `frame_clustering`, `frame_clustering_threshold`, `frame_*_zone` | Drop near-duplicate tunnels |
| Advanced — surface averaging | `average_surface_frame`, `average_surface_global`, `average_surface_*_angle`, `average_surface_tunnel_sampling_step` | Smooth tunnel endpoints |
| Advanced — approximate clustering | `do_approximate_clustering`, `cluster_by_hierarchical_clustering`, `max_training_clusters` | Scale to huge MD sets |
| Advanced — outputs | `profile_tunnel_sampling_step`, `visualization_tunnel_sampling_step`, `visualize_tunnels_per_cluster`, `visualization_subsampling` | Resolution of CSV / VMD |
| Others | `swap`, `seed`, `path_to_vmd`, `generate_trajectory`, `long_residue_names` | Reproducibility, side effects |

## Choosing a starting point

CAVER auto-centers the starting point in the nearest cavity within
`max_distance` (default 3 Å). You give it a *hint*:

```ini
# Most precise — one or more atom serial numbers; CAVER uses their centroid:
starting_point_atom 578
starting_point_atom 1609
starting_point_atom 3258

# Or a residue (centroid of the residue's atoms):
starting_point_residue 150

# Or an explicit XYZ in PDB coordinates:
starting_point_coordinates 17.012 24.139 7.790
```

For an enzyme: pick atoms from the catalytic residue(s). For a
membrane channel: pick a residue at the constriction. For a known
ligand: pick atoms from the ligand. If your "cavity" guess is wrong,
`max_distance` controls how far CAVER will hunt — bump it (with
caution) or pick a better hint.

Detail and examples: `references/inputs.md::Starting points`.

## Visualization

CAVER writes:

- **PyMOL** session: `pymol/<input>_results.pse` (static structures and
  small ensembles).
- **VMD** launcher scripts in the output: `vmd.sh`, `vmd_timeless.sh`,
  `vmd.bat`, `vmd_timeless.bat` plus the .tcl drivers
  (`view.tcl`, `view_timeless.tcl`). Set `path_to_vmd` in the config or
  edit the shell scripts.
- Per-cluster **tunnel mesh PDBs** under `data/tunnels/` you can load
  into any molecular viewer (PyMOL `load`, ChimeraX `open`, VMD).

Full visualization recipes (incl. headless rendering): `references/visualization.md`.

## CLI reference

`caver.jar` accepts these flags:

| Flag | Purpose |
|------|---------|
| `-home <dir>` | CAVER installation (must contain `bin/atom_radii.csv`, `lib/`, `caver.jar`). In the SIF: `/opt/caver`. |
| `-pdb <dir>` | Directory of input `*.pdb` files (one snapshot per file). |
| `-conf <file>` | Path to the config file. |
| `-out <dir>` | Output directory (created if missing). |
| `-help` | Brief usage |

Standard invocation pattern (what the SIF's `%runscript` runs for you):

```bash
java ${JAVA_OPTS} -cp /opt/caver/lib -jar /opt/caver/caver.jar \
    -home /opt/caver -pdb <pdb_dir> -conf <conf> -out <out>
```

`JAVA_OPTS` defaults to `-Xmx4g` inside the SIF — override with
`--env JAVA_OPTS="-Xmx16g"` for big jobs.

## Gotchas (read before you debug)

1. **No tunnels found** → starting point is outside the protein, or
   `probe_radius` is too large, or `shell_radius`/`shell_depth` is
   wrong. Drop `probe_radius` to 0.6, verify the starting coords lie
   inside the cavity (e.g. visualize `origins.pdb` from a quick
   `generate_summary yes` run).
2. **Spurious surface "tunnels"** → starting point isn't actually
   buried. Pick a deeper hint atom or tighten `max_distance`.
3. **Out of memory** (`java.lang.OutOfMemoryError: Java heap space`) →
   bump `JAVA_OPTS` (`--env JAVA_OPTS="-Xmx16g"` for the SIF).
4. **`Residue name not in atom_radii.csv`** → custom residue. Either
   add to `caver/bin/atom_radii.csv` (or a bind-mounted override) or
   set `long_residue_names yes` if the issue is just a 4-letter name.
5. **MD trajectory frames not aligned** → CAVER doesn't align for you.
   Use VMD / `gmx trjconv` / mdtraj to align all frames to a reference
   first, otherwise the clustering will see "moving" tunnels.
6. **PDB has multiple chains and HETATM ligands** → fine for tunnel
   geometry, but visualizations get cluttered. Many users strip
   waters/cofactors before running and add them back for the PyMOL
   session if needed.
7. **`one_tunnel_in_snapshot cheapest`** vs **`no`** → set to `no` if
   you want every distinct tunnel per snapshot in the per-frame CSV.
   Default `cheapest` is appropriate for the summary view.
8. **`seed` is random by default.** Always set `seed 1` (or any
   integer) for reproducibility.

Full failure modes: `references/troubleshooting.md`.

## Reference index

- `references/installation.md` — building the SIF (`CAVER.def`,
  fakeroot, the `/opt/caver` layout, native Java fallback for
  Linux/Windows/macOS, VMD/PyMOL availability).
- `references/inputs.md` — PDB requirements, starting-point modes,
  snapshot directory layout, atom-radii customization, MD prep.
- `references/config.md` — every config parameter with semantics,
  defaults, units, and recommended overrides.
- `references/outputs.md` — directory layout, every CSV column, mesh
  PDB conventions, log/warning files.
- `references/clustering.md` — average-link clustering, threshold
  intuition, frame clustering, approximate clustering for big sets,
  zones.
- `references/visualization.md` — PyMOL session, VMD scripts,
  headless rendering, custom palettes.
- `references/troubleshooting.md` — build, runtime, and "no tunnels"
  failure modes.
- `examples/CAVER.def` — the Apptainer definition file (mirror of
  upstream).
- `examples/commandline_examples.sh` — copy-paste invocations.
- `examples/config_static.txt` — minimal config for a single PDB.
- `examples/config_md.txt` — full config for an MD ensemble.
- `examples/run_caver.sh` — wrapper that resolves `$SINGULARITY_HOME`
  and forwards args.

## Installing this skill

```bash
# Symlink (recommended — picks up edits live)
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/caver
# Or copy:
cp -R . ~/.claude/skills/caver
```

After that, an agent invokes it via `Skill(skill="caver")`.

## Citation

CAVER 3.0 / 3.01, Loschmidt Laboratories, Masaryk University. GPL-3.0.

```
Chovancova, E., Pavelka, A., Benes, P., Strnad, O., Brezovsky, J.,
Kozlikova, B., Gora, A., Sustr, V., Klvana, M., Medek, P.,
Biedermannova, L., Sochor, J., Damborsky, J. (2012).
CAVER 3.0: A Tool for the Analysis of Transport Pathways in Dynamic
Protein Structures. PLoS Comput Biol 8: e1002708.
doi:10.1371/journal.pcbi.1002708
```
