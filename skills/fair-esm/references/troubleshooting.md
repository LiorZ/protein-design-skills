# Troubleshooting

A taxonomy of the failure modes that hit you in practice with
`fair-esm`, ordered from most common to least.

## Install / import failures

### `ModuleNotFoundError: No module named 'openfold'`

ESMFold needs OpenFold. Install it with the `[esmfold]` extra **plus**
the two git deps:

```bash
pip install "fair-esm[esmfold]"
pip install 'dllogger @ git+https://github.com/NVIDIA/dllogger.git'
pip install 'openfold @ git+https://github.com/aqlaboratory/openfold.git@4b41059694619831a7db195b7e0988fc4ff3a307'
```

### `nvcc fatal: Unsupported gpu architecture` / `nvcc: command not found`

OpenFold compiles CUDA kernels at install time. You need:

- `nvcc` on PATH (`which nvcc; nvcc --version`).
- CUDA toolkit version matching `torch.version.cuda`.

If you can't install CUDA toolkit, use Hugging Face's `transformers`
port (`EsmForProteinFolding`) which has no CUDA-kernel dependency.

### `ImportError: torch_scatter` from `import esm.inverse_folding`

Recent commits (`636becf`) make `import esm.inverse_folding` succeed
even without `torch_scatter` — but calling `model.sample(...)` will
still fail. Install `torch_scatter` matched to your PyTorch + CUDA:

```bash
TORCH=$(python -c "import torch; print(torch.__version__.split('+')[0])")
CUDA=$(python -c "import torch; print('cu'+torch.version.cuda.replace('.',''))")
pip install torch-scatter -f https://data.pyg.org/whl/torch-${TORCH}+${CUDA}.html
```

Or use the official conda recipe for ESM-IF1 — see `installation.md`.

### `RuntimeError: CUDA error: no kernel image is available for execution on the device`

PyTorch and your GPU's compute capability are mismatched. Common when
running newer GPUs (sm_90 / H100) on older PyTorch wheels. Upgrade
PyTorch and reinstall pyg.

## Model-loading failures

### `Exception: Could not load https://dl.fbaipublicfiles.com/.../X.pt`

Two causes:

1. **Wrong model name** — check `references/models.md` for the
   canonical list.
2. **Network firewall** — the model files live on `fbaipublicfiles.com`.
   On a closed network, mirror to `~/.cache/torch/hub/checkpoints/`
   manually:
   ```bash
   wget https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t33_650M_UR50D.pt \
        -P ~/.cache/torch/hub/checkpoints/
   wget https://dl.fbaipublicfiles.com/fair-esm/regression/esm2_t33_650M_UR50D-contact-regression.pt \
        -P ~/.cache/torch/hub/checkpoints/
   ```

### `FileNotFoundError: ...-contact-regression.pt`

For local `.pt` loading, the regression file must sit next to the main
checkpoint with the matching `*-contact-regression.pt` name.

ESM-1v and ESM-IF1 don't ship regression weights — skip
`--include contacts` for those.

## Runtime issues

### `RuntimeError: CUDA out of memory`

Knobs, in order of preference:

1. **Lower batch size** — `--toks_per_batch 1024` for ESM-2, or
   `--max-tokens-per-batch 512` for ESMFold.
2. **Lower chunk size** — ESMFold: `model.set_chunk_size(64)`, then 32,
   then 16.
3. **Truncate** — `--truncation_seq_length 800` if shorter is fine.
4. **CPU offload** — `--cpu-offload` (FSDP) for ESMFold; bigger
   ceiling at the cost of slower wall time.
5. **Smaller model** — drop from 650 M → 150 M → 35 M.

### Outputs differ between runs with the same seed

ESM-IF1 and ESMFold use stochastic ops (dropout if `eval()` is missed;
some non-deterministic CUDA kernels). Fix:

- Call `model.eval()`.
- `torch.manual_seed(...)` *and* `torch.use_deterministic_algorithms(True)`.
- For ESMFold, optionally pass an explicit `masking_pattern` to
  `infer(...)`.

### Sampled ESM-IF1 sequences contain `EEEEEEEE` / `KKKKKK` etc.

Known failure mode flagged in the official README. Filter them out:

```python
import re
def has_long_repeat(seq, n=5):
    return bool(re.search(r"(.)\1{%d,}" % (n - 1), seq))
designs = [s for s in designs if not has_long_repeat(s)]
```

Try lower temperature, or switch to ProteinMPNN for that target.

### ESMFold mean pLDDT is 30-40 across the board

- Sequence may be longer than training distribution (~1024). Try
  splitting.
- For multimers, ESMFold uses a 25-G linker by default; check that
  `chain_linker` makes sense for your case.
- Some sequences (disordered regions, weird repeats) genuinely fold
  poorly. Switch to AF2 / Boltz / Chai for hard targets.

### `predict.py` AssertionError: "listed wildtype does not match"

The mutation string says e.g. `A24P` but `sequence[24 - offset_idx]` is
not `A`. Most likely:

- `--offset-idx` is wrong (the integer that maps mutation position to
  sequence index).
- Sequence and DMS CSV are out of register (different isoforms, signal
  peptide stripped vs not, etc).

### `MSATransformer` with `esm-extract` raises ValueError

The script doesn't handle MSA inputs. Use the Python API directly — see
`msa-transformer.md`.

## ESM-IF1-specific

### `RuntimeError: structure has multiple atoms with same name`

The PDB has altlocs or multiple models. Pre-process with PyMOL / biotite
to keep only altloc A and model 1:

```python
from biotite.structure.io.pdb import PDBFile
import biotite.structure as struc
pdb = PDBFile.read("target.pdb")
arr = pdb.get_structure(model=1, altloc="first")
PDBFile().set_structure(arr); PDBFile().write("clean.pdb")
```

### `ValueError: No chains found in the input file`

Either the file has only HETATM records (no protein) or it's broken.
Sanity check with `biotite.structure.get_chains(struct)`.

### `ValueError: Chain X not found in input file`

The chain id is case-sensitive. PDB chain ids are typically uppercase
letters; mmCIF can be longer strings.

## ESMFold-specific

### `_pickle.PicklingError` when running `--cpu-offload`

The FSDP CPU-offload path uses `torch.distributed` and initializes a
process group. Don't combine `--cpu-offload` with `torch.multiprocessing`
or other DDP wrappers — they conflict.

### `Tried to instantiate dummy base class Device` (PyTorch deprecation)

ESMFold internals rely on some older PyTorch APIs. Pin PyTorch to a
version known to work (the `environment.yml` ships PyTorch 1.13.1).

## Atlas API

### HTTP 413 from `api.esmatlas.com/foldSequence/v1/pdb/`

Sequence is too long (~400 residues is the cap). Fold locally.

### HTTP 429

Per-IP rate limiting. Back off / spread across multiple IPs / fold
locally.

## When to give up on `fair-esm`

If you've been fighting OpenFold install for more than ~30 minutes,
switch to the Hugging Face `transformers` ESMFold (`EsmForProteinFolding`)
or use ColabFold's ESMFold image. Same model, no `nvcc` requirement.

If you need ESM-3 or ESM-C, this package doesn't have them — install
[`evolutionaryscale/esm`](https://github.com/evolutionaryscale/esm).
