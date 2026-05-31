# Installation — building & running the CAVER SIF

CAVER is a Java program. The container approach packages a JRE plus the
CAVER 3.01 source tree so you don't need Java on the host and the same
SIF runs on any Linux node.

## The `$SINGULARITY_HOME` convention

```bash
export SINGULARITY_HOME=/path/to/dir/with/sifs
ls "$SINGULARITY_HOME"/CAVER.sif      # this is the image
```

Every command in the skill resolves the image via that variable.

## What's in the SIF

From `CAVER.def` (Bootstrap: docker, From: `eclipse-temurin:21-jre-noble`):

- **OS**: Ubuntu 24.04 (`noble`) base.
- **Java**: Eclipse Temurin 21 JRE (LTS).
- **CAVER 3.01**: copied to **`/opt/caver`**. Inside:
  - `caver.jar` — the main entry point.
  - `lib/` — `AverageLinkClustering.jar`, `kd.jar` (k-d tree), `ml.jar`
    (Weka 3.6.5), `vecmath.jar`.
  - `bin/` — `atom_radii.csv` (default radii by element/residue),
    Python visualization scripts (`view.py`, `view_plugin.py`, …),
    tcl drivers for VMD, citation, palette PNGs.
  - `license/license.txt` — GPL-3.0.
- **Examples** at `/opt/caver/examples`: `QUICK_START`,
  `static_structures/{1AKD,1BL8,1MXT,2ACE,2BG9,2OAR}`,
  `guided_example`.
- **User guide PDFs** at `/opt/caver/user_guide`.
- `/workspace` is created and ready as a bind-mount target.
- **`%runscript`** runs:
  ```bash
  exec java ${JAVA_OPTS} -cp /opt/caver/lib -jar /opt/caver/caver.jar "$@"
  ```
  …so `apptainer run CAVER.sif <flags>` is equivalent to
  `java -jar caver.jar <flags>` with `JAVA_OPTS` injected.

`JAVA_OPTS` defaults to `-Xmx4g`. Override at run time.

## Build it

### Locally with fakeroot

```bash
cd ~/Repos/CAVER
apptainer build --fakeroot "$SINGULARITY_HOME"/CAVER.sif CAVER.def
```

You need an apptainer build where unprivileged user-namespace builds
are enabled (`/etc/subuid`, `/etc/subgid`, `apptainer-fakeroot`).

### With `sudo`

```bash
sudo apptainer build "$SINGULARITY_HOME"/CAVER.sif CAVER.def
```

### Build resources

- Base image: ~250 MB (eclipse-temurin 21-jre-noble).
- CAVER tree: ~25 MB.
- **Final SIF**: ~250-300 MB. Tiny relative to ESM / Boltz / Protenix
  images — CAVER has no PyTorch dependency.

### On a cluster

The build is trivial — no GPU, no kernel modules. Build on a
workstation and `scp` the SIF to the cluster, or build directly on a
login node if `apptainer` is available there.

## Run it

### Default — `apptainer run`

```bash
apptainer run "$SINGULARITY_HOME"/CAVER.sif \
    -home /opt/caver \
    -pdb  ./md_snapshots \
    -conf ./config.txt \
    -out  ./out
```

Apptainer auto-mounts `$HOME` and `$PWD`, so the relative paths above
resolve to the host's current directory.

### Override JVM heap (essential for big jobs)

```bash
apptainer run --env JAVA_OPTS="-Xmx16g" "$SINGULARITY_HOME"/CAVER.sif \
    -home /opt/caver -pdb ./md -conf ./conf.txt -out ./out
```

`JAVA_OPTS` is read by the `%runscript` and inserted on the `java`
command line. You can pass any other JVM flags here too
(`-Xms`, `-XX:+UseG1GC`, etc.).

### `apptainer exec` — for ad-hoc commands

```bash
# Show the CAVER help text:
apptainer exec "$SINGULARITY_HOME"/CAVER.sif \
    java -cp /opt/caver/lib -jar /opt/caver/caver.jar -help

# Run the bundled QUICK_START example:
apptainer exec "$SINGULARITY_HOME"/CAVER.sif bash -c '
  cd /opt/caver/examples/QUICK_START/inputs && \
  java -Xmx1200m -cp /opt/caver/lib -jar /opt/caver/caver.jar \
       -home /opt/caver -pdb ../md_snapshots -conf ./config.txt -out ./out
'
```

### `apptainer shell` — interactive

```bash
apptainer shell "$SINGULARITY_HOME"/CAVER.sif
Apptainer> java -version
Apptainer> ls /opt/caver
Apptainer> cat /opt/caver/bin/citation.txt
```

### Why no `--nv`?

CAVER is pure Java + CPU. There is **no** CUDA / OpenCL / GPU path —
adding `--nv` does nothing useful and just nags about missing drivers
if the host lacks them.

