# Driving Boltz from Python

Boltz does not expose a stable `run_inference(...)` Python entry point comparable to Chai-1's. The intended programmatic interface is **the CLI invoked via `subprocess`**, with output files parsed afterward. This page documents that pattern plus the lower-level building blocks that exist inside `boltz.main` for advanced users.

## Recommended: drive via subprocess

```python
import json
import subprocess
from pathlib import Path

def boltz_predict(yaml_path, out_dir, *, use_msa_server=True, diffusion_samples=1,
                  recycling_steps=3, seed=None, model="boltz2", extra_args=()):
    cmd = ["boltz", "predict", str(yaml_path),
           "--out_dir", str(out_dir),
           "--diffusion_samples", str(diffusion_samples),
           "--recycling_steps", str(recycling_steps),
           "--model", model]
    if use_msa_server:
        cmd.append("--use_msa_server")
    if seed is not None:
        cmd.extend(["--seed", str(seed)])
    cmd.extend(extra_args)
    subprocess.run(cmd, check=True)

    stem = Path(yaml_path).stem
    pred_dir = Path(out_dir) / f"boltz_results_{stem}" / "predictions" / stem
    best_cif = pred_dir / f"{stem}_model_0.cif"
    confidence = json.loads(
        (pred_dir / f"confidence_{stem}_model_0.json").read_text()
    )
    affinity = None
    aff_files = list(pred_dir.glob(f"affinity_{stem}.json"))
    if aff_files:
        affinity = json.loads(aff_files[0].read_text())
    return {"cif": best_cif, "confidence": confidence, "affinity": affinity}
```

Why this is the recommended path:

- The CLI is the **only** stable API surface that the maintainers test on every release.
- Internal class APIs (`Boltz1`, `Boltz2`, `BoltzWriter`, `process_inputs`, ...) move between minor versions.
- Output files are documented and stable.

## Low-level building blocks

If you must avoid `subprocess`, the bits inside `boltz.main` are roughly:

```python
from pathlib import Path
import torch
from pytorch_lightning import Trainer

from boltz.main import (
    download_boltz1, download_boltz2,
    BoltzProcessedInput, BoltzDiffusionParams, Boltz2DiffusionParams,
    PairformerArgs, PairformerArgsV2,
    check_inputs, process_inputs,
)
from boltz.data.module.inference import BoltzInferenceDataModule
from boltz.data.types import Manifest
from boltz.model.models.boltz2 import Boltz2
```

Sketch of the flow (read `boltz.main.predict` for the authoritative version):

```python
cache = Path("~/.boltz").expanduser()
download_boltz2(cache)

data = check_inputs("input.yaml")          # validates path / format
out_dir = Path("./results")
out_dir.mkdir(exist_ok=True, parents=True)

process_inputs(
    data=data, out_dir=out_dir,
    ccd_path=cache / "ccd.pkl",
    mol_dir=cache / "mols",
    use_msa_server=True,
    msa_server_url="https://api.colabfold.com",
    msa_pairing_strategy="greedy",
    msa_server_username=None,
    msa_server_password=None,
    api_key_header=None,
    api_key_value=None,
    boltz2=True,
    preprocessing_threads=4,
    max_msa_seqs=8192,
)

manifest = Manifest.load(out_dir / "processed" / "manifest.json")
processed = BoltzProcessedInput(
    manifest=manifest,
    targets_dir=out_dir / "processed" / "structures",
    msa_dir=out_dir / "processed" / "msa",
)

# Load model
ckpt = cache / "boltz2_conf.ckpt"
model = Boltz2.load_from_checkpoint(
    str(ckpt),
    strict=False,
    diffusion_process_args=Boltz2DiffusionParams().__dict__,
    pairformer_args=PairformerArgsV2().__dict__,
    # ... and many more args; see boltz.main.predict for the full list
)

datamodule = BoltzInferenceDataModule(
    manifest=manifest,
    target_dir=processed.targets_dir,
    msa_dir=processed.msa_dir,
    num_workers=2,
)

trainer = Trainer(accelerator="gpu", devices=1, strategy="auto", logger=False)
trainer.predict(model, datamodule=datamodule)
```

This shape **will change** between releases. Pin your `boltz` version (`pip install boltz==2.2.1`) if you rely on the internal APIs.

## Output reading helpers

```python
import json
import numpy as np
from pathlib import Path

def load_confidence(pred_dir: Path, stem: str, sample: int = 0):
    return json.loads(
        (pred_dir / f"confidence_{stem}_model_{sample}.json").read_text()
    )

def load_plddt(pred_dir: Path, stem: str, sample: int = 0):
    return np.load(pred_dir / f"plddt_{stem}_model_{sample}.npz")["plddt"]

def load_pae(pred_dir: Path, stem: str, sample: int = 0):
    return np.load(pred_dir / f"pae_{stem}_model_{sample}.npz")["pae"]

def load_affinity(pred_dir: Path, stem: str):
    aff = pred_dir / f"affinity_{stem}.json"
    return json.loads(aff.read_text()) if aff.exists() else None
```

## Building YAMLs programmatically

YAML is just plain Python dicts dumped with `yaml.safe_dump`:

```python
import yaml

def build_yaml(target_seq, target_msa, ligand_smiles, affinity=True):
    spec = {
        "version": 1,
        "sequences": [
            {"protein": {"id": "A", "sequence": target_seq, "msa": str(target_msa)}},
            {"ligand":  {"id": "L", "smiles": ligand_smiles}},
        ],
    }
    if affinity:
        spec["properties"] = [{"affinity": {"binder": "L"}}]
    return yaml.safe_dump(spec, sort_keys=False)
```

Write to disk, run `boltz_predict(...)`, parse the outputs. That is the recommended pipeline shape for any large-scale workflow.

## Subprocess gotchas

- `subprocess.run([..., "--use_msa_server"], check=True)` — `check=True` will raise `CalledProcessError` on any non-zero exit. Catch it if you want soft failure handling.
- `boltz predict` is verbose; suppress stdout/stderr with `stdout=subprocess.DEVNULL` only after you've debugged once — the logs are useful when MSA / kernel issues happen.
- DDP (`--devices > 1`) spawns child processes. If you wrap this with `multiprocessing` yourself, prefer `start_method="spawn"` to avoid forking CUDA contexts.
