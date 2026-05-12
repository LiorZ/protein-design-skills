# Installation

DISCO is a normal Python package managed with [`uv`](https://docs.astral.sh/uv/),
plus a Hydra entry-point script at `runner/inference.py`. There is no PyPI
release — you clone the repo and use `uv sync` to build a local
`.venv` that includes the `disco`, `runner`, `openfold`, and `LigandMPNN`
workspace members.

## Prerequisites

| Requirement | Recommended | Notes |
|-------------|-------------|-------|
| OS | Linux | Tested on Ubuntu 22.04 / 24.04 |
| Python | 3.11 — 3.12 | `requires-python = ">=3.11,<3.13"` in `pyproject.toml` |
| GPU | NVIDIA, **Ampere or newer** (A100 / L40S / H100 / H200 / B100 / B200) | Required for the DeepSpeed4Science EvoformerAttention kernels. Anything older needs `use_deepspeed_evo_attention=false`. |
| CUDA | 12.x | The default torch wheel works on most setups; override if you need a specific CUDA. |
| Disk | ~5 GB | Mostly the HuggingFace checkpoint and CUTLASS clone if used. |
| Network | Required on first launch | Pulls the `DISCO.pt` checkpoint from `DISCO-Design/DISCO`. |

## Step-by-step

### 1) Get `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

(or see <https://docs.astral.sh/uv/getting-started/installation/>.)

### 2) Clone DISCO and sync

```bash
git clone https://github.com/DISCO-design/DISCO.git ~/Repos/DISCO
cd ~/Repos/DISCO
uv sync
source .venv/bin/activate
```

`uv sync` resolves every dependency in `pyproject.toml`, builds the
workspace packages (`packages/openfold`, `packages/LigandMPNN`, `runner`),
and installs them all into `./.venv`. Subsequent `uv sync` calls are
idempotent.

### 3) (Optional) Switch torch to a specific CUDA backend

`uv sync` installs the default torch wheel. If you need an explicit CUDA
build (e.g. CUDA 12.4 because that's what your driver supports):

```bash
uv pip uninstall torch
uv pip install torch --torch-backend=cu124
```

Verify with:

```bash
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

### 4) AMD GPUs — the DeepSpeed caveat

DeepSpeed has no AMD support. You must:

1. **Edit `pyproject.toml`** and remove the `deepspeed>=0.18.3` line **before**
   running `uv sync` (otherwise `uv sync` will fail).
2. Pass `use_deepspeed_evo_attention=false` on every inference command:

   ```bash
   python runner/inference.py use_deepspeed_evo_attention=false ...
   ```

The naive attention fallback materializes the full attention matrix and
uses substantially more GPU memory — expect long sequences to OOM on
≤24 GB cards.

### 5) (Optional, NVIDIA Ampere+) Set up CUTLASS

DISCO's default uses [DeepSpeed4Science EvoformerAttention](https://www.deepspeed.ai/tutorials/ds4sci_evoformerattention/),
which compiles memory-efficient attention kernels using
[NVIDIA CUTLASS](https://github.com/NVIDIA/cutlass) on first call. The
kernels are not pre-built — you need a CUTLASS checkout on disk:

```bash
git clone https://github.com/NVIDIA/cutlass.git /path/to/cutlass
export CUTLASS_PATH=/path/to/cutlass
```

Add `export CUTLASS_PATH=...` to your shell profile (`~/.zshrc`, `~/.bashrc`)
so it persists across sessions.

The first inference run will spend a few minutes compiling the kernels.
Subsequent runs reuse the cache.

If `CUTLASS_PATH` is unset *and* `use_deepspeed_evo_attention=true`
(the default), DISCO will **assert at startup** with:

```
AssertionError: if use ds4sci, set env as https://www.deepspeed.ai/tutorials/ds4sci_evoformerattention/
```

Either set the env var, or pass `use_deepspeed_evo_attention=false`.

### 6) (Optional) Fast LayerNorm

To use the fast LayerNorm kernels (slight speedup, lazy compile):

```bash
export LAYERNORM_TYPE=fast_layernorm
```

If unset, DISCO uses the stock PyTorch LayerNorm.

## Model weights

The first invocation of `runner/inference.py` triggers an automatic
HuggingFace download from
[`DISCO-Design/DISCO`](https://huggingface.co/DISCO-Design/DISCO) of
`DISCO.pt` (~3 GB).

By default the file lands in your HuggingFace cache (`~/.cache/huggingface/hub`).
To use a custom path:

```bash
python runner/inference.py load_checkpoint_path=/path/to/DISCO.pt ...
```

If `load_checkpoint_path` is `null` *or* the path doesn't exist on disk,
the HuggingFace download is re-triggered. To use a custom-trained
checkpoint, set `load_checkpoint_path` and (optionally)
`load_strict=false` to skip shape-mismatched tensors.

## Verifying the install

```bash
cd ~/Repos/DISCO
source .venv/bin/activate

# Should print a config tree and start downloading the checkpoint.
python runner/inference.py \
  experiment=designable \
  effort=fast \
  input_json_path=input_jsons/unconditional_config.json \
  seeds=\[0\] \
  dump_dir=./test_output
```

A successful run produces:

```
test_output/
├── pdbs/
│   ├── length_70_sample_0.pdb
│   ├── length_100_sample_0.pdb
│   ├── length_200_sample_0.pdb
│   └── length_300_sample_0.pdb
└── sequences/
    ├── length_70_sample_0.txt
    ├── length_100_sample_0.txt
    ├── length_200_sample_0.txt
    └── length_300_sample_0.txt
```

## Common install failures

| Symptom | Fix |
|---------|-----|
| `uv sync` fails on `deepspeed` (AMD) | Remove `deepspeed>=0.18.3` from `pyproject.toml`, re-run `uv sync`. |
| `AssertionError: if use ds4sci, set env as ...` | Export `CUTLASS_PATH=...` **or** add `use_deepspeed_evo_attention=false` to the command. |
| `RuntimeError: CUDA error: no kernel image is available for execution on the device` | Your GPU is pre-Ampere. Use `use_deepspeed_evo_attention=false`. |
| `torch.cuda.OutOfMemoryError` on a 24 GB card with `use_deepspeed_evo_attention=false` | Either get an Ampere+ card and enable EvoformerAttention, or drop to shorter sequences (≤200 residues). |
| Network failure on HF download | Pre-download `DISCO.pt` manually and point at it with `load_checkpoint_path=`. |
| First step takes 10+ minutes with no logs | This is normal — CUTLASS kernels are compiling. The compile is cached. |
