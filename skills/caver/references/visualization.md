# Visualization — PyMOL, VMD, headless rendering

CAVER emits visualization assets in three forms:

1. A **PyMOL session** (`pymol/<input>_results.pse`) — open and look.
2. **VMD launcher scripts** (`vmd.sh`, `vmd_timeless.sh`) for
   trajectories.
3. **Per-cluster tunnel mesh PDBs** under `data/tunnels/<cluster>/` —
   load into any viewer.

CAVER itself doesn't bundle PyMOL or VMD; the SIF doesn't either. The
visualization assets are post-processing artifacts you open with
whatever you have on your workstation.

## PyMOL session (`pymol/<input>_results.pse`)

The simplest path. The session contains:

- The input structure (one model — the first if multiple snapshots).
- All clustered tunnels coloured by `Priority` (best cluster = brightest).
- Optional start / end zone meshes (if `save_zones yes`).

```bash
pymol out/pymol/1AKD_results.pse
```

To render a figure:

```bash
pymol -cq -d "
  load out/pymol/1AKD_results.pse;
  set ray_opaque_background, on;
  bg_color white;
  ray 1600 1200;
  png tunnels.png, dpi=300
"
```

The session has named selections for each cluster:
`cluster_1`, `cluster_2`, … so you can hide/show specific tunnels:

```pymol
hide everything, cluster_3 cluster_4 cluster_5
ray 1600 1200; png main_tunnel.png
```

For an MD ensemble, the `.pse` shows the first snapshot only — use
VMD for trajectories.

## VMD scripts (`vmd.sh`, `vmd_timeless.sh`)

CAVER writes shell launchers + `.tcl` drivers into the output
directory. Two flavors:

| Script | Purpose |
|--------|---------|
| `vmd.sh` / `vmd.bat` / `view.tcl` | **Time-resolved** — opens all snapshots as a trajectory + their tunnels |
| `vmd_timeless.sh` / `vmd_timeless.bat` / `view_timeless.tcl` | **Time-collapsed** — opens the first snapshot + the union of all tunnels |

The `.sh` launcher reads `$linux_vmd` (or `path_to_vmd` from the
config). To run on Linux:

```bash
export linux_vmd=/usr/local/bin/vmd            # adjust to your VMD path
cd out
bash vmd.sh                                     # time-resolved
# or
bash vmd_timeless.sh
```

Or set it in the original `config.txt` **before** running CAVER:

```ini
path_to_vmd /usr/local/bin/vmd
```

…and CAVER will bake the right path into the generated scripts.

### Inside the .tcl drivers

`view.tcl` / `view_timeless.tcl` load:

- The input PDB(s).
- The CAVER mesh PDBs from `data/tunnels/<cluster>/`.
- The per-frame trajectory linking (time-resolved only).
- A custom palette (`bottleneck_pallette.png`, `pallette.png` in
  `bin/`).

Open the scripts to tweak colors, atom selections, or the camera.
They're standard VMD Tcl.

### `view_plugin.py` — for the PyMOL plugin

