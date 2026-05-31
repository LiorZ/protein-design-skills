# Troubleshooting

Failure modes you'll hit, in roughly the order you hit them.

## Build (apptainer build CAVER.sif CAVER.def)

### "could not switch to user namespace" / "permission denied"

Fakeroot isn't configured. Either:

```bash
sudo apt-get install apptainer-suid apptainer-fakeroot
sudo apptainer config fakeroot --add $USER
```

…or fall back to `sudo apptainer build`.

### "No such file or directory: caver_3.0/caver"

You ran `apptainer build` from the wrong directory. The `%files`
paths in `CAVER.def` are relative; run from `~/Repos/CAVER`:

```bash
cd ~/Repos/CAVER
apptainer build --fakeroot CAVER.sif CAVER.def
```

### "Unable to find image 'eclipse-temurin:21-jre-noble'"

Apptainer can't reach Docker Hub. Either pre-fetch:

```bash
APPTAINER_DOCKER_USERNAME='' apptainer pull docker://eclipse-temurin:21-jre-noble
```

…or build against a different JRE (edit `From:` in the `.def`, any
`openjdk:21-jre`-ish image works — CAVER 3.01 runs on Java 8+).

## Run (apptainer run CAVER.sif …)

### `java.lang.OutOfMemoryError: Java heap space`

Default heap is 4 GB. Bump it:

```bash
apptainer run --env JAVA_OPTS="-Xmx16g" \
    "$SINGULARITY_HOME"/CAVER.sif \
    -home /opt/caver -pdb ./md -conf ./config.txt -out ./out
```

For very large MD ensembles (1 000+ snapshots), 32-64 GB is common. If
your host doesn't have it, try `do_approximate_clustering yes` and
`swap yes` in `config.txt`.

### `Error: Unable to access jarfile /opt/caver/caver.jar`

The `%files` block didn't pick up the CAVER tree. Confirm the source:

```bash
ls -la /home/lior/Repos/CAVER/caver_3.0/caver/caver.jar
apptainer inspect "$SINGULARITY_HOME"/CAVER.sif | head -20
```

Rebuild after fixing the path.

### "No tunnels found" / `summary.txt` is empty

Most common cause: **bad starting point**. Order of operations:

1. Visualize `out/data/origins.pdb` — are the points inside the
   protein, in the expected cavity?
2. Lower the probe: `probe_radius 0.6`. The bundled static-structure
   examples all use 0.6.
3. Check `out/warnings.txt` for "starting point optimization moved
   >= max_distance" or "no path to surface".
4. Increase `max_distance` (cautiously): `max_distance 5`.
5. For a multi-chain structure, ensure your starting hint is in the
   correct chain — `starting_point_residue A150` not just `150`.
6. Confirm the structure isn't broken. `grep -c '^ATOM ' input.pdb`
   should be 4-figure for a real protein.

### "Spurious surface tunnels everywhere"

Your starting point isn't actually buried. Symptoms:

- Many short, near-straight tunnels with `Length < 5 Å`.
- `summary.txt` has 20+ clusters with similar high `Priority`.

Fixes:

- Pick a deeper hint atom (use a sidechain heavy atom of a buried
  residue, not the Cα of a surface residue).
- Tighten `max_distance` to 1-2 Å so CAVER can't drift to a surface
  position.
- Increase `min_middle_zone` (`5 → 10`) — drops very short paths.

### `Residue name <XYZ> not in atom_radii.csv`

CAVER falls back to element-based radii. Usually fine for cofactors
(heme, NAD, ATP) — confirm with `out/warnings.txt`. To add explicit
radii:

```bash
# Edit a local copy:
cp /opt/caver/bin/atom_radii.csv ./my_radii.csv
# …add lines like:
#   HEM  FE   1.50
#   HEM  NA   1.55
#   HEM  NB   1.55
# Then bind-mount:
apptainer run \
    --bind ./my_radii.csv:/opt/caver/bin/atom_radii.csv \
    "$SINGULARITY_HOME"/CAVER.sif ...
```

### Tunnel results vary between identical runs

`seed` is random by default. Set it explicitly for reproducibility:

```ini
seed 1
```

…and CAVER will produce identical tunnels (modulo float
non-determinism, which is small).

### MD ensemble: clusters are jittery / non-physical

Your frames aren't aligned to a common reference. CAVER assumes a
fixed protein frame. Fix:

