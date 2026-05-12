# Installing `fair-esm`

`fair-esm` is published on PyPI and the source lives at
`https://github.com/facebookresearch/esm`. The package itself is a thin
PyTorch wrapper; the friction is almost always with the **optional**
extras (OpenFold for ESMFold; pytorch-geometric + `torch-scatter` for
ESM-IF1).

## Compatibility matrix

| Component       | Constraint                                  | Why |
|-----------------|----------------------------------------------|-----|
| Python          | 3.7 – 3.9 (3.10 *may* work for ESM-2 only)   | OpenFold requires ≤ 3.9 |
| PyTorch         | ≥ 1.12 (≥ 1.13 recommended)                  | torch.hub model loaders |
| CUDA            | 11.x or 12.x with matching `nvcc`            | OpenFold compiles CUDA kernels at install time |
| `nvcc`          | Required *only* for ESMFold install          | OpenFold extension |
| pytorch-geometric | torch / CUDA-matched wheel               | ESM-IF1 GVP layers |
| `torch-scatter` | torch / CUDA-matched wheel                   | ESM-IF1 sampling. Guarded — package imports without it but ESM-IF1 sampling will fail |
| OS              | Linux x86_64                                 | Windows untested; macOS works on CPU only |
| Disk            | ~5 GB for the 3 B and 15 B ESM-2 checkpoints | Cached under `~/.cache/torch/hub/checkpoints` |

The repo also ships an `environment.yml` that pins a known-good set of
versions (PyTorch 1.13.1 + CUDA 11.7 + OpenFold).

## Three install recipes

### Recipe A — ESM-2, ESM-1, ESM-1v, MSA-Transformer (no ESMFold, no ESM-IF1)

```bash
pip install -U fair-esm
```

That's it. You can `import esm; esm.pretrained.esm2_t33_650M_UR50D()` and
weights download to `~/.cache/torch/hub/checkpoints/`.

### Recipe B — ESMFold

```bash
pip install -U "fair-esm[esmfold]"
pip install 'dllogger @ git+https://github.com/NVIDIA/dllogger.git'
pip install 'openfold @ git+https://github.com/aqlaboratory/openfold.git@4b41059694619831a7db195b7e0988fc4ff3a307'
```

Caveats:

- Python ≤ 3.9. OpenFold fails on 3.10+ at the time of writing.
- `nvcc` must be on PATH and match the PyTorch CUDA version. `which nvcc`
  followed by `nvcc --version` should print a version matching
  `torch.version.cuda`.
- The OpenFold install compiles CUDA kernels — expect ~5 minutes the
  first time and a screenful of compiler warnings. If it fails, the most
  common cause is missing `nvcc` or a mismatched CUDA toolkit.

Alternative: use the conda `environment.yml` in the repo root:

```bash
git clone https://github.com/facebookresearch/esm.git
cd esm
conda env create -f environment.yml
conda activate esmfold
```

### Recipe C — ESM-IF1 (inverse folding)

The official recipe is conda-only because `pyg` wheels are CUDA-pinned:

```bash
conda create -n inverse python=3.9
conda activate inverse
conda install pytorch cudatoolkit=11.3 -c pytorch
conda install pyg -c pyg -c conda-forge
conda install pip
pip install biotite
pip install fair-esm
```

If you must do this with pip, you need to pick a `torch-scatter`,
`torch-sparse`, `torch-cluster`, `torch-spline-conv`, and `torch-geometric`
wheel **that matches both your PyTorch and CUDA version**. The Colab cell
in `examples/inverse_folding/notebook.ipynb` is the cleanest reference:

```python
import torch
TORCH = torch.__version__.split('+')[0]
CUDA  = 'cu' + torch.version.cuda.replace('.', '')
# then for each of torch-scatter / -sparse / -cluster / -spline-conv:
# pip install torch-scatter -f https://data.pyg.org/whl/torch-{TORCH}+{CUDA}.html
```

Recent fair-esm commits (`636becf` *guard torch_scatter dependency*) made
`import esm.inverse_folding` succeed even when `torch_scatter` is absent.
But sampling with `model.sample(coords, ...)` still raises at first call.
Install `torch_scatter` matched to your torch / CUDA before running design.

## All-in-one Docker (community)

There is no official ESM Docker image. Two common community options:

- [ColabFold's ESMFold image](https://github.com/sokrypton/ColabFold) — easy
  one-liner if you just need ESMFold predictions.
- HuggingFace `transformers` ESM port — `pip install transformers` then use
  `EsmForMaskedLM` / `EsmForProteinFolding`. This avoids OpenFold entirely.

## Weights cache

Pretrained checkpoints land in
`~/.cache/torch/hub/checkpoints/<model_name>.pt`.

For ESM-2 there is *also* a `<model_name>-contact-regression.pt` file
downloaded alongside it — required for unsupervised contact prediction.
ESM-1v, ESM-IF, and the partially-trained ESM-2 (`-270K` / `-500K`) do
**not** have regression weights and contacts won't work for them.

To pre-stage weights on a node without internet:

```bash
mkdir -p ~/.cache/torch/hub/checkpoints
cd ~/.cache/torch/hub/checkpoints
wget https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t33_650M_UR50D.pt
wget https://dl.fbaipublicfiles.com/fair-esm/regression/esm2_t33_650M_UR50D-contact-regression.pt
```

The full URL list is in `references/models.md`.

You can also redirect cache with `torch.hub.set_dir("/some/big/disk")`,
which `esm-fold` exposes as `-m / --model-dir`.

## Verifying the install

```python
import esm
print(esm.__version__)
m, a = esm.pretrained.esm2_t6_8M_UR50D()       # 8 M, ~30 MB
print(sum(p.numel() for p in m.parameters()))  # ~7.4 M
```

For ESMFold:

```python
import esm
m = esm.pretrained.esmfold_v1().eval().cuda()
print(m.infer_pdb("MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSL")[:500])
```

For ESM-IF1:

```python
import esm, torch
m, a = esm.pretrained.esm_if1_gvp4_t16_142M_UR50()
m.eval()
print(type(m).__name__)  # GVPTransformerModel
```

If any of these import-time checks fail, jump to `troubleshooting.md`.
