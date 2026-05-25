# Python API

PLACER is importable as a module (not pip-installable). Inside the SIF the
source is at `/opt/PLACER`, so add it to `sys.path` and import. Run any script
with `apptainer exec --nv placer.sif python my_script.py`.

```python
import sys
sys.path.append("/opt/PLACER")   # or os.environ["PLACER_DIR"]
import PLACER
```

## The three pieces

- `PLACER.PLACER(weights=None)` — the model. Loads the default checkpoint if
  `weights` is omitted (inside the SIF the default resolves correctly because
  the model code knows its own location; for `run_PLACER.py` the CLI default is
  CWD-relative — that caveat is CLI-only).
- `PLACER.PLACERinput()` — a builder describing one prediction job.
- `PLACER.protocol.dump_output(output_dict, filename, rerank=None)` — write the
  multimodel PDB + CSV (same files `run_PLACER.py` produces).

## Minimal example

```python
import sys; sys.path.append("/opt/PLACER")
import PLACER

placer = PLACER.PLACER()                         # load model

inp = PLACER.PLACERinput()
inp.cif("4dtz.cif")                              # RCSB mmCIF
inp.name("p450_dopamine")
inp.predict_ligand([("D", "LDP", 501)])          # fixes all other ligands
inp.ligand_reference({"HEM": "CCD", "LDP": "CCD"})

outputs = placer.run(inp, 50)                    # dict: {0: {...}, 1: {...}, ...}
PLACER.protocol.dump_output(outputs, "out/p450_dopamine", rerank="prmsd")
```

`placer.run(inp, N)` returns a dict of N models; each value holds the model PDB
string and the per-model scores. `dump_output` writes `out/p450_dopamine.csv`
and `out/p450_dopamine_model.pdb` (see `outputs.md`).

## `PLACERinput` setters

Each is a getter/setter — call with a value to set, with no argument to read.

| Method | Purpose / argument |
|--------|--------------------|
| `pdb(path_or_string)` | Set input from a PDB file path **or** a PDB string. |
| `cif(path)` | Set input from an RCSB mmCIF file. |
| `name(str)` | Job name → output filename prefix. |
| `predict_ligand([(chain, name3, resno), …])` | Ligand(s) to predict; auto-fixes the rest. |
| `predict_multi(bool)` | Predict & score all allowed ligands. |
| `fixed_ligand([...])` | Ligand(s) to keep fixed. |
| `fixed_ligand_noise(float)` | Noise on fixed-ligand coords (default = `sigma_bb`). |
| `skip_ligands([name3, …])` | Exclude ligands from parsing (e.g. `["HOH", "SO4"]`). |
| `ligand_reference({name3: "file.sdf" | "file.mol2" | "CCD"})` | Refine atom typing/bonding; `"CCD"` reads from the internal DB. |
| `ignore_ligand_hydrogens(bool)` | Ignore H mismatches between PDB and SDF/MOL2. |
| `bonds([...])` | Add explicit inter-atomic bond(s). |
| `mutate({"128A": "75I", …})` | Mutate positions before predicting. |
| `add_custom_residues(dict)` | Register non-canonical residues (same schema as `--residue_json`, see `inputs.md`). |
| `get_custom_residues()` | Read back the registered custom-residue dict. |
| `target_res(...)` | Crop center residue (required for apo inputs). |
| `crop_centers([...])` | Crop-center atom names **or XYZ coordinates** (coordinate input is API-only). |
| `corruption_centers([...])` | Corruption-center atom names **or XYZ coordinates** (API-only) for loose global sampling. |
| `exclude_sm(bool)` | Equivalent of `--no-use_sm` — predict without the small molecule. |
| `create_from_dict(dct)` | Build an input from a serialized dict. |
| `copy()` | Deep-copy the input (handy for sweeps). |

> Note the API accepts **XYZ coordinates** for `crop_centers`/`corruption_centers`,
> which the CLI does not expose — useful for programmatic pocket scanning.

## Notes from the upstream API examples

- Predicting heme in myoglobin from `3rgk.pdb` **fails** (ligand shares the
  protein chain → AssertionError); the same structure as `3rgk.cif` **works**.
  Use mmCIF, or put the ligand on its own chain. (See `inputs.md`.)
- For de novo proteins where heme atom names differ from the CCD default, pass a
  reference: `inp.ligand_reference({"HEM": "/opt/PLACER/examples/ligands/HEM.mol2"})`.
- Use `inp.skip_ligands(["HOH", "SO4"])` to drop crystallographic solvent before
  prediction (CLI analog: `--exclude_common_ligands`).

The upstream repo ships `examples/API_examples.py` and
`examples/API_examples_notebook.ipynb` (inside the SIF at
`/opt/PLACER/examples/`) covering native ligands, renamed-atom ligands, fixed
cofactors, mutations, and custom residues.
