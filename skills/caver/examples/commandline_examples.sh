#!/usr/bin/env bash
# Copy-paste invocations for the CAVER SIF.
# Assumes:  export SINGULARITY_HOME=/path/to/dir/with/CAVER.sif
set -euo pipefail

SIF="${SINGULARITY_HOME:?must export SINGULARITY_HOME}/CAVER.sif"

# -----------------------------------------------------------------------------
# 1) Build the SIF (one-time)
# -----------------------------------------------------------------------------
# cd ~/Repos/CAVER
# apptainer build --fakeroot "$SIF" CAVER.def
#  …or:
# sudo apptainer build "$SIF" CAVER.def

# -----------------------------------------------------------------------------
# 2) Smoke test (no -Xmx needed, just version + help)
# -----------------------------------------------------------------------------
apptainer exec "$SIF" java -version
apptainer exec "$SIF" \
    java -cp /opt/caver/lib -jar /opt/caver/caver.jar -help || true

# -----------------------------------------------------------------------------
# 3) Run the bundled QUICK_START example (MD ensemble, ~5 seconds)
# -----------------------------------------------------------------------------
mkdir -p /tmp/caver_quickstart && cd /tmp/caver_quickstart
apptainer exec "$SIF" cp -r /opt/caver/examples/QUICK_START .
apptainer run "$SIF" \
    -home /opt/caver \
    -pdb  /tmp/caver_quickstart/QUICK_START/md_snapshots \
    -conf /tmp/caver_quickstart/QUICK_START/inputs/config.txt \
    -out  /tmp/caver_quickstart/QUICK_START/out

ls /tmp/caver_quickstart/QUICK_START/out
# Expect: summary.txt, summary_precise_numbers.csv, analysis/, data/, pymol/

# -----------------------------------------------------------------------------
# 4) Run on a single static structure (your project)
# -----------------------------------------------------------------------------
#  Layout:
#   proj/
#   ├── pdb/1AKD.pdb
#   ├── config.txt          # see examples/config_static.txt
#   └── out/                # will be created
mkdir -p proj/pdb proj/out
# cp <YOUR_STRUCTURE>.pdb proj/pdb/
# cp ../config_static.txt proj/config.txt

apptainer run "$SIF" \
    -home /opt/caver \
    -pdb  ./proj/pdb \
    -conf ./proj/config.txt \
    -out  ./proj/out

# -----------------------------------------------------------------------------
# 5) Run on an MD trajectory with a larger heap
# -----------------------------------------------------------------------------
#  Layout:
#   proj/
#   ├── md_snapshots/{1..100}.pdb        # one PDB per frame (aligned!)
#   ├── config.txt                       # see examples/config_md.txt
#   └── out/

apptainer run --env JAVA_OPTS="-Xmx16g" "$SIF" \
    -home /opt/caver \
    -pdb  ./proj/md_snapshots \
    -conf ./proj/config.txt \
    -out  ./proj/out

# -----------------------------------------------------------------------------
# 6) Bind a custom atom_radii.csv (for non-canonical cofactors)
# -----------------------------------------------------------------------------
# Edit a copy of /opt/caver/bin/atom_radii.csv with your additions, then:
apptainer run \
    --bind ./my_atom_radii.csv:/opt/caver/bin/atom_radii.csv \
    "$SIF" \
    -home /opt/caver -pdb ./pdb -conf ./config.txt -out ./out

# -----------------------------------------------------------------------------
# 7) Re-cluster without recomputing tunnels (cheap iteration)
# -----------------------------------------------------------------------------
#  In config.txt:
#    load_tunnels       yes
#    load_cluster_tree  yes        # also reuse the tree (fastest)
#    clustering_threshold 5.0      # new cut height
apptainer run "$SIF" \
    -home /opt/caver \
    -pdb  ./proj/md_snapshots \
    -conf ./proj/config_recluster.txt \
    -out  ./proj/out                # point at the SAME out dir

# -----------------------------------------------------------------------------
# 8) Interactive shell
# -----------------------------------------------------------------------------
apptainer shell "$SIF"
# Inside:
#   Apptainer> java -version
#   Apptainer> ls /opt/caver
#   Apptainer> cat /opt/caver/bin/citation.txt

# -----------------------------------------------------------------------------
# 9) Render the PyMOL session on a workstation
# -----------------------------------------------------------------------------
# (PyMOL is NOT inside the SIF; install via conda/brew/apt on your local box.)
# pymol proj/out/pymol/1AKD_results.pse
# Or headless:
# pymol -cq -d "load proj/out/pymol/1AKD_results.pse; ray 1600 1200; png tunnels.png"

# -----------------------------------------------------------------------------
# 10) Time-resolved VMD movie (requires VMD on the host)
# -----------------------------------------------------------------------------
# export linux_vmd=/usr/local/bin/vmd
# cd proj/out
# bash vmd.sh                  # time-resolved
# bash vmd_timeless.sh         # time-collapsed