```bash
# GROMACS:
gmx trjconv -s ref.gro -f traj.xtc -fit rot+trans -o aligned.xtc
# Then dump every Nth frame to PDB:
gmx trjconv -s ref.gro -f aligned.xtc -dt 100 -sep -o frame_.pdb
```

Or use VMD's RMSD trajectory tool / mdtraj `superpose`.

### "Snapshot 17.pdb has no tunnels at probe_radius 0.9"

That frame happens to close the channel. Two interpretations:

- **Real**: the channel is dynamically gated — this is the signal you
  wanted. The `Priority` for that cluster will be reduced because the
  frame contributes 0.
- **Artifact**: the frame is mid-equilibration / has a bad conformation.
  Drop it via `first_frame` / `last_frame` slicing or post-hoc filtering.

### `out/warnings.txt` complains about long residue names

CAVER 3.01 reads 4-letter residues by default. If a structure has a
genuine 3-letter residue whose name happens to bleed into column 21
(e.g. some old-school all-caps numbered residues), turn off the
extension:

```ini
long_residue_names no
```

### PyMOL `.pse` won't open

You're using an old PyMOL (≤ 2.5)? CAVER's `.pse` files are written
with modern PyMOL conventions. Update:

```bash
conda install -c conda-forge "pymol-open-source>=2.5"
```

### `vmd.sh` does nothing / `unable to open scripts/view.tcl`

The launcher uses a relative path. Run it **from the output directory**:

```bash
cd out
bash vmd.sh
```

Or set `path_to_vmd` in `config.txt` before running CAVER so the
generated scripts reference the right binary.

## Performance

### CAVER is slow on a 5 000-frame trajectory

- `swap no` — keep everything in RAM (need bigger `-Xmx`).
- `do_approximate_clustering yes`, `cluster_by_hierarchical_clustering 5000`.
- `number_of_approximating_balls 4` (down from 12) — coarser geometry,
  faster path search. Acceptable for big membrane channels (the 2BG9
  example uses 4).
- `time_sparsity 5` — process every 5th frame.
- `save_dynamics_visualization no` — visualization is slow; do it
  only on a sub-sampled ensemble.

### Per-frame time keeps climbing

CAVER allocates per-frame; long runs may benefit from
`-XX:+UseG1GC -XX:MaxGCPauseMillis=500` in `JAVA_OPTS`. Default GC is
fine for most jobs.

## Network / no-internet failures

CAVER itself **never** hits the network at runtime. If you see network
errors, they're from:

- The `apptainer build` step (Docker Hub for the base image).
- An optional VMD/PyMOL post-process you wrote yourself.

Run the SIF on an air-gapped node without any extra flags — it works.

## "Help, the residues lining the tunnel are wrong"

`compute_tunnel_residues yes` outputs residues within
`residue_contact_distance` of any tunnel point. Adjust:

- **Too many residues**: drop the cutoff (`3.0 → 2.5`).
- **Too few**: bump (`3.0 → 4.0`).
- **Confused which cluster**: the output is per-cluster; look at
  `data/clusters_timeless/`.

The tunnel-lining residue list is the input to engineering — verify
it visually by colouring those residues in PyMOL alongside the tunnel
mesh.

## Reproducing the bundled examples

```bash
# QUICK_START (MD ensemble of 10 snapshots, ~5 sec runtime):
apptainer run "$SINGULARITY_HOME"/CAVER.sif \
    -home /opt/caver \
    -pdb  /opt/caver/examples/QUICK_START/md_snapshots \
    -conf /opt/caver/examples/QUICK_START/inputs/config.txt \
    -out  ./quickstart_out

# 1AKD static structure:
apptainer run "$SINGULARITY_HOME"/CAVER.sif \
    -home /opt/caver \
    -pdb  /opt/caver/examples/static_structures/1AKD/inputs \
    -conf /opt/caver/examples/static_structures/1AKD/inputs/config.txt \
    -out  ./1AKD_out
```

Compare your `summary.txt` to the bundled
`/opt/caver/examples/static_structures/1AKD/results/summary.txt` — if
the numbers match, the install is sane.

## When to escalate to upstream

If you've ruled out the above and still see wrong tunnels:

- Forum / mailing list: http://www.caver.cz/
- Citation contact: Damborsky lab, Masaryk University.

Useful diagnostics to attach:

- `out/log.txt` and `out/warnings.txt`.
- A trimmed `config.txt`.
- A single representative input PDB.
- The output of `apptainer inspect CAVER.sif`.
