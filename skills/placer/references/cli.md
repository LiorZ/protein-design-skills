# `run_PLACER.py` — full CLI reference

Entry point: `python /opt/PLACER/run_PLACER.py [options]` (inside the SIF).
All examples below omit the `apptainer exec --nv placer.sif` prefix and the
`--weights /opt/PLACER/weights/PLACER_model_1.pt` argument for brevity — both
are required in practice (see `installation.md`).

## Input selection (choose one)

| Flag | Meaning |
|------|---------|
| `-f, --ifile IFILE` | A single PDB/mmCIF, **or** a text file listing one path per line. Recognized extensions: `.pdb`, `.ent`, `.cif`, `.cif.gz`. mmCIF is parsed correctly only for **RCSB-formatted** files. |
| `-i, --idir IDIR` | A folder; every `*.pdb` in it is processed. |

## Output

| Flag | Meaning |
|------|---------|
| `-o, --odir ODIR` | Output folder. Default `./`. Created if missing. |
| `--ocsv OCSV` | Explicit CSV path. By default the CSV name is derived from the input stem + `--suffix`. |
| `--suffix SUFFIX` | String appended to output filenames (use it to distinguish runs on the same input). |
| `--cautious` | If the output CSV already exists, skip that prediction (resumable batches). |
| `--rerank {prmsd,plddt,plddt_pde}` | Sort the output models **and** CSV rows best→worst. `prmsd` ascending; `plddt`/`plddt_pde` descending. The model indices printed during the run no longer correspond to file order after reranking. |

## Sampling

| Flag | Meaning |
|------|---------|
| `-n, --nsamples N` | Number of stochastic samples (models) to generate. Default 10. **50** is enough for sidechains; **50-100** for docking; **>200** for hard ligands with few high-confidence hits. |

## Which atoms get predicted

| Flag | Meaning |
|------|---------|
| `--predict_ligand <sel> [<sel> …]` | Ligand(s) to predict. **Turning this on auto-fixes every other ligand** not listed. Selector: `<name3>`, `<name3-resno>`, or `<chain-name3-resno>`. |
| `--predict_multi` | Predict & score **all** allowed ligands in the input (still respects `--fixed_ligand`/`--predict_ligand`). |
| `--fixed_ligand <sel> [<sel> …]` | Keep these ligand(s) fixed (e.g. a heme cofactor while docking an inhibitor). |
| `--fixed_ligand_noise FLOAT` | Noise added to fixed-ligand coordinates. Default = the model's backbone `sigma_bb`. |
| `--use_sm` / `--no-use_sm` | Predict **with** the small molecule (holo; default on) or **without** it (apo — e.g. for pure sidechain prediction, or after `--mutate`). |
| `--target_res <chain-resno>` or `<chain-name3-resno>` | Protein residue used as the **crop center**. **Required when the input has no ligand** (apo sidechain prediction). |

## Cropping / sampling geometry

| Flag | Meaning |
|------|---------|
| `--crop_centers <atom> [<atom> …]` | Atom name(s) used as the **crop** center; one is picked at random per sample. Refines *where* the cropped sphere sits, but does **not** change which atoms/ligands are predicted (use `--predict_ligand` for that). Coordinate input is available in the Python API. Example: `B-200-HEM-FE B-200-HEM-O1`. |
| `--corruption_centers <atom> [<atom> …]` | Atom name(s) used as **corruption** centers — lets the ligand be sampled across the whole protein (loose global docking). One is picked at random per sample; provide **at least as many centers as there are ligands**. Coordinate input available in the API. |

## Ligand / residue chemistry

| Flag | Meaning |
|------|---------|
| `--ligand_file XXX:lig.sdf [YYY:lig2.mol2 …]` | Refine atom typing & connectivity from an SDF/MOL2 file. Format `<name3>:<file>`. The special form `<name3>:CCD` reads the ligand from PLACER's internal CCD database. **Coordinates are still taken from the PDB/mmCIF** — this only fixes hybridization/bonds (e.g. to keep aromatic rings planar). |
| `--ignore_ligand_hydrogens` | Ignore H atoms defined in the PDB and SDF/MOL2; don't error on mismatched protonation. Hydrogens are not predicted by PLACER anyway. |
| `--bonds A-42-ALA-CB:B-173-JRP-CL:<len> [...]` | Add explicit bond(s) between two atoms (space-separated list). |
| `--mutate 5A:TRP [6A:GLY …]` | Mutate position(s) before predicting. Format `<resno><chain>:<name3>`. |
| `--residue_json file.json` | Register non-canonical/custom residues (used in the PDB or via `--mutate`) into the internal CCD library. Schema in `inputs.md`. |
| `--exclude_common_ligands` | Drop common crystallographic solvents/additives (the AlphaFold3-supplement list) — useful when running directly on crystal structures. |

## Model

| Flag | Meaning |
|------|---------|
| `--weights WEIGHTS` | PyTorch `.pt` checkpoint. Default `weights/PLACER_model_1.pt` **resolved relative to CWD** — pass the absolute in-container path `/opt/PLACER/weights/PLACER_model_1.pt`. |
| `-h, --help` | Show help and exit. |

## Selector syntax cheat-sheet

A ligand or residue is named by 1-3 of: chain letter, 3-letter code, residue
number.

- `HEM` — by name3 only (all HEM residues).
- `LDP-501` — name3 + resno.
- `D-LDP-501` — chain + name3 + resno (most specific; use when chains repeat).
- `--mutate` uses `<resno><chain>:<name3>` (e.g. `128A:75I`).
- `--target_res` uses `<chain>-<resno>` (e.g. `A-149`) or `<chain>-<name3>-<resno>`.
- `--bonds`/`--crop_centers`/`--corruption_centers` use full atom selectors
  `<chain>-<resno>-<name3>-<atomname>` (e.g. `B-200-HEM-FE`).

## Worked examples

Dock an inhibitor, heme auto-fixed, 50 samples, ranked by prmsd:
```bash
run_PLACER.py --ifile 4dtz.cif --odir out -n 50 --rerank prmsd \
  --predict_ligand D-LDP-501 --suffix LDP
```

Dock two ligands at once:
```bash
run_PLACER.py --ifile 4dtz.cif --odir out -n 50 --rerank prmsd \
  --predict_ligand D-LDP-501 C-HEM-500 --predict_multi --suffix LDP-HEM
```

Sidechains in an apo de novo protein (crop center required):
```bash
run_PLACER.py --ifile dnHEM1_apo.pdb --odir out -n 50 --target_res A-149 --suffix A149
```

Refine ligand chemistry from MOL2 so the ring stays planar:
```bash
run_PLACER.py --ifile dnHEM1.pdb --odir out -n 50 --rerank prmsd \
  --ligand_file HEM:HEM.mol2
```

Mutate to a non-canonical, load it from JSON, drop the existing ligand:
```bash
run_PLACER.py --ifile denovo_SER_hydrolase.pdb --odir out -n 50 --suffix 75I \
  --mutate 128A:75I --residue_json 75I.json --no-use_sm
```
