# Installation

BindCraft installs into a **conda env**, not a container. There is no
Apptainer / Docker path upstream — the heavy work (PyRosetta + JAX/CUDA
matching) is done by the install script.

## One-line install

```bash
git clone https://github.com/martinpacesa/BindCraft  /path/to/bindcraft
cd /path/to/bindcraft
bash install_bindcraft.sh --cuda '12.4' --pkg_manager 'conda'
```

`--cuda` should match the CUDA your driver supports (`nvidia-smi` →
"CUDA Version: 12.x"). If you leave it blank the script picks a default
that may not match — get explicit. `--pkg_manager` accepts `conda` or
`mamba` (mamba is faster).

## What the install script does

1. **Creates a `BindCraft` conda env** with Python 3.10.
2. **Installs JAX + JAXLib** pinned `jax>=0.4,<=0.6.0` (with CUDA matching
   the `--cuda` flag) — plus `chex`, `dm-haiku`, `flax<0.10.0`, `dm-tree`,
   `joblib`, `ml-collections`, `immutabledict`, `optax`.
3. Installs the numerics / I/O stack: `numpy<2.0.0` (important — Numpy 2
   breaks ColabDesign), `pandas`, `matplotlib`, `seaborn`, `scipy`,
   `biopython`, `pdbfixer`, `tqdm`, `jupyter`, `ffmpeg`, `fsspec`,
   `py3dmol`, `libgfortran5`.
4. **Installs ColabDesign from GitHub** (`pip install
   git+https://github.com/sokrypton/ColabDesign.git --no-deps`).
5. **Installs PyRosetta** from the official wheel index
   (`https://west.rosettacommons.org/pyrosetta/quarterly/release.cxx11thread.serialization`).
6. **Downloads AF2 weights** to
   `<install_dir>/params/alphafold_params_2022-12-06.tar`, extracts them,
   and deletes the tar. This is the dependency that takes the longest
   (~5.3 GB download).
7. **chmod +x** the bundled `functions/dssp` and `functions/DAlphaBall.gcc`
   helpers (DSSP for secondary structure, DAlphaBall for surface analysis
   inside PyRosetta).
8. Cleans the conda package cache to reclaim space.

## After install — sanity-check

```bash
conda activate BindCraft
python - <<'PY'
import os, jax, colabdesign, pyrosetta, Bio
print("jax devices:", jax.devices())
print("colabdesign:", colabdesign.__file__)
print("pyrosetta:", pyrosetta.__file__)
PY
```

You should see `[CudaDevice(id=0)]` (or similar). CPU-only is *not*
supported for the AF2 step — every trajectory will hang.

## Hardware requirements

| Resource | Requirement |
|----------|-------------|
| GPU | **CUDA-capable Nvidia**, fp16-friendly |
| GPU memory | **≥ 32 GB recommended** for typical targets; smaller targets (≤ 200 aa) can sometimes run on 24 GB; 16 GB will OOM on most real targets |
| CPU | 1 core is enough — the script is GPU-bound |
| RAM | The shipped SLURM script asks for **42 GB** — 32 GB is usually fine |
| Disk | ~2 MB code + ~5.3 GB AF2 weights + design output (often 10s–100s of GB depending on `number_of_final_designs` and whether you keep unrelaxed PDBs / pickles / animations) |
| Walltime | The shipped SLURM script asks for **72 h**; difficult targets need every minute of it |

> **Smaller target = smaller GPU footprint and faster trajectories.** The
> single biggest lever for memory and speed is the size of
> `starting_pdb`. Trim aggressively before designing.

## Disk savings

Once a run is going, the output directory grows fast. To stay lean, leave
these on (they are the defaults in every shipped preset):

```json
{
  "remove_unrelaxed_trajectory": true,   // delete unrelaxed Trajectory PDBs after relax
  "remove_unrelaxed_complex":    true,   // delete unrelaxed MPNN complex PDBs
  "remove_binder_monomer":       true,   // delete binder-only repredictions after scoring
  "zip_animations":              true,   // gzip the Trajectory/Animation folder at end of run
  "zip_plots":                   true,   // gzip the Trajectory/Plots folder at end of run
  "save_trajectory_pickle":      false,  // do NOT save raw ColabDesign pickles (huge)
  "save_mpnn_fasta":             false   // sequences are already in the CSV
}
```

Only flip `save_trajectory_pickle: true` if you need to inspect the
hallucination internals later — each pickle is hundreds of MB.

## License notes

- **BindCraft itself**: MIT (Martin Pacesa).
- **AF2 weights**: DeepMind's [original AlphaFold parameters license](https://github.com/google-deepmind/alphafold) — research / non-commercial use unless DeepMind licenses commercial use.
- **PyRosetta**: gratis for academic use; **a commercial PyRosetta license is required for commercial use** of any BindCraft run.
- **ColabDesign**: MIT (Sergey Ovchinnikov).
- **ProteinMPNN weights**: MIT (Justas Dauparas).

If you cannot accept PyRosetta's terms, the only realistic alternative
binder designer in this collection is **BoltzGen** (MIT code + weights,
fully permissive).

## Troubleshooting install

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `jax devices: [CpuDevice]` | CUDA mismatch | Re-run install with the correct `--cuda` matching `nvidia-smi`. |
| `ImportError: numpy.core.multiarray failed to import` | numpy ≥ 2 in env | The install pins `numpy<2`; if you upgraded later, `pip install 'numpy<2'`. |
| `ModuleNotFoundError: colabdesign` | pip step failed silently | Re-run the ColabDesign line manually: `pip install git+https://github.com/sokrypton/ColabDesign.git --no-deps`. |
| `pyrosetta: ImportError: libRosetta_*` | architecture mismatch (e.g. ARM) | PyRosetta is x86_64-only; BindCraft will not run on Apple Silicon / ARM. |
| `params_model_5_ptm.npz` missing | AF2 weights download failed mid-stream | Delete `params/` and re-run only the wget + tar lines from `install_bindcraft.sh`. |

The official wiki at
<https://github.com/martinpacesa/BindCraft/wiki/De-novo-binder-design-with-BindCraft>
is the canonical reference and is regularly updated — read it before
posting issues.
