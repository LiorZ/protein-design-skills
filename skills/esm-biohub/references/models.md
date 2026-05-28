# Models — the registry, sizes, where they live, how to load

`esm/utils/constants/models.py` is the canonical name list. Loaders live at
`esm/pretrained.py` (local) and `esm/sdk/forge.py` (remote).

## Local model registry (`LOCAL_MODEL_REGISTRY`)

These are loaded with `ESMC.from_pretrained(name)` / `ESM3.from_pretrained(name)`
and download weights to `$HF_HOME` (Hugging Face cache) on first use.

| Name constant | String | HF repo | Loader | Architecture | Gated? |
|---------------|--------|---------|--------|--------------|--------|
| `ESM3_OPEN_SMALL` | `esm3_sm_open_v1` | (bundled in HF under `EvolutionaryScale/esm3-sm-open-v1`) | `ESM3.from_pretrained(...)` | d=1536, n_heads=24, v_heads=256, n_layers=48 | ✅ accept terms |
| `ESM3_STRUCTURE_ENCODER_V0` | `esm3_structure_encoder_v0` | same | `pretrained.ESM3_structure_encoder_v0(device)` | d=1024, n_heads=1, v_heads=128, n_layers=2, d_out=128, n_codes=4096 | bundled |
| `ESM3_STRUCTURE_DECODER_V0` | `esm3_structure_decoder_v0` | same | `pretrained.ESM3_structure_decoder_v0(device)` | d=1280, n_heads=20, n_layers=30 | bundled |
| `ESM3_FUNCTION_DECODER_V0` | `esm3_function_decoder_v0` | same | `pretrained.ESM3_function_decoder_v0(device)` | defaults | bundled |
| `ESMC_300M` | `esmc_300m` | `Biohub/ESMC-300M` | `ESMC.from_pretrained("esmc_300m")` | d=960, n_heads=15, n_layers=30 | open |
| `ESMC_600M` | `esmc_600m` | `Biohub/ESMC-600M` | `ESMC.from_pretrained("esmc_600m")` | d=1152, n_heads=18, n_layers=36 | open |
| `ESMC_6B` | `esmc_6b` | `Biohub/ESMC-6B` | `ESMC.from_pretrained("esmc_6b")` | d=2560, n_heads=40, n_layers=80 | **gated** |

### Aliases

```python
ESM3_OPEN_SMALL_ALIAS_1 = "esm3-open-2024-03"
ESM3_OPEN_SMALL_ALIAS_2 = "esm3-sm-open-v1"
ESM3_OPEN_SMALL_ALIAS_3 = "esm3-open"
```

All three map to `esm3_sm_open_v1` via `normalize_model_name(...)`. You can
pass any of them to `ESM3.from_pretrained()` and to the API.

### `from_pretrained` behavior

```python
ESMC.from_pretrained(
    model_name: str = ESMC_600M,          # default
    device: torch.device | None = None,    # defaults to "cuda" if available, else "cpu"
    use_flash_attn: bool = True,           # silently false if flash_attn isn't installed
) -> ESMC
```

- Moves weights to `device`.
- **Casts to `bfloat16` automatically** if `device != "cpu"`. To keep fp32:
  load on CPU then `.to("cuda").float()`.
- ESMC layers use `use_flash_attn` — if missing, dense fallback (slower).
- The actual download happens through `huggingface_hub.load_torch_model(model, data_root("esmc-…"))`.

ESM3 has the same signature for `ESM3.from_pretrained`.

## Biohub Platform (Forge) models — API only

These are **never downloaded locally**. Access via the SDK with an
`ESM_API_KEY`:

| Model string | Class | Surface |
|--------------|-------|---------|
| `esm3-sm-open-v1` / `esm3-medium-2024-08` / `esm3-large-…` | `ESM3ForgeInferenceClient` | `from esm.sdk import client; client(model=...)` |
| `esmc-300m-2024-12` / `esmc-600m-2024-12` / `esmc-6b-2024-12` | `ESMCForgeInferenceClient` | `from esm.sdk import esmc_client; esmc_client(model=...)` |
| `esmfold2-2026-05` / `esmfold2-fast-2026-05` | `SequenceStructureForgeInferenceClient` | `from esm.sdk import esmfold2_client; esmfold2_client(model=...)` |

A few SDK-side guards worth knowing:

- `client(model=...)` raises `ValueError` if the name doesn't start with
  `"esm3"`.
- `esmc_client(model=...)` raises if it doesn't start with `"esmc"`.
- `esmfold2_client(model=...)` raises if it doesn't start with `"esmfold2"`.

The platform offers larger ESM3 checkpoints (medium / large) that have
**no local equivalent** — passing those to `ESM3.from_pretrained` raises
`ValueError("Model … not found in local model registry.")`.

## ESMFold2

There is **one architecture** (`ESMFold2Model` in the EvolutionaryScale
`transformers` fork) and effectively two checkpoints:

| Label | Checkpoint | Default loops | Default sampling steps | Use case |
|-------|------------|----------------|------------------------|----------|
| **Full** (`esmfold2-2026-05`) | `biohub/ESMFold2` on HF | 3-10 | 200 | Highest accuracy |
| **Fast** (`esmfold2-fast-2026-05`) | (Biohub Platform only) | 3 | 32 | High throughput / screening |

