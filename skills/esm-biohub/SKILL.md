---
name: esm-biohub
description: >
  Run the **Biohub `esm` repository** (formerly EvolutionaryScale) — the world
  model of protein biology that ships **ESMC** (state-of-the-art protein
  language model), **ESMFold2** (AF3-class structure prediction with proteins
  + DNA + RNA + ligands), **ESM3** (generative model over sequence / structure
  / function), and **ESMC Sparse Autoencoders** (interpretable feature
  decomposition of ESMC's internal representations). Use this skill when:
  (1) Producing **per-residue or pooled embeddings** of one or many sequences
      with ESMC (300M / 600M / 6B) for downstream classification, regression,
      retrieval, clustering, or representation learning,
  (2) **Zero-shot mutation scoring / pseudo-perplexity / entropy** on a
      sequence by sampling masked logits (the headline ESMC use case for
      variant-effect prediction),
  (3) **Fine-tuning** ESMC for a task (PEFT / LoRA classification or
      regression head) or doing a **layer sweep** to find the best feature
      layer for a downstream probe,
  (4) Predicting **all-atom 3D structure** of a protein, protein complex,
      protein + DNA / RNA, or protein + small-molecule ligand with **ESMFold2**
      — optionally with MSAs, residue / nucleotide CCD modifications, or
      covalent bonds; also single-sequence fast mode for high-throughput,
  (5) **Inverse folding** / sequence design from a backbone, **folding** from
      a sequence, **function prediction** (InterPro keyword decoding), and
      iterative **chain-of-thought generation** across tracks with ESM3,
  (6) Extracting **SAE features** from ESMC (the `Biohub/ESMC-6B-sae-…`
      family) to interpret what an ESMC representation has "learned" about a
      sequence (16 384 features, agentic natural-language descriptions),
  (7) Driving any of the above via the **Biohub Platform** (cloud API at
      `https://biohub.ai`, formerly `forge.evolutionaryscale.ai`) instead of
      locally — `client()` / `esmc_client()` / `esmfold2_client()` /
      `SequenceStructureForgeInferenceClient` with `batch_executor` for
      embarrassingly-parallel jobs,
  (8) Working with the canonical **`ESMProtein` / `ESMProteinTensor` /
      `StructurePredictionInput`** dataclasses, the `ProteinChain` /
      `ProteinComplex` / `MolecularComplex` I/O classes (mmCIF + PDB), and
      the structure metrics (lDDT / RMSD / pLDDT / pTM / ipTM /
      pair_chains_iptm).

  This skill is written for running `esm` from an **Apptainer / Singularity
  SIF container** (`esm.sif` built from `esm.def`, lives in
  `$SINGULARITY_HOME`). The runtime is heavy: Python 3.12, PyTorch with
  CUDA 12.6 wheels, the **EvolutionaryScale fork of `transformers`** (pinned
  via `pyproject.toml`), `rdkit`, `biotite`, `flash-attn` (optional),
  `accelerate`, and the full `esm` package — packaging it once into a SIF is
  the only sane way to make it reproducible. The skill covers building the
  SIF, the `apptainer run --nv` / `exec --nv` / `shell --nv` invocation
  patterns, every model in the registry and how to load it (HF Hub vs
  built-in `from_pretrained`), the SDK clients for the Biohub Platform, the
  cookbook tutorials, the input/output dataclasses, the confidence scores,
  and Hugging Face / Torch cache redirection so the read-only image doesn't
  try to write into `/root`.

  Hard limitations: weights are **not baked into the SIF** — they are
  downloaded by HuggingFace at first use into `$HF_HOME` (default
  `~/.cache/huggingface`); the **ESMC 6B** weights are gated and require a
  HuggingFace login (`huggingface-cli login` or `HF_TOKEN` env var); the
  Biohub Platform clients require `ESM_API_KEY`; `flash_attn` is optional
  but recommended (falls back to dense attention if absent); Python is
  pinned to **3.12** (`>=3.12,<3.13`); the package is MIT-licensed but
  individual model weights carry their own licenses (check the HF model
  card).

  Pairs with: `boltz` / `chai-lab` / `protenix` (alternative AF3-class
  co-folders — cross-validate ESMFold2 predictions on the same complex),
  `placer` (atomistic ligand-pose / sidechain refinement on top of an
  ESMFold2 pocket prediction), `boltzgen` / `disco` / `foundry` (de novo
  binder / enzyme design — fold designs with ESMFold2 for validation, or
  use ESMC for sequence scoring), `protflow` (wrap ESM models as pipeline
  steps at SLURM scale), `biotite` (the parser used internally for
  mmCIF/PDB I/O — also useful for downstream structural analysis), and the
  older `fair-esm` skill (legacy Meta ESM-2/ESM-IF1 — same family but a
  different codebase and different model checkpoints).
license: MIT
category: protein-design
tags: [protein-design, language-model, structure-prediction, embeddings, esmc, esmfold2, esm3, sparse-autoencoders, sae, mutation-scoring, inverse-folding, apptainer, singularity, biohub, evolutionaryscale, alphafold3]
repo: https://github.com/Biohub/esm
preprint: https://biohub.ai/papers/esm_protein.pdf
platform: https://biohub.ai/
---

# esm-biohub — Biohub's world model of protein biology (ESMC + ESMFold2 + ESM3 + SAEs)

## What this is

The **`esm`** Python package (repo at `~/Repos/esm_biohub`, version **3.3.0**,
namespace `Biohub/...` on Hugging Face — formerly `EvolutionaryScale`) ships
four production-grade protein models behind one codebase:

| Model | What it does | Sizes | Local? |
|-------|--------------|-------|--------|
| **ESMC** | Pure protein **language model** — encoder-only transformer trained on billions of sequences; emits per-residue logits + hidden states + embeddings. The successor to ESM-2 with stronger long-range structural understanding at scale. | 300M, 600M, **6B** | ✅ HF Hub |
| **ESMC SAEs** | **Sparse autoencoders** trained on ESMC hidden states; decompose a representation into ~16 384 interpretable features with agentic natural-language descriptions. | layer 30 / 60 codebooks (`k=64, codebook=16384`, …) | ✅ HF Hub |
| **ESMFold2** | All-atom **structure prediction**, AF3-class, conditioned on ESMC-6B embeddings. Folds protein + DNA + RNA + ligands; supports MSAs, modifications, covalent bonds. Validated on Foldbench; available in `fast` (single-sequence, 32-step) and full (200-step) variants. | one architecture, two checkpoints | ✅ HF Hub (`Biohub/ESMFold2`) |
| **ESM3** | **Generative** model that reasons jointly over sequence, structure, secondary structure, SASA, and function tokens. The original ESM3; used here for inverse folding, function-conditioned generation, GFP-style de novo design, and chain-of-thought across tracks. | `esm3-sm-open-v1` locally; `esm3-medium-2024-08`, `esm3-large-…` via API only | partial (sm open only) |
| **ESM Atlas** | A **dataset** — 6.8 B protein structures predicted with ESMFold2, organized by ESMC's world model and interpreted with SAEs. Not packaged in the SIF; queried separately via the Biohub Platform. | n/a | n/a |

Two ways to run any of these:

1. **Local** — `from_pretrained` → downloads weights from HF Hub into
   `$HF_HOME` → runs on the host GPU.
2. **Biohub Platform** (cloud API at `https://biohub.ai`, formerly
   `forge.evolutionaryscale.ai`) — `esm.sdk.client()` / `esmc_client()` /
   `esmfold2_client()` → handles its own infra, you pay per call, you need
   `ESM_API_KEY`.

> **Read first — three things that trip people up:**
>
> 1. **Weights are not in the SIF.** The container ships the **code**; HF
>    downloads weights to `$HF_HOME` at first use. Set it to a bind-mounted
>    host path so a 12 GB ESMC-6B download isn't lost when the container
>    exits. ESMC-6B is **gated** on HF — `huggingface-cli login` first.
> 2. **The `Biohub/...` HF namespace.** The README in this repo references
>    the new branding (Biohub, biohub.ai). Some upstream code, examples, and
>    error messages still say "Forge" / "evolutionaryscale" — both are the
>    same platform; the URL `https://biohub.ai` is the canonical one.
> 3. **Python 3.12 is required.** `pyproject.toml` pins `>=3.12,<3.13`. The
>    SIF uses Ubuntu 24.04 (system Python 3.12), so this is handled — but if
>    you try to run outside the SIF with conda, match the version.

## Quickstart — run from the Apptainer SIF

This skill assumes you have built `esm.sif` from `esm.def` and that the
directory containing it is exported as **`$SINGULARITY_HOME`**:

```bash
export SINGULARITY_HOME=/path/to/dir/containing/esm.sif
ls "$SINGULARITY_HOME"/esm.sif       # should exist
```

(The repo also has `Dockerfile` / `Dockerfile.vastai` if you prefer a
container runtime over apptainer — see `references/installation.md`.)

### 1) Build the SIF (one-time)

The definition file at `~/Repos/esm_biohub/esm.def` builds against
`nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04` and installs Python 3.12, the
PyTorch CUDA-12.6 wheels, and the `esm` package + its EvolutionaryScale
`transformers` fork:

```bash
cd ~/Repos/esm_biohub
apptainer build --fakeroot "$SINGULARITY_HOME"/esm.sif esm.def
# Smoke test (does NOT need a GPU at build time, just import):
apptainer exec "$SINGULARITY_HOME"/esm.sif python -c "import esm; print(esm.__version__)"
```

Full build details (fakeroot vs sudo, cluster builds, caches, GPU drivers,
bind-mounting a writable HF cache) are in `references/installation.md`.

### 2) Make the HF model cache persistent (so weights download once)

Model weights are **not** baked into the SIF — HF Hub downloads them at
first use into `$HF_HOME` (default `$HOME/.cache/huggingface`). Apptainer
auto-mounts `$HOME`, so by default **the container shares the host's HF
cache automatically** — every download persists on the host between
runs, and a `huggingface-cli login` you ran on the host carries over.

```bash
# Default (zero-config): host ~/.cache/huggingface is reused inside the container.
huggingface-cli login                                       # once, for gated weights
apptainer exec --nv "$SINGULARITY_HOME"/esm.sif python my_script.py
# First call downloads weights; later calls hit the host cache instantly.
```

If your `$HOME` is small / slow (typical on clusters), bind a scratch
path to `~/.cache/huggingface` inside the container instead:

```bash
HFCACHE=/scratch/$USER/huggingface; mkdir -p "$HFCACHE"
apptainer exec --nv \
  --bind "$HFCACHE":"$HOME/.cache/huggingface" \
  "$SINGULARITY_HOME"/esm.sif python my_script.py
```

Or point `$HF_HOME` at a custom in-container path:

```bash
apptainer exec --nv \
  --bind "$HFCACHE":/hf_cache --env HF_HOME=/hf_cache \
  "$SINGULARITY_HOME"/esm.sif python my_script.py
```

For shared / pre-warmed caches, multi-user clusters, and `HF_HUB_CACHE`
write-through patterns, see `references/installation.md` (the
"Hugging Face cache & gated weights" section covers every variant).

### 3) Run inference (GPU)

```bash
# One-off script (the def file's %runscript is `exec python "$@"`):
apptainer run --nv "$SINGULARITY_HOME"/esm.sif my_script.py --arg ...

# Anything else (e.g. a module, a CLI tool installed in the venv):
apptainer exec --nv "$SINGULARITY_HOME"/esm.sif python -m esm ...

# Interactive shell with the env on PATH:
apptainer shell --nv "$SINGULARITY_HOME"/esm.sif
Apptainer> python
>>> import esm; from esm.models.esmc import ESMC
>>> model = ESMC.from_pretrained("esmc_300m").to("cuda")
```

- `--nv` exposes the host NVIDIA driver/libs — **required** for GPU
  inference. Without it, ESMC and ESMFold2 fall back to CPU (impractical for
  anything but ESMC-300M).
- Apptainer auto-mounts `$HOME` and `$PWD`, so HF caches at
  `$HOME/.cache/huggingface` and your input/output files under `$PWD` resolve
  without extra binds. Anything outside those needs `--bind SRC:DST`.
- Restrict GPUs with `--env CUDA_VISIBLE_DEVICES=0`.

### 4) Hello-world: embed a sequence with ESMC

```bash
apptainer exec --nv "$SINGULARITY_HOME"/esm.sif python <<'PY'
import torch
from esm.models.esmc import ESMC
from esm.sdk.api import ESMProtein, LogitsConfig

model = ESMC.from_pretrained("esmc_300m").to("cuda")  # 300M; gated 6B needs HF login
protein = ESMProtein(sequence="MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGK")
out = model.logits(model.encode(protein),
                   LogitsConfig(sequence=True, return_embeddings=True))
print("logits :", out.logits.sequence.shape, "  embeds:", out.embeddings.shape)
PY
```

Two equivalent invocation modes are documented end-to-end in
`references/esmc.md`:

- **Native HF transformers**: `AutoModelForMaskedLM.from_pretrained("Biohub/ESMC-6B")` —
  the surface most people copy out of the upstream README.
- **`esm.sdk` ESMProtein API**: `ESMC.from_pretrained("esmc_300m")` →
  `client.logits(client.encode(protein), LogitsConfig(...))` — the
  recommended path because the same code works locally and against the
  Biohub Platform.

## Model registry & how to load each one

| Name (local) | HF Hub repo | Loader | Notes |
|--------------|-------------|--------|-------|
| `esmc_300m` | `Biohub/ESMC-300M` | `ESMC.from_pretrained("esmc_300m")` | 30 layers, d=960, ungated |
| `esmc_600m` | `Biohub/ESMC-600M` | `ESMC.from_pretrained("esmc_600m")` | 36 layers, d=1152, ungated |
| `esmc_6b`   | `Biohub/ESMC-6B` | `ESMC.from_pretrained("esmc_6b")` | 80 layers, d=2560, **gated** |
| `esm3_sm_open_v1` | (bundled) | `ESM3.from_pretrained("esm3_sm_open_v1")` | The open ESM3; aliases: `esm3-sm-open-v1`, `esm3-open-2024-03`, `esm3-open` |
| `esm3-medium-2024-08`, `esm3-large-…` | API only | `client(model="esm3-medium-2024-08")` | Biohub Platform; needs `ESM_API_KEY` |
| `esmfold2-2026-05`     | `Biohub/ESMFold2`      | `ESMFold2Model.from_pretrained("biohub/ESMFold2")` | Full, 200-step diffusion |
| `esmfold2-fast-2026-05` | (API model name) | `esmfold2_client(model="esmfold2-fast-2026-05")` | Single-sequence, 32-step |
| `Biohub/ESMC-6B-sae-k64-codebook16384` (and family) | HF Hub | `AutoModel.from_pretrained(...)` | SAEs over ESMC; 16 384 features per codebook |

Full table (parameters, default hyperparams, gated vs open, what the SAE
codebooks look like) is in `references/models.md`. The constants for these
names live at `esm/utils/constants/models.py`.

## The cookbook tutorials (ship inside `/opt/esm/cookbook/`)

When you build the SIF, all of `cookbook/` is baked in at `/opt/esm/cookbook/`.
The tutorials are the official entry point for learning the API:

| Notebook | What it teaches |
|----------|-----------------|
| `tutorials/embed.ipynb` | Embed sequences and explore per-layer information |
| `tutorials/esmc_mutation_scoring.ipynb` | Zero-shot mutation effect (entropy, LLR) — variant scoring |
| `tutorials/esmc_layer_sweep.ipynb` | Find the best ESMC layer for a downstream task (enzyme classification) |
| `tutorials/esmc_finetune.ipynb` | PEFT fine-tuning of an ESMC head |
| `tutorials/esmc_sae_feature_interpretation.ipynb` | Extract SAE features, rank, and map onto 3D structure |
| `tutorials/esmfold2.ipynb` | Fold protein + DNA + RNA + ligand with ESMFold2 |
| `tutorials/esmprotein.ipynb` | The `ESMProtein` class (sequence + structure + function tracks) |
| `tutorials/esm3_generate.ipynb` | ESM3 motif scaffolding, secondary-structure editing |
| `tutorials/esm3_guided_generation.ipynb` | Guided generation with custom scoring functions |
| `tutorials/gfp_design.ipynb` | The novel-GFP design walkthrough from the paper |

```bash
apptainer exec --nv "$SINGULARITY_HOME"/esm.sif \
  jupyter notebook --no-browser --ip 0.0.0.0 --port 8888 /opt/esm/cookbook
```

There is also `cookbook/snippets/` (executable `.py` scripts: `esmc.py`,
`esm3.py`, `sae.py`, `fold_invfold.py`) — short, copy-pasteable.

## SDK at a glance (Biohub Platform clients)

The `esm.sdk` module wraps the cloud API. All clients accept a `token` and
`url` and expose the same `encode` / `decode` / `logits` / `generate` verbs:

```python
import os
from esm.sdk import client, esmc_client, esmfold2_client, batch_executor
from esm.sdk.api import ESMProtein, LogitsConfig

# Pick an API:
esm3 = client(model="esm3-sm-open-v1",      token=os.environ["ESM_API_KEY"])
esmc = esmc_client(model="esmc-600m-2024-12", token=os.environ["ESM_API_KEY"])
fold = esmfold2_client(model="esmfold2-fast-2026-05", token=os.environ["ESM_API_KEY"])

# Use:
out = esmc.logits(esmc.encode(ESMProtein(sequence="MKTLLILAVL...")),
                  LogitsConfig(sequence=True, return_embeddings=True))

# Batch (parallel HTTP, automatic retries):
with batch_executor() as ex:
    results = ex.execute_batch(esmc.encode, input=[ESMProtein(sequence=s) for s in seqs])
```

`ESM_API_KEY` is read from the environment if you don't pass `token=` —
generate a key in the Biohub developer console. Full client surface and
retry/timeout semantics: `references/sdk.md`.

## Input / output dataclasses in 30 seconds

### `ESMProtein` (ESMC, ESM3)

A single protein with optional tracks: `sequence`, `secondary_structure`,
`sasa`, `function_annotations`, `coordinates`, plus metrics (`plddt`, `ptm`,
`pae`, …). Round-trips PDB / mmCIF via `from_pdb` / `to_pdb` and is the unit
of generation/encoding for ESMC and ESM3.

### `StructurePredictionInput` (ESMFold2)

A list of typed entities — `ProteinInput`, `DNAInput`, `RNAInput`,
`LigandInput` — plus optional `covalent_bonds`, `distogram_conditioning`,
`pocket` (binder chain + contact list), and per-chain MSAs. Lives at
`esm.utils.structure.input_builder`. Re-exported from
`esm.models.esmfold2`.

```python
from esm.models.esmfold2 import (
    ProteinInput, DNAInput, RNAInput, LigandInput, Modification,
    StructurePredictionInput, ESMFold2InputBuilder)
from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model

spi = StructurePredictionInput(sequences=[
    ProteinInput(id="A", sequence="MIEIK..."),
    DNAInput(id="B", sequence="GATAGCGCTATC",
             modifications=[Modification(position=5, ccd="C36")]),
    LigandInput(id="L", ccd=["SAH"]),
])
model = ESMFold2Model.from_pretrained("biohub/ESMFold2").cuda().eval()
result = ESMFold2InputBuilder().fold(model, spi,
                                     num_loops=3, num_sampling_steps=50,
                                     num_diffusion_samples=1, seed=0)
print(f"pLDDT={result.plddt.mean():.3f}  pTM={result.ptm:.3f}  ipTM={result.iptm:.3f}")
open("pred.cif","w").write(result.complex.to_mmcif())
```

Full schema (every field, every entity type, MSA injection, covalent bonds,
distogram conditioning, pocket constraints) is in `references/esmfold2.md`.

### `MolecularComplexResult` (ESMFold2 output)

`.complex` (a `MolecularComplex` — flat atom array with chain & token info,
serializes to mmCIF/PDB) + per-sample `plddt`, `ptm`, `iptm`, `pae`,
`distogram`, `pair_chains_iptm`, `residue_index`, `entity_id`. Documented in
`references/outputs.md`.

## Confidence — what to rank on

ESMFold2 emits AlphaFold3-style scores per diffusion sample:

- **`plddt`** — per-residue confidence, mean is a good global proxy.
- **`ptm` / `iptm`** — global / interface predicted TM-score (→1 better).
- **`pair_chains_iptm`** — per chain-pair ipTM (judging individual
  interfaces in a multi-chain complex).
- **`pae`** — predicted aligned error grid.

For ESM3 generations: `plddt`, `ptm`, and (for batch generation)
`ESMProteinError` mixed with `ESMProtein` so check `isinstance(p,
ESMProtein)` before consuming. Full score definitions and ranking guidance
in `references/outputs.md`.

## Gotchas (read before you debug)

1. **HF gating on ESMC-6B.** First run will 401 unless you've done
   `huggingface-cli login` (or set `HF_TOKEN`) and accepted the model card.
   Bind the host's HF cache so the login persists.
2. **HF cache in `/root` is read-only.** The SIF's `%environment` defaults
   `HF_HOME=${HF_HOME:-$HOME/.cache/huggingface}` and `TORCH_HOME=…/torch`.
   These resolve to the **calling user's** `$HOME` (which apptainer mounts).
   If you set them to a custom path, make sure the path is writable and
   bind-mounted.
3. **`flash_attn` is optional.** ESMC tries to use it; if it can't import,
   it falls back to dense attention. The SIF doesn't install flash-attn by
   default — install it inside the venv only if you really need the speed
   bump and have a matching CUDA toolchain.
4. **`--nv` is required for GPU.** Without it, the container can't see the
   driver and everything runs on CPU. Even ESMC-300M is slow on CPU.
5. **`use_flash_attn=True` is the loader default**, but it silently noops
   if `flash_attn` isn't installed (`is_flash_attn_available = False`). No
   error — just unexpectedly slow.
6. **Models cast to bf16 on GPU.** `ESMC.from_pretrained` calls
   `.to(torch.bfloat16)` automatically on non-CPU devices. If you need
   fp32, do `.float()` or pass `device="cpu"` first.
7. **`from_rcsb("...")` hits the RCSB network.** Useful in examples but
   needs Internet inside the container — `apptainer run` inherits the host
   network, so this generally Just Works. For air-gapped clusters, cache
   structures locally and use `ProteinChain.from_pdb` instead.
8. **`batch_generate` can return `ESMProteinError`** for individual prompts
   (e.g. a prompt with no masked positions). Always
   `isinstance(p, ESMProtein)` before using `.sequence` / `.to_pdb()`.
9. **ESM3 forge models are HTTPS-only.** `esm3-medium-…` / `esm3-large-…`
   are not downloaded locally; passing one to `ESM3.from_pretrained` will
   raise `ValueError(f"Model … not found in local model registry.")`. Use
   `client(model="esm3-medium-2024-08", token=...)` instead.
10. **`SAEConfig(model=...)` is deprecated.** Use `SAEConfig(models=[...])`.
    For ESMC-300M SAEs you must also pass `normalize_features=False`
    (300M SAEs don't have normalization stats).

Full failure modes and fixes: `references/troubleshooting.md`.

## Reference index

- `references/installation.md` — building the SIF (`esm.def`, fakeroot,
  CUDA driver, bind-mounts, HF cache, conda / Docker / vast.ai fallbacks),
  the `$SINGULARITY_HOME` convention.
- `references/models.md` — every model in the registry, sizes, gating,
  default cycle/step (ESMFold2), aliases, and which surface (local /
  Biohub Platform) supports which model.
- `references/esmc.md` — ESMC API, embeddings, logits, mutation scoring,
  pseudo-perplexity, layer sweeps, fine-tuning entry points.
- `references/esmfold2.md` — `StructurePredictionInput` schema,
  `ESMFold2InputBuilder.fold()`, MSAs, modifications, covalent bonds,
  pocket / distogram conditioning, the `fast` variant.
- `references/esm3.md` — `ESMProtein` tracks, `GenerationConfig`,
  `SamplingConfig`, encode/decode/generate/forward_and_sample, batch
  generation, function prediction, chain-of-thought, GFP design pattern.
- `references/sae.md` — SAEs over ESMC, `SAEConfig`, the codebooks, feature
  interpretation, max-pooling, `normalize_features=False` for 300M.
- `references/sdk.md` — `client()` / `esmc_client()` / `esmfold2_client()`
  / `SequenceStructureForgeInferenceClient`, `batch_executor`,
  `ESM_API_KEY`, retry / timeouts, the `Forge` → `Biohub` rename.
- `references/outputs.md` — `ESMProtein`, `MolecularComplex(Result)`,
  every confidence score, PDB / mmCIF serialization.
- `references/troubleshooting.md` — flash-attn / CUDA / HF cache / PEP-668 /
  OOM / network errors.
- `examples/esm.def` — the Apptainer definition file (copy of the
  upstream).
- `examples/commandline_examples.sh` — copy-paste container invocations
  (build, run a script, drop into a shell, run a cookbook notebook).
- `examples/esmc_embed.py` — minimal local ESMC embedding script.
- `examples/esmfold2_fold.py` — minimal local ESMFold2 fold script.
- `examples/sae_features.py` — extract SAE features via the SDK.

## Installing this skill

```bash
# Symlink (recommended — picks up edits live)
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/esm-biohub
# Or copy:
cp -R . ~/.claude/skills/esm-biohub
```

After that, an agent invokes it via `Skill(skill="esm-biohub")`.

## Citation

Biohub / EvolutionaryScale Team. MIT-licensed code; per-weight licenses on
HF.

```
Candido et al.
Language Modeling Materializes a World Model of Protein Biology.
Preprint, 2026. https://biohub.ai/papers/esm_protein.pdf
```

```
Hayes et al.
Simulating 500 million years of evolution with a language model.
Science, 2025. https://doi.org/10.1126/science.ads0018
```

```
EvolutionaryScale Team. evolutionaryscale/esm. Zenodo, 2024.
https://doi.org/10.5281/zenodo.14219303
```
