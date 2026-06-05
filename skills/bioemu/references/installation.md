# Installation

BioEmu is a plain pip-installable Linux-only Python package. There is no
container, no SIF, no separate ColabDesign-style install script — pip
does everything.

## The three install flavours

```bash
# 1. Base — CPU JAX (slow MSA / embedding generation but everything works)
pip install bioemu

# 2. Recommended — CUDA-accelerated MSA via JAX
pip install bioemu[cuda]      # jax[cuda12]==0.4.35 + nvidia-cuda-nvcc-cu12==12.8.93

# 3. + side-chain reconstruction + MD relax
pip install bioemu[md]        # openmm==8.4.0, openmm-cuda-12==8.4.0
                              # (also needs conda on PATH for HPacker auto-setup)
```

Combine: `pip install 'bioemu[cuda,md]'`.

## Requirements

| Resource | Requirement |
|----------|-------------|
| OS | **Linux only** (no Windows, no macOS upstream) |
| Python | **≥ 3.10** |
| GPU | CUDA-capable Nvidia strongly recommended (CPU works but is unusably slow at any realistic length) |
| GPU memory | Scales quadratically with sequence length × `batch_size_100`. For default `batch_size_100=10`: ~20 GB at L≈300, ~70 GB at L≈600 |
| Disk | ~ 3.5 GB AF2 weights + ~ 1 GB per BioEmu checkpoint + your output (samples are small — ~ 1 MB per 100 frames at L=100) |
| `conda` | **Only** if you use `bioemu.sidechain_relax` (HPacker auto-setup). Set `HPACKER_PYTHONBIN` to bypass. |

## What gets downloaded on first use

| File | Location | Trigger | Size |
|------|----------|---------|------|
| AlphaFold2 weights (`params_model_*.npz`) | `~/.cache/colabfold/` | First `bioemu.sample` call | ~ 3.5 GB |
| BioEmu checkpoint (`checkpoints/<model_name>/checkpoint.ckpt`) | HF cache (`~/.cache/huggingface/hub/`) | First `bioemu.sample` call with that `model_name` | ~ 100 MB (31–36 M params) |
| BioEmu config (`checkpoints/<model_name>/config.yaml`) | HF cache | Same | < 100 KB |
| HPacker venv | `~/.cache/bioemu/hpacker/` (override with `HPACKER_VENV_DIR`) | First `bioemu.sidechain_relax` call | ~ 5 GB |

All weights come from `huggingface.co/microsoft/bioemu`. No HuggingFace
login needed (the repo is public).

## Vendored dependencies

These are bundled — **don't** pip-install them separately:

- `src/bioemu/colabfold_inline/` — patched [ColabFold](https://github.com/sokrypton/ColabFold) v1.5.4 (MIT)
- `src/_vendor/alphafold/` — patched [AlphaFold2](https://github.com/google-deepmind/alphafold) v2.3.2 (Apache 2.0)
- `src/bioemu/openfold/` — patched [OpenFold](https://github.com/aqlaboratory/openfold) (Apache 2.0)

You do **not** need an Anthropic-style ColabFold setup; the inlined
ColabFold handles MSA retrieval (default: the public ColabFold MMseqs2
server) and embedding generation in-process.

## Sanity-check

```bash
python - <<'PY'
import torch, jax, bioemu
print("torch CUDA:", torch.cuda.is_available(), "| devices:", torch.cuda.device_count())
print("jax devices:", jax.devices())
print("bioemu:", bioemu.__file__)
PY
```

Then run the chignolin example (~ 30 s on an A100):

```bash
python -m bioemu.sample --sequence GYDPETGTWG --num_samples 10 --output_dir /tmp/chignolin-test
ls /tmp/chignolin-test
# expect: sequence.fasta  topology.pdb  samples.xtc  batch_*.npz
```

## Azure AI Foundry (hosted endpoint, no install)

If you don't want to host BioEmu yourself, Microsoft ships a managed
endpoint on Azure AI Foundry:

1. Open `https://ai.azure.com/explore/models/BioEmu/version/1/registry/azureml`.
2. Deploy a `Standard_NC24ads_A100_v4` instance (~ 30 min for the
   endpoint to come up).
3. POST a JSON body `{"input_data": {"sequence": "<aa>", "num_samples": N}}` with a Bearer-token auth header.
4. The response carries `samples.xtc`, `sequence.fasta`, and
   `topology.pdb` as base64-encoded blobs.

See `AZURE_AI_FOUNDRY.md` in the repo for a full Python snippet.

## License

BioEmu code + weights: **MIT** (Microsoft Corporation).

Vendored dependencies: ColabFold MIT, AlphaFold2 / OpenFold Apache 2.0.
Optional HPacker: see `https://github.com/gvisani/hpacker`.

## Troubleshooting install

| Symptom | Cause | Fix |
|---------|-------|-----|
| `pip install bioemu` fails on macOS / Windows | unsupported OS | Linux only. Use WSL2 on Windows. |
| `jax devices: [CpuDevice]` | base install instead of `[cuda]` | `pip install 'bioemu[cuda]'` (this re-installs JAX with CUDA). |
| `ImportError: cannot import name 'openmm-cuda-12'` | did not install `[md]` | `pip install 'bioemu[md]'`. |
| `RuntimeError: Error running hpacker` on first `sidechain_relax` | conda not on PATH | Install conda; or set `HPACKER_PYTHONBIN=/path/to/python-with-hpacker`. |
| AF2 weight download stalls | colabfold.com flake | The weights live at `https://storage.googleapis.com/alphafold/`. wget them manually into `~/.cache/colabfold/`. |
| HF download stalls | rate limit | `export HF_HUB_DOWNLOAD_TIMEOUT=600`; or pre-download with `huggingface-cli download microsoft/bioemu`. |