## Bind-mounts

Apptainer auto-mounts `$HOME` and `$PWD`. Anything else needs a bind:

```bash
apptainer run \
    --bind /data/proteins:/data/proteins \
    --bind /scratch/$USER/caver:/work \
    "$SINGULARITY_HOME"/CAVER.sif \
    -home /opt/caver \
    -pdb  /data/proteins/md_2OAR \
    -conf /work/config.txt \
    -out  /work/out_2OAR
```

Common patterns:

| Bind | Why |
|------|-----|
| `--bind /scratch/$USER:/work` | Write outputs to fast scratch |
| `--bind /data:/data` | Project data dir |
| `--bind /tmp:/tmp` | Override apptainer's default tmpfs (CAVER buffers some intermediates here for big MD jobs) |

### Overriding `atom_radii.csv` (custom residues / modifications)

The bundled radii file is at `/opt/caver/bin/atom_radii.csv` inside the
SIF. To use a custom radii table without rebuilding:

```bash
# Bind your edited copy on top of the SIF's:
apptainer run \
    --bind ./my_atom_radii.csv:/opt/caver/bin/atom_radii.csv \
    "$SINGULARITY_HOME"/CAVER.sif \
    -home /opt/caver -pdb ./md -conf ./config.txt -out ./out
```

Format: `<residue3>  <atom_name>  <radius_Å>` per row. CAVER falls
back to a per-element default for unknown atoms (the warning is
written to `out/warnings.txt`).

## Native (non-container) installs

If you can't / don't want to use apptainer:

### Linux / macOS — Java only

```bash
# 1. Install a Java 8+ runtime (CAVER 3.01 works on Java 8 through 21).
sudo apt install -y default-jre         # Debian/Ubuntu
brew install openjdk                    # macOS

# 2. Use the source tree directly:
cd ~/Repos/CAVER/caver_3.0/examples/QUICK_START/inputs
java -Xmx1200m -cp ../../../caver/lib -jar ../../../caver/caver.jar \
     -home ../../../caver -pdb ../md_snapshots -conf ./config.txt -out ./out
```

This is exactly what `caver.sh` in the examples does. The SIF just
provides a portable JRE.

### Windows

```cmd
cd caver_3.0\examples\QUICK_START\inputs
java -Xmx1200m -cp ..\..\..\caver\lib -jar ..\..\..\caver\caver.jar ^
     -home ..\..\..\caver -pdb ..\md_snapshots -conf .\config.txt -out .\out
```

Same as `caver.bat`. No SIF on Windows; use the native Java install.

## VMD (optional, for trajectory visualization)

CAVER emits VMD launcher scripts (`vmd.sh`, `vmd_timeless.sh`, etc.)
but **doesn't bundle VMD**. To use them:

- Install VMD on the host (https://www.ks.uiuc.edu/Research/vmd/).
- Set `path_to_vmd` in `config.txt` to the host VMD binary,
  **or** edit the generated `vmd.sh` to reference `$linux_vmd` (the
  variable the script reads).
- The container doesn't need to know about VMD; the visualization
  scripts are post-processing artifacts you run on the host.

For headless cluster nodes, render PyMOL sessions (`pymol/*.pse`) on a
local workstation instead.

## PyMOL (optional, for static-structure visualization)

CAVER writes `pymol/<input>_results.pse`. Open it in any PyMOL
install:

```bash
pymol out/pymol/1AKD_results.pse
```

The session embeds the input structure plus per-cluster tunnel meshes
already coloured by `Priority`.

## Verifying a build

```bash
# Header + labels:
apptainer inspect "$SINGULARITY_HOME"/CAVER.sif

# %test from the def file (java -version + caver -help):
apptainer test "$SINGULARITY_HOME"/CAVER.sif

# Run the QUICK_START example end-to-end (~5 seconds):
mkdir -p /tmp/cavertest && cd /tmp/cavertest && \
  cp -r /opt/caver/examples/QUICK_START/* . 2>/dev/null || \
  apptainer exec "$SINGULARITY_HOME"/CAVER.sif \
      cp -r /opt/caver/examples/QUICK_START /tmp/cavertest

apptainer run "$SINGULARITY_HOME"/CAVER.sif \
    -home /opt/caver \
    -pdb  /tmp/cavertest/QUICK_START/md_snapshots \
    -conf /tmp/cavertest/QUICK_START/inputs/config.txt \
    -out  /tmp/cavertest/QUICK_START/out

ls /tmp/cavertest/QUICK_START/out
# Expect: summary.txt, summary_precise_numbers.csv, analysis/, data/, pymol/, log.txt
```

A healthy run prints (to stdout / `log.txt`) the per-frame tunnel count
and the final clustering summary, and writes the directory tree above.
