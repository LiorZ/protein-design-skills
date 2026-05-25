# Troubleshooting

## Build-time (apptainer build)

| Symptom | Cause / fix |
|---------|-------------|
| `FATAL: could not use fakeroot` / permission errors during build | Your user lacks fakeroot mappings. Use `sudo apptainer build ...`, or build on a machine where you have root/fakeroot and copy the `.sif` over. |
| Build hangs or fails on `git clone` / pip `se3-transformer` | The build needs network. Behind a proxy, pass it through: `APPTAINERENV_HTTPS_PROXY=... apptainer build ...`, or build somewhere with open egress. |
| conda/mamba solve fails or is extremely slow with `placer_env_lite.yml` | Rebuild with the fully-pinned env: `--build-arg ENV_FILE=envs/placer_env.yml`. |
| `mamba env create` fails resolving CUDA/dgl channels | The env pins `dglteam/label/th23_cu121` and `nvidia/label/cuda-12.1.0`. A transient channel/mirror issue — retry; or use the pinned `placer_env.yml`. |
| Out of disk during build | The image is ~8-12 GB and the build cache more. Set `APPTAINER_TMPDIR`/`APPTAINER_CACHEDIR` to a roomy filesystem. |

## Runtime — GPU / environment

| Symptom | Cause / fix |
|---------|-------------|
| Predictions are extremely slow (minutes each) | You forgot `--nv`, so PLACER is on CPU. Add `--nv`. |
| `CUDA error: ... no kernel image` / driver-too-old | Host NVIDIA driver doesn't support CUDA 12.1. Update the host driver (≥ 530), or run CPU-only (omit `--nv`). |
| `torch.cuda.is_available()` is False even with `--nv` | No GPU visible (check `nvidia-smi` on host), or `CUDA_VISIBLE_DEVICES` excludes all GPUs. Pass `APPTAINERENV_CUDA_VISIBLE_DEVICES=0`. |
| `FileNotFoundError: weights/PLACER_model_1.pt` | The default `--weights` is CWD-relative. Pass `--weights /opt/PLACER/weights/PLACER_model_1.pt` (`$PLACER_WEIGHTS`) or add `--pwd /opt/PLACER`. |
| Can't read input / can't write output | The path is outside `$PWD`/`$HOME` (the only auto-mounts). Add `--bind /your/path:/your/path`. |
| `torch.cuda.OutOfMemoryError` | Crop is too large (PLACER is OOD above ~600 atoms). Tighten the pocket via `--target_res`/`--crop_centers`, or use a bigger GPU. |

## Runtime — inputs / chemistry

| Symptom | Cause / fix |
|---------|-------------|
| `AssertionError` about ligand chain on a `.pdb` input | The ligand shares the protein's chain letter. Move the ligand to its own chain, or convert to RCSB-style mmCIF (which parses ligand chains differently). See `inputs.md`. |
| mmCIF parse error / garbage atoms | The mmCIF isn't RCSB-formatted (e.g. it came from AF/Boltz/Chai). Convert to PDB or use a true RCSB mmCIF. |
| Aromatic rings come out non-planar | PLACER guessed wrong hybridization/bonds from coordinates. Supply `--ligand_file LIG:lig.sdf` (or `LIG:CCD`) with correct chemistry. Occasionally the model just distorts a molecule — its confidence scores are usually worse in that case too. |
| Hydrogen / protonation mismatch errors between PDB and SDF/MOL2 | Add `--ignore_ligand_hydrogens` (H is not predicted anyway). |
| "no ligand found" / crop center error on an apo structure | Apo inputs have nothing to center on — pass `--target_res <chain-resno>` (and usually `--no-use_sm`). |
| A random, meaningless ligand gets predicted | With ligands present but no `--predict_ligand`, PLACER picks one at random per sample. Specify `--predict_ligand <sel>` (and `--fixed_ligand`/`--predict_multi` as needed). |
| `--mutate` to a non-canonical errors with "unknown residue" | Register it with `--residue_json file.json` (schema in `inputs.md`). |
| Crystallographic solvent (HOH/SO4/…) interferes | `--exclude_common_ligands`, or API `skip_ligands([...])`. |

## Results quality

| Symptom | Fix |
|---------|-----|
| All `prmsd` scores are high (> 4) | Hard target. Increase `-n` to >200; supply correct ligand chemistry via `--ligand_file`; verify the starting pose is plausible (PLACER refines, it doesn't dock from scratch). |
| Poses look reasonable but you're unsure which to trust | Rank by `prmsd`, keep the top ~10%, and cross-check `plddt`/`plddt_pde > 0.8`. Don't rank by `rmsd`/`lddt`/`fape` for blind predictions — those compare to the input, not ground truth. |
| Want per-residue confidence | Read the b-factor column of `*_model.pdb` (per-atom `prmsd`). |

## Sanity checks

```bash
# Image built and env imports cleanly:
apptainer exec placer.sif python /opt/PLACER/run_PLACER.py --help

# GPU visible inside the container:
apptainer exec --nv placer.sif python -c \
  "import torch; print('cuda', torch.cuda.is_available(), torch.version.cuda)"

# End-to-end on a bundled example:
apptainer exec --nv placer.sif python /opt/PLACER/run_PLACER.py \
  --ifile /opt/PLACER/examples/inputs/4dtz.cif --odir out -n 5 --rerank prmsd \
  --predict_ligand D-LDP-501 --weights /opt/PLACER/weights/PLACER_model_1.pt
```