Load locally:

```python
from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model
model = ESMFold2Model.from_pretrained("biohub/ESMFold2").cuda().eval()
```

Note that `from_pretrained("biohub/ESMFold2")` (lowercase) comes from the
upstream README; HF model-id matching is case-insensitive, but if a future
release renames, prefer the constant
`from esm.utils.constants.models import ESMFOLD2`.

Constants:

```python
ESMFOLD2_FAST = "esmfold2-fast-2026-05"
ESMFOLD2      = "esmfold2-2026-05"
ESMFOLD2_MAX_MSA_SEQS = 16384
```

The fold call:

```python
ESMFold2InputBuilder().fold(
    model,
    spi,
    num_loops=3,             # recycling cycles  (more = better, slower)
    num_sampling_steps=50,   # diffusion sampler steps; full=200, fast=32
    num_diffusion_samples=1, # >1 returns a list[MolecularComplexResult]
    seed=0,
    noise_scale=None,        # sampler override
    step_scale=None,
    max_inference_sigma=None,
    early_exit=False,
    complex_id="pred",
)
```

## ESMC Sparse Autoencoders

SAEs are trained over ESMC hidden states. They're loaded as **plain HF
AutoModels** (no `esm` wrapper), then injected into the ESMC model:

```python
from transformers import AutoModel, AutoTokenizer

model = AutoModel.from_pretrained("Biohub/ESMC-6B", device_map="auto").eval()
tokenizer = AutoTokenizer.from_pretrained("Biohub/ESMC-6B")

sae = AutoModel.from_pretrained(
    "Biohub/ESMC-6B-sae-k64-codebook16384",
    allow_patterns=["config.json", "layer_30.safetensors", "layer_60.safetensors"],
    device=model.device,
)
sae.initialize_layers([30, 60])         # which ESMC layers this codebook covers
model.add_sae_models([sae.layers["30"], sae.layers["60"]])
```

Codebook properties (from the paper / README):

- **k = 64** (sparsity, number of active features per token)
- **codebook size = 16 384** features per codebook
- Trained per-layer; the released codebooks cover **layers 30 and 60** of
  ESMC-6B.
- Each feature has an **agent-generated natural-language description**
  shipped alongside (see the Biohub Atlas UI / HF dataset).

SAE output is a `sparse.coo_tensor` keyed by layer name:

```python
output = model(**inputs)
output["sae_outputs"]["layer60"]          # sparse.coo, shape (L, 16384)
```

Via the SDK (Biohub Platform):

```python
from esm.sdk.api import SAEConfig, LogitsConfig
sae_cfg = SAEConfig(models=["ESMC-6B-sae-layer60-k64-codebook16384"],
                    normalize_features=True)   # MUST be False for ESMC-300M SAEs
out = client.logits(protein_tensor, LogitsConfig(sae_config=sae_cfg), return_bytes=False)
features = out.sae_outputs[sae_cfg.models[0]]   # torch.sparse_coo_tensor
```

More on the SAE API: `references/sae.md`.

## Specific HF Hub model paths used in this repo

Grepped from the codebase + upstream README:

- `Biohub/ESMC-300M` / `Biohub/ESMC-600M` / `Biohub/ESMC-6B`
- `Biohub/ESMFold2`
- `Biohub/ESMC-6B-sae-layer60-k64-codebook16384`
- `Biohub/ESMC-6B-sae-k64-codebook16384` (collection)
- `EvolutionaryScale/esm3-sm-open-v1` (the actual file home for the
  `esm3_sm_open_v1` local name; loader resolves this internally — you don't
  type the slash form)

If you bump a checkpoint version, update the corresponding constant in
`esm/utils/constants/models.py` (or the SDK clients) so the rest of the
code can still call by symbolic name.

## Picking the right model

| Task | Choice | Why |
|------|--------|-----|
| One-shot embedding of a small set | **ESMC-300M** local | Cheap, ungated, fast |
| Production embeddings, downstream classifiers | **ESMC-600M** local | The default; best size/quality ratio |
| Anything paper-grade or matches the Atlas | **ESMC-6B** | The headline model — gated, ~12 GB |
| Fast structure screening | ESMFold2 **fast** via API | 32-step sampling, single-sequence |
| Best ESMFold2 quality | ESMFold2 **full** local | 200-step sampling, MSAs |
| Interpretable feature decomposition | ESMC-6B + **layer-60 SAE** | The codebook the Atlas was built on |
| Inverse folding / motif scaffolding / GFP-style design | **ESM3** open-small (local) or medium/large (API) | Multi-track generative |
| Cross-validate an ESMFold2 prediction | Pair with `boltz`, `chai-lab`, `protenix` | AF3-class cross-check |

## Sanity: confirming a model loaded

```python
from esm.models.esmc import ESMC
m = ESMC.from_pretrained("esmc_300m")
print(next(m.parameters()).device, next(m.parameters()).dtype)
# cpu torch.float32  (on CPU)
# cuda:0 torch.bfloat16 (on GPU — automatic)
```