The bundled `view_plugin.py` is the entry point for the
[CAVER PyMOL plugin](http://www.caver.cz/index.php?sid=156). If you
install the plugin in PyMOL, CAVER's output directory can be opened
directly via the plugin GUI. Not needed for the headless / scripted
flow.

## Per-cluster mesh PDBs

Under `out/data/tunnels/tunnel_<id>/` there's one PDB per tunnel in
the cluster (sub-sampled by `visualize_tunnels_per_cluster` /
`visualization_subsampling`):

```
out/data/tunnels/tunnel_1/
├── 0_1.pdb
├── 0_2.pdb
└── ...
```

Each is a sequence of HETATM pseudo-atoms tracing the tunnel surface
(spheres of the local tunnel radius). Load any viewer:

```bash
pymol -d "
  load 1AKD.pdb, protein;
  cmd.load_traj('out/data/tunnels/tunnel_1/0_1.pdb', 'tunnel_1');
  show spheres, tunnel_1; color cyan, tunnel_1;
  show cartoon, protein
"
```

Or in ChimeraX:

```
open 1AKD.pdb
open out/data/tunnels/tunnel_1/0_1.pdb
preset 'sphere/sphere'
```

## Headless rendering on a cluster

CAVER is CPU-only and the SIF doesn't include PyMOL, so the workflow
is:

1. Run CAVER on the cluster → get `out/`.
2. `scp out/pymol/` and `out/data/tunnels/` to your workstation.
3. Render figures locally.

If you must render on the cluster (e.g. for an automated report),
install PyMOL-Open-Source via conda on the same node:

```bash
conda create -n pymol -c conda-forge pymol-open-source -y
conda run -n pymol pymol -cq -d "load out/pymol/X_results.pse; ray 1600 1200; png x.png"
```

PyMOL needs an OpenGL-capable EGL or off-screen renderer; `pymol -cq`
uses the software rasterizer.

## Custom palettes

The default palette is in `bin/pallette.png`; the bottleneck-specific
palette in `bin/bottleneck_pallette.png`. To change the colors used in
visualizations:

```bash
# Bind-mount your palettes over the SIF's:
apptainer run \
    --bind ./my_pallette.png:/opt/caver/bin/pallette.png \
    "$SINGULARITY_HOME"/CAVER.sif ...
```

The PNGs are read pixel-by-pixel as a gradient — make them tall and
1-pixel-wide.

## Recipe — annotated figure with PyMOL

Make a publication-quality figure of the top 3 tunnels:

```python
# render_top3.py
import pymol
from pymol import cmd
pymol.finish_launching(['pymol', '-cq'])

cmd.load("out/pymol/1AKD_results.pse")
cmd.bg_color("white")
cmd.show("cartoon", "polymer")
cmd.color("gray80", "polymer")
cmd.set("ray_opaque_background", "on")

# Hide everything past cluster 3:
for i in range(4, 20):
    cmd.disable(f"cluster_{i}")

cmd.color("salmon",  "cluster_1")
cmd.color("skyblue", "cluster_2")
cmd.color("limon",   "cluster_3")

cmd.orient()
cmd.ray(2000, 1500)
cmd.png("top3.png", dpi=300)
```

```bash
conda run -n pymol pymol -cq render_top3.py
```

## Recipe — quick QC plot of the starting points

After running CAVER, check the optimized origins landed in the active
site:

```bash
pymol -cq -d "
  load proj/pdb/1.pdb, protein;
  load proj/out/data/origins.pdb, origins;
  hide everything; show cartoon, protein;
  show spheres, origins; color red, origins;
  zoom origins, 10;
  ray 1200 900; png origins_qc.png
"
```

If the red spheres are scattered or far from your expected cavity,
your starting hint was bad — fix it before trusting the tunnels.

## Recipe — animate tunnels over an MD trajectory

VMD time-resolved:

```bash
export linux_vmd=/path/to/vmd
cd out
bash vmd.sh
# Inside VMD:
# - Frames are the snapshots; tunnels recolor per-frame
# - File → Render → Tachyon  (or  movie maker plugin)
```

For a PyMOL-only path (no VMD), you can stitch the per-frame mesh PDBs
manually:

```python
import os, pymol
from pymol import cmd
pymol.finish_launching(['pymol', '-cq'])

frames = sorted(os.listdir("md_snapshots"))
for i, frame in enumerate(frames):
    cmd.delete("all")
    cmd.load(f"md_snapshots/{frame}", "protein")
    for cluster_dir in sorted(os.listdir("out/data/tunnels")):
        cmd.load(f"out/data/tunnels/{cluster_dir}/0_{i+1}.pdb", cluster_dir)
    cmd.bg_color("white"); cmd.orient()
    cmd.ray(800, 600); cmd.png(f"frame_{i:03d}.png", dpi=150)

# Then stitch with ffmpeg:
# ffmpeg -framerate 10 -i frame_%03d.png -c:v libx264 -pix_fmt yuv420p tunnels.mp4
```

## Reading meshes programmatically

Each mesh PDB is just a sequence of HETATM lines with B-factor =
local tunnel radius. Load with `biotite`:

```python
import biotite.structure.io.pdb as pdb
struct = pdb.PDBFile.read("out/data/tunnels/tunnel_1/0_1.pdb").get_structure(model=1)
radii = struct.b_factor       # per-pseudo-atom tunnel radius (Å)
xyz   = struct.coord          # (N, 3)
```

Useful for custom analyses (e.g. checking that the tunnel passes
through a specific residue's vicinity).
