# PLACER examples

Everything here assumes you run PLACER from the Apptainer/Singularity SIF
described in [`PLACER.def`](PLACER.def). The container bundles the PLACER source,
the model weights, and the full conda runtime, so you never touch a host conda
env.

## Files

| File | What it is |
|------|------------|
| `PLACER.def` | Apptainer/Singularity definition. Build once into `placer.sif`. |
| `commandline_examples.sh` | Copy-paste `apptainer exec` invocations covering the main use cases (docking, multi-ligand, sidechains, apo, mutation/non-canonical). |

## 1) Build the image (one-time)

```bash
apptainer build --fakeroot placer.sif PLACER.def
# no --fakeroot privileges?  ->  sudo apptainer build placer.sif PLACER.def
```

Build needs network (git clone + conda solve + the SE3Transformer pip install)
and pulls several GB. Expect 20-40 min. The `%test` section runs
`run_PLACER.py --help` at the end to confirm the env imports cleanly.

## 2) Run the bundled examples

```bash
bash commandline_examples.sh
```

These use the inputs shipped *inside* the image
(`/opt/PLACER/examples/inputs`), so they work without any host data. Results
land in `./out` on the host (apptainer auto-mounts `$PWD`).

## 3) Run on your own structure

```bash
SIF=./placer.sif
W=/opt/PLACER/weights/PLACER_model_1.pt

apptainer exec --nv "$SIF" \
  python /opt/PLACER/run_PLACER.py \
    --ifile my_complex.pdb \      # ligand must already be in this file
    --odir out \
    -n 100 \
    --rerank prmsd \
    --predict_ligand A-LIG-1 \    # <chain>-<name3>-<resno>
    --weights "$W"
```

Then inspect `out/my_complex_*.csv` (sorted best→worst by `prmsd`) and
`out/my_complex_*_model.pdb` (multimodel; per-atom `prmsd` in the b-factor
column). For docking, keep the top ~10% by `prmsd`.

## Key reminders

- **The ligand must already exist (with coordinates) in the input.** PLACER
  cannot dock from a bare SMILES/SDF against an apo protein.
- **Always pass `--weights /opt/PLACER/weights/PLACER_model_1.pt`** (or
  `--pwd /opt/PLACER`) — the default weights path is resolved relative to the
  working directory.
- **`--nv` is required for GPU.** Without it, PLACER runs on CPU (minutes/model).
- **Apo runs need `--target_res`** as a crop center (usually with `--no-use_sm`).
- **Bind extra paths** with `--bind SRC:DST` for inputs/outputs outside
  `$PWD`/`$HOME`.

See the parent skill's `references/` for the full CLI, input conventions,
Python API, and output/score definitions.
